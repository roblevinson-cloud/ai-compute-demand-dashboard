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

API = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
PARTNERS = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
REPORTER = 156
CMD = "8703"
START = "2020-01"
MIDDLE_EAST = {
    "ARE", "SAU", "QAT", "KWT", "OMN", "BHR", "ISR", "JOR", "LBN",
    "IRQ", "IRN", "YEM", "SYR", "TUR", "PSE"
}
NORTH_AMERICA = {"USA", "CAN", "GRL", "BMU", "SPM"}


def months_between(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


def shift_month(period: str, delta: int):
    y, m = map(int, period.split("-"))
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def last_completed_month():
    today = date.today()
    return shift_month(f"{today.year:04d}-{today.month:02d}", -1)


def get_json(session: requests.Session, url: str, params=None, tries=6):
    delay = 1.25
    for attempt in range(tries):
        r = session.get(url, params=params, timeout=90)
        if r.status_code in (429, 409, 502, 503, 504):
            if attempt == tries - 1:
                r.raise_for_status()
            time.sleep(float(r.headers.get("Retry-After", delay)))
            delay *= 1.8
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Unable to fetch {url}")


def load_partner_names(session):
    payload = get_json(session, PARTNERS)
    rows = payload.get("results", []) if isinstance(payload, dict) else []
    out = {}
    for row in rows:
        raw_id = row.get("id", row.get("partnerCode"))
        if raw_id is None or str(raw_id).lower() == "all":
            continue
        try:
            code = int(raw_id)
        except Exception:
            continue
        out[code] = {
            "name": row.get("text") or row.get("partnerDesc") or f"Partner {code}",
            "group": bool(row.get("isGroup", False)),
        }
    return out


def clean_number(value):
    if value is None:
        return None
    try:
        x = float(value)
        if not math.isfinite(x):
            return None
        return x
    except Exception:
        return None


def fetch_month(session, month: str, partner_names):
    params = {
        "reportercode": REPORTER,
        "period": month.replace("-", ""),
        "flowCode": "X",
        "cmdCode": CMD,
        "maxRecords": 500,
        "breakdownMode": "classic",
        "includeDesc": "true",
    }
    payload = get_json(session, API, params=params)
    err = payload.get("error") if isinstance(payload, dict) else None
    if err:
        raise RuntimeError(str(err))
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if int(payload.get("count", len(rows))) >= 500:
        raise RuntimeError(f"{month}: UN Comtrade preview reached the 500-record ceiling")

    world = None
    seen = {}
    for row in rows:
        pcode = row.get("partnerCode")
        try:
            pcode = int(pcode)
        except Exception:
            continue
        value = clean_number(row.get("primaryValue"))
        if value is None:
            value = clean_number(row.get("fobvalue"))
        qty = clean_number(row.get("qty"))
        iso3 = (row.get("partnerISO") or "").upper().strip()
        pname = row.get("partnerDesc") or partner_names.get(pcode, {}).get("name") or f"Partner {pcode}"
        qty_abbr = str(row.get("qtyUnitAbbr") or "").strip().lower()
        unit_like = qty_abbr in {"u", "unit", "units", "number", "number of items", "no"}
        units = qty if unit_like else None

        if pcode == 0 or iso3 == "W00" or str(pname).lower() == "world":
            world = {"period": month, "units": units, "value_usd": value}
            continue
        if len(iso3) != 3 or not iso3.isalpha():
            continue
        if partner_names.get(pcode, {}).get("group"):
            continue

        rec = {
            "period": month,
            "partner_code": pcode,
            "iso3": iso3,
            "country": pname,
            "units": units,
            "value_usd": value,
            "qty_estimated": bool(row.get("isQtyEstimated", False)),
        }
        key = (pcode, iso3)
        if key not in seen:
            seen[key] = rec
        else:
            for field in ("units", "value_usd"):
                a, b = seen[key].get(field), rec.get(field)
                if a is None:
                    seen[key][field] = b
                elif b is not None:
                    seen[key][field] = a + b
            seen[key]["qty_estimated"] = seen[key]["qty_estimated"] or rec["qty_estimated"]

    countries = list(seen.values())
    if world is None:
        world = {
            "period": month,
            "units": sum(r["units"] or 0 for r in countries) or None,
            "value_usd": sum(r["value_usd"] or 0 for r in countries) or None,
        }
    return countries, world


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
            region = "Middle East"
        else:
            cont = continents.get(iso, "Unknown")
            if cont == "America":
                region = "North America" if iso in NORTH_AMERICA else "Latin America"
            elif cont in {"Asia", "Europe", "Africa", "Oceania"}:
                region = cont
            else:
                region = "Other"
        r["region"] = region
    return records


def load_existing(path: Path):
    if not path.exists():
        return [], []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("records", []), payload.get("world_totals", [])
    except Exception:
        return [], []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="docs/china-auto/data/exports.json")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing, existing_world = load_existing(out)
    existing_periods = sorted({r.get("period") for r in existing if r.get("period")})
    end = last_completed_month()
    fetch_start = START if args.full or not existing_periods else max(START, shift_month(existing_periods[-1], -3))

    session = requests.Session()
    session.headers.update({"User-Agent": "roblevinson-cloud-china-auto-monitor/1.0"})
    partner_names = load_partner_names(session)
    replacement_records, replacement_world, errors = [], [], []
    print(f"Refreshing China HS 8703: {fetch_start} through {end}")

    for month in months_between(fetch_start, end):
        try:
            rows, world = fetch_month(session, month, partner_names)
            if rows:
                replacement_records.extend(rows)
                replacement_world.append(world)
                print(f"{month}: {len(rows)} destinations")
            else:
                print(f"{month}: no published rows")
        except Exception as exc:
            errors.append({"period": month, "error": str(exc)})
            print(f"{month}: ERROR {exc}")
        time.sleep(1.1)

    kept = [r for r in existing if r.get("period", "") < fetch_start]
    kept_world = [r for r in existing_world if r.get("period", "") < fetch_start]
    records = add_regions(kept + replacement_records)
    world_totals = kept_world + replacement_world
    records.sort(key=lambda r: (r.get("period", ""), r.get("country", "")))
    world_totals.sort(key=lambda r: r.get("period", ""))
    published_periods = sorted({r["period"] for r in records})
    latest = published_periods[-1] if published_periods else None
    meta = {
        "status": "ok" if records else "empty",
        "title": "China Passenger Vehicle Export Monitor",
        "reporter": "China",
        "reporter_code": REPORTER,
        "flow": "Exports",
        "hs_code": CMD,
        "hs_description": "Motor cars and other motor vehicles principally designed for transport of persons",
        "frequency": "Monthly",
        "currency": "USD",
        "start_period": published_periods[0] if published_periods else START,
        "latest_period": latest,
        "updated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "UN Comtrade, China-reported customs exports",
        "source_url": "https://comtradeplus.un.org/TradeFlow",
        "record_count": len(records),
        "refresh_errors": errors[-12:],
        "note": "HS 8703 customs export values are border/export values, not retail sales prices.",
    }
    payload = {"meta": meta, "world_totals": world_totals, "records": records}
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(records)} records; latest published month: {latest}")


if __name__ == "__main__":
    main()
