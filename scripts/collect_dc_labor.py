from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "dc_labor"
RAW_DIR = DATA_DIR / "raw"
DOCS_DIR = ROOT / "docs" / "labor"
CONFIG_PATH = ROOT / "config" / "dc_labor_markets.json"
SOURCE_URL = "https://where2bro.com/hot-spots/"
UA = "ai-compute-demand-dashboard/1.0 (+https://github.com/roblevinson-cloud/ai-compute-demand-dashboard)"

DC_TERMS = {
    "DATA CENTER": 1.0, "DATACENTER": 1.0, "QTS": 0.95, "EQUINIX": 0.95,
    "DATABANK": 0.95, "MICROSOFT": 0.9, "META": 0.9, "FACEBOOK": 0.9,
    "EDGECORE": 0.95, "VANTAGE": 0.95, "SWITCH": 0.9, "GOOGLE": 0.85,
    "COMPASS": 0.95, "EDGED DATA": 0.95, "PROJECT MINER": 0.98,
    "PROJECT SPADE": 0.98, "BIGHORN": 0.8, "RNO1": 0.8, "RNO 2": 0.8,
    "STY CAMPUS": 0.75,
}

PROJECT_RULES = [
    (r"PROJECT MINER", "Project Miner / Santa Teresa"),
    (r"META EL PASO|VFC META", "Meta El Paso"),
    (r"QTS(?: EAST CAMPUS| DATA CENTER| FAYETTE)?", "QTS"),
    (r"EWD DATA CENTER", "EWD Data Center"),
    (r"MICROSOFT", "Microsoft"), (r"EDGECORE|RNO1", "EdgeCore"),
    (r"VANTAGE", "Vantage"), (r"BIGHORN DATA CENTER", "Bighorn Data Center"),
    (r"PROJECT SPADE", "Google Project Spade"), (r"GOOGLE", "Google"),
    (r"EQUINIX", "Equinix"), (r"DATABANK", "DataBank"),
    (r"SWITCH DATA CENTER|SWITCH", "Switch"), (r"EDGED DATA", "Edged Data Center"),
    (r"ALIGNED", "Aligned"),
]


class TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "section", "article"}

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
        raw = html.unescape("".join(self.parts)).replace("\xa0", " ")
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


def market_for(local: str, city_label: str, cfg: dict) -> tuple[str, dict]:
    info = cfg.get("locals", {}).get(str(local), {})
    return info.get("market", city_label.title()), info


def project_for(text: str) -> str:
    up = text.upper()
    for pattern, name in PROJECT_RULES:
        if re.search(pattern, up):
            return name
    return "Unclassified data center"


def dc_confidence(text: str) -> float:
    up = text.upper()
    scores = [score for term, score in DC_TERMS.items() if term in up]
    return max(scores, default=0.0)


def parse_weekly_hours(text: str) -> float | None:
    t = text.upper().replace("’", "'").replace("×", "X")
    m = re.search(r"(\d{2})\s*,\s*(\d{2})\s*,\s*(\d{2})\s*/?\s*HR", t)
    if m:
        return round(sum(map(int, m.groups())) / 3, 1)
    m = re.search(r"(\d)\s*[-/X]\s*(8|9|10|12)\s*'?S", t)
    if m:
        return float(int(m.group(1)) * int(m.group(2)))
    m = re.search(r"WORKING\s*\(?(\d)\)?\s*(8|9|10|12)S", t)
    if m:
        return float(int(m.group(1)) * int(m.group(2)))
    m = re.search(r"(\d{2})\s*(?:HR|HRS)\s*(?:PER|/)\s*W", t)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{2})\s*HRS?\+?/?WEEK", t)
    if m:
        return float(m.group(1))
    return None


def parse_money(text: str) -> tuple[float | None, float | None, float | None]:
    t = text.upper().replace(",", "")
    base = incentive = per_diem = None
    m = re.search(r"\$(\d+(?:\.\d+)?)\s*/?\s*(?:HR|HOUR)", t)
    if m:
        base = float(m.group(1))
    m = re.search(r"\$(\d+(?:\.\d+)?)\s*(?:/HR|/HOUR)?\s*(?:INCENTIVE|OVER SCALE|OVERSCALE)", t)
    if m:
        incentive = float(m.group(1))
    else:
        m = re.search(r"(?:PAYING|RATE\s*[-:]?)\s*\$(\d+(?:\.\d+)?)\s*(?:/HR|/HOUR)?\s*OVER", t)
        if m:
            incentive = float(m.group(1))
    m = re.search(r"\$(\d+(?:\.\d+)?)\s*(?:A|PER)\s*DAY\s*(?:PER\s*DIEM|PERDIEM|INCENTIVE)", t)
    if m:
        per_diem = float(m.group(1))
    return base, incentive, per_diem


def parse_ot(text: str) -> float | None:
    t = text.upper()
    if "DOUBLE TIME" in t or "ALL OT IS DT" in t or "ALL O/T PAID DOUBLE" in t:
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


def parse_source_date(mmdd: str, observed: datetime) -> str:
    month, day = map(int, mmdd.split("-"))
    year = observed.year
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    if (observed - dt).days > 180:
        year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def segments(text: str) -> Iterable[tuple[str, str, str, str]]:
    header = re.compile(r"(?m)^LU-?(\d+)\s+(.+?)\s+\((\d{1,2}-\d{1,2})\)\s*$")
    matches = list(header.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield m.group(1), m.group(2).strip(), m.group(3), text[m.end():end].strip()


def call_blocks(segment_text: str) -> list[tuple[int, str]]:
    lines = [x.strip() for x in segment_text.splitlines() if x.strip()]
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(\d+)\s*(?:JW|JWS|JIW|REG|[-–—])\b", line, re.I) or re.match(r"^(\d+)\s*[-–—]\s+", line)
        if m:
            out.append((int(m.group(1)), " ".join(lines[i:i+2])))
        m2 = re.search(r"POSITION:\s*(\d+)\s+OPEN\b", line, re.I)
        if m2:
            prior = lines[max(0, i-1)] if i else ""
            out.append((int(m2.group(1)), f"{prior} {line} {' '.join(lines[i+1:i+3])}"))
        m3 = re.search(r"NUMBER OF MEN:\s*(\d+)", line, re.I)
        if m3:
            out.append((int(m3.group(1)), " ".join(lines[max(0, i-1):i+4])))
    seen, dedup = set(), []
    for n, txt in out:
        key = (n, re.sub(r"\s+", " ", txt.upper()))
        if key not in seen:
            seen.add(key)
            dedup.append((n, txt))
    return dedup


def parse_calls(text: str, observed: datetime, cfg: dict) -> list[Call]:
    rows: list[Call] = []
    for local, city_label, mmdd, seg in segments(text):
        market, _ = market_for(local, city_label, cfg)
        source_date = parse_source_date(mmdd, observed)
        for openings, raw in call_blocks(seg):
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
                source_url=SOURCE_URL, source_text=re.sub(r"\s+", " ", raw)[:900],
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


def build_dashboard(cfg: dict) -> dict:
    calls = read_csv(DATA_DIR / "calls.csv")
    if not calls:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "markets": [], "history": [], "drops": []}
    uniq = {}
    for row in calls:
        fp = (row["source_date"], row["local"], row["project"], row["source_text"])
        uniq[fp] = row
    calls = list(uniq.values())
    by_market_date: dict[tuple[str, str], list[dict]] = {}
    for row in calls:
        by_market_date.setdefault((row["market"], row["source_date"]), []).append(row)
    history = []
    for (market, date), rows in sorted(by_market_date.items()):
        openings = sum(int(float(r["openings"])) for r in rows)
        weighted = sum(float(r["stress_score"]) * int(float(r["openings"])) for r in rows)
        intensity = round(weighted / openings, 1) if openings else 0.0
        history.append({"market": market, "date": date, "openings": openings, "intensity": intensity})
    latest_by_market = {}
    for row in history:
        if row["market"] not in latest_by_market or row["date"] > latest_by_market[row["market"]]["date"]:
            latest_by_market[row["market"]] = row
    markets = []
    market_lookup = cfg.get("markets", {})
    for market, latest in latest_by_market.items():
        meta = market_lookup.get(market, {})
        projects = {}
        for r in calls:
            if r["market"] == market and r["source_date"] == latest["date"]:
                projects[r["project"]] = projects.get(r["project"], 0) + int(float(r["openings"]))
        markets.append({**latest, "lat": meta.get("lat"), "lon": meta.get("lon"), "state": meta.get("state"),
                        "projects": [{"project": k, "openings": v} for k, v in sorted(projects.items(), key=lambda x: -x[1])]})
    markets.sort(key=lambda r: (-r["intensity"], -r["openings"]))
    drops = []
    per_market = {}
    for row in history:
        per_market.setdefault(row["market"], []).append(row)
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
                              "flag": "Potential deceleration — verify against direct local board / project phase"})
    drops.sort(key=lambda x: x["change_pct"])
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE_URL,
            "methodology": {"scope": "Explicitly identifiable data-center-related electrician calls only.",
                            "stress_score": "0–100 composite of openings, weekly hours, explicit hourly incentive, OT multiplier and per diem.",
                            "warning": "A drop in open calls can mean hiring filled, project phase change, reporting change, or true construction deceleration."},
            "markets": markets, "history": history, "drops": drops}


def main() -> int:
    observed = datetime.now(timezone.utc)
    cfg = load_config()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    r = requests.get(SOURCE_URL, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    body = r.text
    digest = hashlib.sha256(body.encode()).hexdigest()
    hash_path = DATA_DIR / "last_hash.txt"
    old_hash = hash_path.read_text().strip() if hash_path.exists() else ""
    if digest != old_hash:
        stamp = observed.strftime("%Y%m%dT%H%M%SZ")
        (RAW_DIR / f"{stamp}_where2bro_hot_spots.html").write_text(body, encoding="utf-8")
        hash_path.write_text(digest + "\n", encoding="utf-8")
        parser = TextExtractor()
        parser.feed(body)
        rows = parse_calls(parser.text(), observed, cfg)
        if rows:
            append_csv(DATA_DIR / "calls.csv", [asdict(x) for x in rows], list(asdict(rows[0]).keys()))
    dashboard = build_dashboard(cfg)
    (DOCS_DIR / "data.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    (DATA_DIR / "latest.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    print(json.dumps({"changed": digest != old_hash, "markets": len(dashboard.get("markets", [])),
                      "history_rows": len(dashboard.get("history", [])), "drops": len(dashboard.get("drops", []))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
