#!/usr/bin/env python3
"""Pull Data Center Dynamics RSS and append relevant tracked-project stories.

The matcher is deliberately conservative: a project/campus-name match is enough,
otherwise multiple weaker signals (developer, tenant, location) are required.
Manual aliases cover tracked projects that are not yet represented in the core
project JSON files.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dcd_monitor.json"

GENERIC = {
    "data center", "data centers", "data centre", "data centres", "project",
    "campus", "undisclosed ig hyperscaler", "undisclosed high ig hyperscaler",
    "investment grade hyperscaler", "high investment grade hyperscaler",
    "project level", "special purpose reno developer", "grid",
}
BROAD_TENANTS = {"google", "oracle", "meta", "microsoft", "amazon", "aws", "openai"}


def normalize(value: str) -> str:
    value = html.unescape(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def split_orgs(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*(?:/|\+|;|\||\band\b)\s*", value, flags=re.I)
    out: list[str] = []
    for part in parts:
        part = re.sub(r"\b(?:JV|HoldCo|SPV|LLC|Inc\.?|Corp\.?|Corporation)\b", " ", part, flags=re.I)
        part = normalize(part)
        if len(part) >= 4 and part not in GENERIC:
            out.append(part)
    return out


def add_alias(target: dict[str, Any], alias: str, weight: int, kind: str) -> None:
    alias = normalize(alias)
    if len(alias) < 4 or alias in GENERIC:
        return
    current = target["aliases"].get(alias)
    if current is None or weight > current[0]:
        target["aliases"][alias] = (weight, kind)


def load_targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for rel_path in config["project_files"]:
        path = ROOT / rel_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        for p in payload.get("projects", []):
            name = p.get("name") or p.get("campus") or p.get("slug")
            if not name:
                continue
            key = normalize(str(name))
            target = targets.setdefault(key, {"name": str(name), "aliases": {}})
            for field in ("name", "campus"):
                if p.get(field):
                    add_alias(target, str(p[field]), 4, "primary")
            if p.get("slug"):
                add_alias(target, str(p["slug"]).replace("-", " "), 4, "primary")
            location = str(p.get("location") or "")
            if location:
                parts = [normalize(x) for x in location.split(",") if normalize(x)]
                if parts:
                    add_alias(target, parts[0], 2, "location")
                if len(parts) >= 2 and len(parts[1]) > 3:
                    add_alias(target, parts[1], 2, "location")
            for field in ("developer", "landlord"):
                for org in split_orgs(str(p.get(field) or "")):
                    add_alias(target, org, 3, "developer")
            for field in ("tenant", "guarantor"):
                for org in split_orgs(str(p.get(field) or "")):
                    add_alias(target, org, 1 if org in BROAD_TENANTS else 2, "tenant")

    for manual in config.get("manual_targets", []):
        name = str(manual["name"])
        key = normalize(name)
        target = targets.setdefault(key, {"name": name, "aliases": {}})
        for alias in manual.get("aliases", []):
            a = normalize(str(alias))
            if a == key or a.startswith("project "):
                weight, kind = 4, "primary"
            elif any(x in a for x in ("county", "bluffs", "city", "parish")):
                weight, kind = 3, "location"
            else:
                weight, kind = 2, "developer"
            add_alias(target, a, weight, kind)
    return list(targets.values())


def match_target(text: str, targets: list[dict[str, Any]]) -> tuple[str | None, int, list[str]]:
    norm = normalize(text)
    best: tuple[str | None, int, list[str]] = (None, 0, [])
    for target in targets:
        score = 0
        hits: list[str] = []
        has_primary = False
        for alias, (weight, kind) in target["aliases"].items():
            if re.search(rf"\b{re.escape(alias)}\b", norm):
                score += int(weight)
                hits.append(alias)
                has_primary = has_primary or kind == "primary"
        qualifies = score >= 4 and (has_primary or len(set(hits)) >= 2)
        if qualifies and score > best[1]:
            best = (target["name"], score, hits)
    return best


def classify(headline: str) -> str:
    h = normalize(headline)
    rules = [
        ("CONSTRUCTION", ("tops out", "topped out", "groundbreak", "construction", "builds", "building", "campus")),
        ("POWER", ("power", "substation", "transmission", "grid", "gw", "megawatt", "mw")),
        ("FINANCING", ("financing", "debt", "loan", "bond", "funding", "raises", "billion")),
        ("PERMIT", ("permit", "approval", "planning", "zoning", "regulator", "green light")),
        ("TENANT", ("lease", "tenant", "prelease", "pre leased", "contract")),
        ("OPERATIONS", ("live", "operational", "ready for service", "commission")),
        ("DEVELOPMENT", ("data center", "data centre", "expansion", "develop")),
    ]
    for tag, terms in rules:
        if any(term in h for term in terms):
            return tag
    return "PROJECT UPDATE"


def parse_date(value: str) -> str:
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def fetch_rss(url: str) -> list[dict[str, str]]:
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "ai-compute-demand-dashboard/1.0 DCD project monitor"},
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items: list[dict[str, str]] = []
    for node in root.findall(".//item"):
        title = clean_html(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        description = clean_html(node.findtext("description") or "")
        pub_date = (node.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "description": description, "pub_date": pub_date})
    return items


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    news_path = ROOT / config["news_path"]
    news = json.loads(news_path.read_text())
    targets = load_targets(config)
    existing_urls = {str(item.get("url", "")).rstrip("/") for item in news.get("items", [])}
    added = 0

    for item in fetch_rss(config["rss_url"]):
        canonical_url = item["link"].split("?", 1)[0].rstrip("/")
        if canonical_url in existing_urls:
            continue
        target, score, hits = match_target(f"{item['title']} {item['description']}", targets)
        if not target:
            continue
        tag = classify(item["title"])
        news["items"].append({
            "date": parse_date(item["pub_date"]),
            "source": "Data Center Dynamics",
            "tag": f"{tag} / {target.upper()}",
            "headline": item["title"],
            "url": item["link"],
            "matched_project": target,
            "match_score": score,
            "match_terms": hits,
        })
        existing_urls.add(canonical_url)
        added += 1

    if added:
        news["items"] = sorted(
            news["items"],
            key=lambda x: (str(x.get("date", "")), str(x.get("headline", ""))),
            reverse=True,
        )[: int(config.get("max_items", 150))]
        news["as_of"] = datetime.now(timezone.utc).date().isoformat()
        news_path.write_text(json.dumps(news, indent=2, ensure_ascii=False) + "\n")

    print(f"DCD monitor: {len(targets)} targets, {added} new matching stories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
