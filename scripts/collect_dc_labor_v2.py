from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "dc_labor"
RAW_DIR = DATA_DIR / "raw"
DOCS_DIR = ROOT / "docs" / "labor"
CONFIG_PATH = ROOT / "config" / "dc_labor_markets.json"
SOURCE_URL = "https://where2bro.com/hot-spots/"
UA = "ai-compute-demand-dashboard/2.0 (+https://github.com/roblevinson-cloud/ai-compute-demand-dashboard)"

DC_TERMS = {
    "DATA CENTER": 1.00, "DATACENTER": 1.00, "QTS": 0.98, "EQUINIX": 0.98,
    "DATABANK": 0.98, "MICROSOFT": 0.92, "META": 0.92, "FACEBOOK": 0.92,
    "EDGECORE": 0.98, "VANTAGE": 0.98, "SWITCH": 0.95, "GOOGLE": 0.90,
    "COMPASS": 0.98, "EDGED DATA": 0.98, "PROJECT MINER": 0.99,
    "PROJECT SPADE": 0.99, "BIGHORN": 0.88, "RNO1": 0.88, "RNO 2": 0.88,
    "STY CAMPUS": 0.80, "STREAM DATA": 0.98, "LMA1": 0.90,
}

PROJECT_RULES = [
    (r"PROJECT MINER", "Project Miner / Santa Teresa"),
    (r"META EL PASO|VFC META", "Meta El Paso"),
    (r"PROJECT ACCORDIAN", "Project Accordian"),
    (r"EWD DATA CENTER", "EWD Data Center"),
    (r"QTS", "QTS"), (r"MICROSOFT", "Microsoft"),
    (r"EDGECORE|RNO1", "EdgeCore"), (r"RNO\s*2", "RNO 2"),
    (r"VANTAGE", "Vantage"), (r"BIGHORN DATA CENTER", "Bighorn Data Center"),
    (r"PROJECT SPADE", "Google Project Spade"), (r"GOOGLE", "Google"),
    (r"EQUINIX", "Equinix"), (r"DATABANK", "DataBank"),
    (r"STREAM DATA", "Stream Data Centers"), (r"SWITCH", "Switch"),
    (r"EDGED DATA", "Edged Data Center"), (r"ALIGNED", "Aligned"),
    (r"PORT WASHINGTON DATA CENTER", "Port Washington Data Center"),
    (r"FULTON INDUSTRIAL DATA CENTER", "Fulton Industrial Data Center"),
    (r"T5 DATA CENTER", "T5 Data Center"), (r"LMA1 DATA CENTER", "LMA1 Data Center"),
    (r"FACEBOOK", "Meta / Facebook"), (r"\bMETA\b", "Meta"),
]


class TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "br", "hr", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts)).replace("\xa0", " ").replace("\u200b", "")
        lines = [re.sub(r"\s+", " ", x).strip() for x in raw.splitlines()]
        return "\n".join(x for x in lines if x)


@dataclass
class Call:
    observed_at: str
    source_date: str
    local: str
    market: str
    city_label: str
    project: str
    openings: int
    weekly_hours: float | None
    base_hourly: float | None
    incentive_hourly: float | None
    per_diem_daily: float | None
    ot_multiplier: float | None
    confidence: float
    stress_score: float
    source_url: str
    source_text: str


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def dc_confidence(text: str) -> float:
    up = text.upper()
    return max((score for term, score in DC_TERMS.items() if term in up), default=0.0)


def project_for(text: str) -> str:
    up = text.upper()
    for pattern, name in PROJECT_RULES:
        if re.search(pattern, up):
            return name
    return "Unclassified data center"


def parse_source_date(mmdd: str, observed: datetime) -> str:
    month, day = map(int, mmdd.split("-"))
    year = observed.year
    probe = datetime(year, month, day, tzinfo=timezone.utc)
    if (observed - probe).days > 180:
        year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_weekly_hours(text: str) -> float | None:
    t = text.upper().replace("’", "'").replace("×", "X")
    m = re.search(r"(\d{2})\s*,\s*(\d{2})\s*,\s*(\d{2})\s*/?\s*HR", t)
    if m:
        return round(sum(map(int, m.groups())) / 3, 1)
    m = re.search(r"(\d)\s*[-/X]\s*(8|9|10|12)\s*'?S?\s*(?:&|\+)\s*(\d)\s*[-/X]\s*(8|9|10|12)\s*'?S?", t)
    if m:
        a, b, c, d = map(int, m.groups())
        return float(a * b + c * d)
    m = re.search(r"(\d{2})\s*[-–]\s*(\d{2})\s*(?:HOURS?|HRS?)\s*(?:PER\s*)?WEEK", t)
    if m:
        return round((int(m.group(1)) + int(m.group(2))) / 2, 1)
    m = re.search(r"(?:WORKING\s*)?\(?(\d)\)?\s*[-/X]?\s*(8|9|10|12)\s*'?S", t)
    if m:
        return float(int(m.group(1)) * int(m.group(2)))
    m = re.search(r"SCHEDULE\s*:\s*(\d)\s*/\s*(8|9|10|12)S", t)
    if m:
        return float(int(m.group(1)) * int(m.group(2)))
    m = re.search(r"(\d{2})\s*(?:HR|HRS|HOURS)\s*(?:PER|/)\s*(?:WK|WEEK)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{2})\s*/?HR\s*(?:PER\s*)?(?:WK|WEEK)", t)
    if m:
        return float(m.group(1))
    if re.search(r"5[_ -]DAY.*10[- ]HOUR", t):
        return 50.0
    return None


def parse_money(text: str) -> tuple[float | None, float | None, float | None]:
    t = text.upper().replace(",", "")
    base = incentive = per_diem = None
    m = re.search(r"\$(\d+(?:\.\d+)?)\s*/?\s*(?:HR|HOUR)\b", t)
    if m:
        base = float(m.group(1))
    if base is None:
        m = re.search(r"(?:PAYS?|PAYING|WAGE|RATE)\s*(?:IS|OF|:|-)?\s*\$(\d+(?:\.\d+)?)\s*(?:PER\s*HOUR|/HR)?", t)
        if m:
            base = float(m.group(1))
    for pat in [
        r"\+\s*\$(\d+(?:\.\d+)?)\s*(?:/HR|/HOUR)?\s*INCENTIVE",
        r"\$(\d+(?:\.\d+)?)\s*/?\s*(?:HR|HOUR)?\s*(?:OVER\s*SCALE|OVERSCALE|OVER\b)",
        r"PAYING\s*\$(\d+(?:\.\d+)?)\s*(?:/HR|/HOUR)?\s*OVER",
        r"\$(\d+(?:\.\d+)?)\s*(?:/HR)?\s*ZONE PAY",
    ]:
        m = re.search(pat, t)
        if m:
            incentive = float(m.group(1)); break
    for pat in [
        r"\$(\d+(?:\.\d+)?)\s*/?\s*DAY\s*(?:PER\s*DIEM|PERDIEM|INCENTIVE)?",
        r"\$(\d+(?:\.\d+)?)\s*(?:A|PER)\s*DAY\s*(?:PER\s*DIEM|PERDIEM|INCENTIVE)?",
        r"(\d+(?:\.\d+)?)\$\s*INCENTIVE\s*ON\s*EACH\s*\d+[- ]HOUR\s*DAY",
    ]:
        m = re.search(pat, t)
        if m:
            per_diem = float(m.group(1)); break
    return base, incentive, per_diem


def parse_ot(text: str) -> float | None:
    t = text.upper()
    if any(x in t for x in ("DOUBLE TIME", "ALL OT IS DT", "ALL O/T PAID DOUBLE", "ALL OT WILL BE DT", "ALL OT IS DOUBLE")):
        return 2.0
    if "TIME AND A HALF" in t or "TIME & A HALF" in t:
        return 1.5
    return None


def stress_score(openings: int, hours: float | None, incentive: float | None, per_diem: float | None, ot: float | None) -> float:
    score = min(40.0, 10.0 * math.log1p(max(openings, 0)))
    if hours:
        score += min(20.0, max(0.0, hours - 40.0))
    if incentive:
        score += min(20.0, incentive)
    if ot == 2.0:
        score += 10.0
    elif ot == 1.5:
        score += 5.0
    if per_diem:
        score += min(10.0, per_diem / 20.0)
    return round(min(100.0, score), 1)


def segments(text: str):
    # Date-shaped parentheses distinguish live local sections from the district index.
    header = re.compile(r"(?m)(?:^|\n)[^\n]*?\bLU-?\s*(\d+)\s+([^\n]+?)\s+\((\d{1,2}-\d{1,2})\)")
    matches = list(header.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield m.group(1), m.group(2).strip(), m.group(3), text[m.end():end].strip()


def call_records(segment_text: str) -> list[tuple[int, str]]:
    lines = [x.strip() for x in segment_text.splitlines() if x.strip()]
    out: list[tuple[int, str]] = []
    exact_calls = re.compile(r"^(\d+)\s+CALLS?$", re.I)
    for i, line in enumerate(lines):
        # Structured multi-line boards, including El Paso Local 583.
        m = re.search(r"\bPOSITION(?:S AVAILABLE)?\s*:\s*(\d+)(?:\s+OPEN)?\b", line, re.I)
        if m:
            prior = lines[i - 1] if i else ""
            tail = " ".join(lines[i + 1:i + 4])
            out.append((int(m.group(1)), f"{prior} {line} {tail}"))
            continue
        m = re.search(r"\bNUMBER OF MEN\s*:\s*(\d+)", line, re.I)
        if m:
            prior = lines[i - 1] if i else ""
            out.append((int(m.group(1)), f"{prior} {line} {' '.join(lines[i+1:i+5])}"))
            continue
        m = exact_calls.match(line)
        if m:
            j = i + 1
            while j < len(lines) and j < i + 12 and not exact_calls.match(lines[j]) and "POSITION:" not in lines[j].upper():
                j += 1
            out.append((int(m.group(1)), " ".join(lines[i:j])))
            continue

        count = None
        for pat in [
            r"^(\d+)\s*(?:[-–—]|JW\b|JWS\b|JIW\b|REG(?:ULAR)?\b|CALLS?\b)",
            r"[-–—]\s*(\d+)\s+(?:REG(?:ULAR)?\s+)?(?:JW|JIW|JNM|CALLS?|INSIDE|CE|CW)\b",
            r"[-–—]\s*(\d+)\s*[-–—]",
            r"\b(\d+)\s+REGULAR CALLS?\b",
        ]:
            m = re.search(pat, line, re.I)
            if m:
                count = int(m.group(1)); break
        if count is not None:
            out.append((count, line))

    seen, clean = set(), []
    for n, raw in out:
        raw = re.sub(r"\s+", " ", raw).strip()
        key = (n, raw.upper())
        if key not in seen:
            seen.add(key); clean.append((n, raw))
    return clean


def parse_calls(text: str, observed: datetime, cfg: dict) -> list[Call]:
    rows: list[Call] = []
    for local, city_label, mmdd, segment in segments(text):
        market = cfg.get("locals", {}).get(str(local), {}).get("market", city_label.title())
        source_date = parse_source_date(mmdd, observed)
        for openings, raw in call_records(segment):
            conf = dc_confidence(raw)
            if conf < 0.75:
                continue
            hours = parse_weekly_hours(raw)
            base, incentive, per_diem = parse_money(raw)
            ot = parse_ot(raw)
            rows.append(Call(
                observed_at=observed.isoformat(), source_date=source_date, local=local,
                market=market, city_label=city_label.title(), project=project_for(raw),
                openings=openings, weekly_hours=hours, base_hourly=base,
                incentive_hourly=incentive, per_diem_daily=per_diem, ot_multiplier=ot,
                confidence=conf, stress_score=stress_score(openings, hours, incentive, per_diem, ot),
                source_url=SOURCE_URL, source_text=raw[:1200],
            ))
    return rows


def append_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def active_snapshot_rows(calls: list[dict]) -> list[dict]:
    # If a source edits a local without changing its printed source date, use the latest scrape only.
    latest: dict[tuple[str, str], str] = {}
    for r in calls:
        key = (r["market"], r["source_date"])
        latest[key] = max(latest.get(key, ""), r["observed_at"])
    return [r for r in calls if r["observed_at"] == latest[(r["market"], r["source_date"])]]


def build_dashboard(cfg: dict) -> dict:
    calls = active_snapshot_rows(read_csv(DATA_DIR / "calls.csv"))
    if not calls:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE_URL, "markets": [], "history": [], "drops": []}
    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in calls:
        grouped.setdefault((r["market"], r["source_date"]), []).append(r)
    history = []
    for (market, date), rows in sorted(grouped.items()):
        openings = sum(int(float(r["openings"])) for r in rows)
        weighted = sum(float(r["stress_score"]) * int(float(r["openings"])) for r in rows)
        history.append({"market": market, "date": date, "openings": openings,
                        "intensity": round(weighted / openings, 1) if openings else 0.0})
    latest_by_market: dict[str, dict] = {}
    for h in history:
        if h["market"] not in latest_by_market or h["date"] > latest_by_market[h["market"]]["date"]:
            latest_by_market[h["market"]] = h
    markets = []
    for market, latest in latest_by_market.items():
        meta = cfg.get("markets", {}).get(market, {})
        projects: dict[str, int] = {}
        for r in grouped[(market, latest["date"])]:
            projects[r["project"]] = projects.get(r["project"], 0) + int(float(r["openings"]))
        markets.append({**latest, "lat": meta.get("lat"), "lon": meta.get("lon"), "state": meta.get("state"),
                        "projects": [{"project": k, "openings": v} for k, v in sorted(projects.items(), key=lambda x: -x[1])]})
    markets.sort(key=lambda r: (-r["intensity"], -r["openings"]))
    drops = []
    per_market: dict[str, list[dict]] = {}
    for h in history:
        per_market.setdefault(h["market"], []).append(h)
    for market, rows in per_market.items():
        rows.sort(key=lambda r: r["date"])
        if len(rows) < 2:
            continue
        prev, cur = rows[-2], rows[-1]
        if prev["openings"] >= 5:
            change = (cur["openings"] - prev["openings"]) / prev["openings"]
            if change <= -0.5:
                drops.append({"market": market, "from_date": prev["date"], "to_date": cur["date"],
                              "from_openings": prev["openings"], "to_openings": cur["openings"],
                              "change_pct": round(change * 100, 1),
                              "flag": "Potential deceleration — verify direct local board / project phase"})
    drops.sort(key=lambda x: x["change_pct"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE_URL,
        "methodology": {
            "scope": "Explicitly identifiable data-center-related electrician calls only; conservative by design.",
            "stress_score": "0–100 composite of openings, weekly hours, explicit hourly incentive, OT multiplier and per diem.",
            "warning": "A drop in open calls can mean hiring filled, project phase change, reporting change, or true construction deceleration."
        },
        "markets": markets, "history": history, "drops": drops,
    }


def main() -> int:
    observed = datetime.now(timezone.utc)
    cfg = load_config()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(SOURCE_URL, timeout=30, headers={"User-Agent": UA})
    response.raise_for_status()
    body = response.text
    digest = hashlib.sha256(body.encode()).hexdigest()
    hash_path = DATA_DIR / "last_hash.txt"
    calls_path = DATA_DIR / "calls.csv"
    old_hash = hash_path.read_text().strip() if hash_path.exists() else ""
    changed = digest != old_hash
    needs_parse = changed or not calls_path.exists()
    if changed:
        stamp = observed.strftime("%Y%m%dT%H%M%SZ")
        (RAW_DIR / f"{stamp}_where2bro_hot_spots.html").write_text(body, encoding="utf-8")
        hash_path.write_text(digest + "\n", encoding="utf-8")
    parsed = 0
    if needs_parse:
        parser = TextExtractor(); parser.feed(body)
        rows = parse_calls(parser.text(), observed, cfg)
        parsed = len(rows)
        if rows:
            append_csv(calls_path, [asdict(x) for x in rows], list(asdict(rows[0]).keys()))
    dashboard = build_dashboard(cfg)
    payload = json.dumps(dashboard, indent=2)
    (DATA_DIR / "latest.json").write_text(payload, encoding="utf-8")
    (DOCS_DIR / "data.json").write_text(payload, encoding="utf-8")
    print(json.dumps({"changed": changed, "parsed_calls": parsed, "markets": len(dashboard.get("markets", [])),
                      "history_rows": len(dashboard.get("history", [])), "drops": len(dashboard.get("drops", []))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
