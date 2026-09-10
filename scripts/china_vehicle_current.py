from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

try:
    import country_converter as coco
except Exception:
    coco = None

CHINA_DATA = "https://chinadata.live/api/v2/trade/hs/8703"
COMTRADE = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
CHINA_CODE = 156
START = "2024-01"

MIDDLE_EAST = {
    "ARE", "SAU", "QAT", "KWT", "OMN", "BHR", "ISR", "JOR", "LBN",
    "IRQ", "IRN", "YEM", "SYR", "TUR", "PSE"
}
NORTH_AMERICA = {"USA", "CAN", "GRL", "BMU", "SPM"}

# Latest published Gasgoo Automotive Research Institute passenger-vehicle
# destination benchmark. It is cumulative Jan-Jul 2026, not a monthly customs
# series, and is deliberately kept separate from the core/mirror records.
GASGOO_BENCHMARK = {
    "period_label": "Jan-Jul 2026",
    "as_of_period": "2026-07",
    "published": "2026-09-09",
    "source": "Gasgoo Automotive Research Institute",
    "source_url": "https://autonews.gasgoo.com/articles/news/chinas-passenger-vehicle-export-overview-jan-jul-2026-russia-leads-with-524428-unitsgasgoo-automotive-research-institute-2097621553725657088",
    "scope": "Cumulative passenger-vehicle exports by destination; top 10 only",
    "top_destinations": [
        {"country": "Russia", "units": 524428, "yoy": 1.434},
        {"country": "Brazil", "units": 408393, "yoy": 1.484},
        {"country": "United Kingdom", "units": 315653, "yoy": 0.948},
        {"country": "Belgium", "units": 266050, "yoy": 0.488},
        {"country": "Australia", "units": 261182, "yoy": 0.911},
        {"country": "Mexico", "units": 191418, "yoy": -0.248},
        {"country": "Italy", "units": 171454, "yoy": 1.297},
        {"country": "United Arab Emirates", "units": 156615, "yoy": -0.387},
        {"country": "Spain", "units": 139565, "yoy": 0.646},
        {"country": "Malaysia", "units": 124759, "yoy": 0.390},
    ],
}


def month_iter(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


def clean_number(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def get_json(session: requests.Session, url: str, params=None, tries: int = 6):
    delay = 2.0
    for attempt in range(tries):
        r = session.get(url, params=params, timeout=90)
        if r.status_code == 429:
            if attempt == tries - 1:
                r.raise_for_status()
            time.sleep(float(r.headers.get("Retry-After", delay)))
            delay = min(delay * 1.7, 15)
            continue
        if r.status_code in (502, 503, 504):
            if attempt == tries - 1:
                r.raise_for_status()
            time.sleep(delay)
            delay = min(delay * 1.7, 15)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Unable to fetch {url}")


def period_from_obj(obj):
    raw = obj.get("period") or obj.get("month") or obj.get("date")
    if raw is None:
        return None
    s = str(raw).replace("-", "")[:6]
    if len(s) == 6 and s.isdigit():
        return f"{s[:4]}-{s[4:]}"
    return None


def fetch_gacc_value_pulse(session: requests.Session):
    current_year = date.today().year
    monthly_by_period = {}
    latest_payload = None
    errors = []

    for year in range(2025, current_year + 1):
        try:
            payload = get_json(
                session,
                CHINA_DATA,
                params={"flow": "export", "period": str(year), "limit": 20},
            )
            if not payload.get("success", True):
                raise RuntimeError(payload.get("error") or f"China Data Portal returned success=false for {year}")
            for row in payload.get("monthly") or []:
                period = period_from_obj(row)
                value = clean_number(row.get("value_usd"))
                if period and value is not None:
                    monthly_by_period[period] = {"period": period, "value_usd": value}
            cov = payload.get("coverage") or {}
            if cov.get("latest_month"):
                latest_payload = payload
        except Exception as exc:
            errors.append({"year": year, "error": str(exc)})
        time.sleep(1.0)

    # If monthly rows were omitted for some response shape, use the latest object.
    if latest_payload:
        latest_obj = latest_payload.get("latest") or {}
        lp = period_from_obj(latest_obj)
        lv = clean_number(latest_obj.get("value_usd"))
        if lp and lv is not None:
            monthly_by_period[lp] = {"period": lp, "value_usd": lv}

    monthly = sorted(monthly_by_period.values(), key=lambda x: x["period"])
    latest_period = monthly[-1]["period"] if monthly else None
    latest_partners = []
    coverage = {}
    if latest_payload:
        coverage = latest_payload.get("coverage") or {}
        for row in latest_payload.get("latest_partners") or []:
            latest_partners.append({
                "partner_code": str(row.get("partner_code") or ""),
                "country": row.get("partner_name") or "Unknown",
                "rank": row.get("partner_rank"),
                "value_usd": clean_number(row.get("value_usd")),
                "share": clean_number(row.get("share")),
                "period": period_from_obj({"period": row.get("latest_month")}) or latest_period,
            })

    return {
        "source": "GACC via China Data Portal public HS4 API",
        "source_url": "https://chinadata.live/china-trade/hs/8703/",
        "hs_code": "8703",
        "latest_period": latest_period,
        "coverage": coverage,
        "monthly_value": monthly,
        "latest_partners": latest_partners,
        "public_partner_limit": latest_payload.get("public_partner_limit") if latest_payload else None,
        "errors": errors,
        "note": "Monthly total USD value covers all GACC partner rows. Public destination detail is limited to the latest top 20 partners and does not expose quantity.",
    }


def add_regions(records):
    unique = sorted({r.get("iso3") for r in records if r.get("iso3")})
    continents = {}
    if coco and unique:
        try:
            cc = coco.CountryConverter()
            converted = cc.convert(names=unique, to="continent", not_found="Unknown")
            if isinstance(converted, str):
                converted = [converted]
            continents = dict(zip(unique, converted))
        except Exception:
            continents = {}
    for r in records:
        iso = r.get("iso3")
        if iso in MIDDLE_EAST:
            r["region"] = "Middle East"
        else:
            cont = continents.get(iso, "Unknown")
            if cont == "America":
                r["region"] = "North America" if iso in NORTH_AMERICA else "Latin America"
            elif cont in {"Asia", "Europe", "Africa", "Oceania"}:
                r["region"] = cont
            else:
                r["region"] = "Other"
    return records


def fetch_mirror_month(session: requests.Session, period: str):
    params = {
        "period": period.replace("-", ""),
        "flowCode": "M",
        "partnerCode": CHINA_CODE,
        "partner2Code": 0,
        "cmdCode": "8703",
        "customsCode": "C00",
        "motCode": 0,
        "maxRecords": 500,
        "breakdownMode": "classic",
        "includeDesc": "true",
    }
    payload = get_json(session, COMTRADE, params=params)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    rows = payload.get("data") or []
    if int(payload.get("count", len(rows))) >= 500:
        raise RuntimeError(f"{period}: mirror request reached 500-row preview ceiling")

    out = []
    for row in rows:
        iso = str(row.get("reporterISO") or "").upper().strip()
        if len(iso) != 3 or not iso.isalpha() or iso == "W00":
            continue
        qty = clean_number(row.get("qty"))
        unit_abbr = str(row.get("qtyUnitAbbr") or "").strip().lower()
        units = qty if unit_abbr in {"u", "unit", "units", "number", "number of items", "no"} else None
        cif = clean_number(row.get("cifvalue"))
        fob = clean_number(row.get("fobvalue"))
        primary = clean_number(row.get("primaryValue"))
        # For a destination-reported import series, primaryValue is normally CIF.
        # Preserve both and expose an export-like value only when FOB is actually reported.
        out.append({
            "period": period,
            "reporter_code": row.get("reporterCode"),
            "iso3": iso,
            "country": row.get("reporterDesc") or iso,
            "units": units,
            "mirror_value_usd": primary,
            "cif_value_usd": cif,
            "fob_value_usd": fob,
            "qty_estimated": bool(row.get("isQtyEstimated", False)),
            "value_basis": "FOB available" if fob is not None else "CIF/import value",
        })
    return out


def fetch_mirror(session: requests.Session, end: str):
    records = []
    coverage = []
    errors = []
    for period in month_iter(START, end):
        try:
            rows = fetch_mirror_month(session, period)
            records.extend(rows)
            coverage.append({
                "period": period,
                "reporter_count": len(rows),
                "units_reporter_count": sum(r.get("units") is not None for r in rows),
                "fob_reporter_count": sum(r.get("fob_value_usd") is not None for r in rows),
            })
            print(f"mirror {period}: {len(rows)} reporters")
        except Exception as exc:
            errors.append({"period": period, "error": str(exc)})
            print(f"mirror {period}: ERROR {exc}")
        time.sleep(2.2)
    add_regions(records)
    records.sort(key=lambda r: (r["period"], r["country"]))
    published = [c["period"] for c in coverage if c["reporter_count"]]
    return {
        "source": "UN Comtrade destination-reported imports from China",
        "source_url": "https://comtradeplus.un.org/TradeFlow",
        "scope": "HS 8703 imports where partner=China; partner-country mirror of Chinese exports",
        "latest_period": published[-1] if published else None,
        "records": records,
        "coverage": coverage,
        "errors": errors[-20:],
        "note": "Mirror coverage depends on destination-country reporting schedules. Import values are generally CIF and are not directly comparable with China-reported FOB export values. Country-level units remain useful as a current direction-of-travel check.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/china-auto/data/current.json")
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "roblevinson-cloud-china-auto-monitor/1.1"})

    gacc = fetch_gacc_value_pulse(session)
    mirror_end = gacc.get("latest_period") or f"{date.today().year:04d}-{date.today().month:02d}"
    mirror = fetch_mirror(session, mirror_end)

    payload = {
        "meta": {
            "updated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "core_history_note": "Complete China-reported country-month HS 8703 history remains in exports.json through the latest UN Comtrade China release.",
            "current_value_latest_period": gacc.get("latest_period"),
            "mirror_latest_period": mirror.get("latest_period"),
            "methodology": "Current layer keeps unlike sources separate: GACC for complete aggregate USD and public top-20 destination values; partner-reported Comtrade mirror for available monthly destination units/value; Gasgoo for a cumulative top-10 passenger-vehicle unit benchmark.",
        },
        "gacc": gacc,
        "mirror": mirror,
        "volume_benchmark": GASGOO_BENCHMARK,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        "current pulse:",
        "GACC latest", gacc.get("latest_period"),
        "mirror latest", mirror.get("latest_period"),
        "mirror rows", len(mirror.get("records") or []),
    )


if __name__ == "__main__":
    main()
