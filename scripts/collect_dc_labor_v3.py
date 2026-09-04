"""Boundary- and entity-hardened entry point for the data-center electrician labor collector.

Where2Bro is human-edited and local headings occasionally contain Unicode dashes,
line breaks, nested inline tags or inconsistent spacing. This wrapper normalizes
section headings, uses stricter entity matching, and adds fail-safe boundary checks so
a malformed source page cannot contaminate an adjacent geography.
"""
from __future__ import annotations

import re

import collect_dc_labor_v2 as base


DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"

# Avoid substring errors such as META matching METATARSALS. Distinct operators and
# explicit data-center phrases may qualify a call; generic words are deliberately
# excluded unless paired with data-center context.
DC_PATTERNS = [
    (r"\bDATA\s*CENTERS?\b|\bDATACENTER\b", 1.00),
    (r"\bPROJECT\s+MINER\b|\bPROJECT\s+SPADE\b", 0.99),
    (r"\bQTS\b|\bEQUINIX\b|\bDATABANK\b|\bEDGECORE\b|\bVANTAGE\b", 0.98),
    (r"\bEDGED\s+DATA\b|\bSTREAM\s+DATA\b", 0.98),
    (r"\bMICROSOFT\b|\bMETA\b|\bFACEBOOK\b", 0.92),
    (r"\bGOOGLE\b", 0.90),
    (r"\bSWITCH\s+DATA\s+CENTER\b", 0.95),
    (r"\bBIGHORN\b|\bRNO1\b|\bRNO\s*2\b", 0.88),
    (r"\bSTY\s+CAMPUS\b|\bLMA1\b", 0.80),
]


def strict_dc_confidence(text: str) -> float:
    up = text.upper()
    return max((score for pattern, score in DC_PATTERNS if re.search(pattern, up)), default=0.0)


def normalize_local_headings(text: str) -> str:
    text = text.translate({ord(ch): "-" for ch in DASHES})
    text = re.sub(r"\bLU\s*-?\s*(\d{1,4})\b", r"LU-\1", text, flags=re.I)

    # WordPress sometimes wraps the local number and city in adjacent inline <strong>
    # nodes with no literal whitespace between their text nodes. The retained 2026-09-04
    # snapshot does this for Local 405: "LU-405" + "CEADER RAPIDS...".
    text = re.sub(r"\b(LU-\d{1,4})(?=[A-Z])", r"\1 ", text, flags=re.I)
    text = re.sub(r"\bCEADER\s+RAPIDS\b", "CEDAR RAPIDS", text, flags=re.I)
    return text


def robust_segments(text: str):
    text = normalize_local_headings(text)
    header = re.compile(
        r"(?im)(?:^|\n)[^\n]*?\bLU-\s*(\d{1,4})\s+([^\n]{1,120}?)\s+"
        r"\((\d{1,2}\s*-\s*\d{1,2})\)"
    )
    matches = list(header.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        mmdd = re.sub(r"\s+", "", match.group(3))
        yield match.group(1), match.group(2).strip(), mmdd, text[match.end():end].strip()


def validated_parse_calls(text, observed, cfg):
    normalized = normalize_local_headings(text)
    rows = base_parse_calls(normalized, observed, cfg)

    visible_locals = {
        m.group(1)
        for m in re.finditer(
            r"(?im)\bLU-\s*(\d{1,4})\s+[^\n]{1,120}?\s+\(\d{1,2}\s*-\s*\d{1,2}\)",
            normalized,
        )
    }
    configured_visible = visible_locals.intersection(set(cfg.get("locals", {}).keys()))
    section_locals = {local for local, _, _, _ in robust_segments(normalized)}
    missing_boundaries = configured_visible - section_locals
    if missing_boundaries:
        raise RuntimeError(
            "Local boundary parser missed configured live headings: "
            + ", ".join(sorted(missing_boundaries, key=int))
        )

    if re.search(r"(?im)\bLU-405\s+CEDAR RAPIDS[^\n]*\(\d{1,2}-\d{1,2}\)", normalized):
        if "405" not in section_locals:
            raise RuntimeError("Local 405 Cedar Rapids boundary was not parsed")

    return rows


# Save v2 implementation before monkey-patching globals resolved at runtime.
base_parse_calls = base.parse_calls
base.dc_confidence = strict_dc_confidence
base.segments = robust_segments
base.parse_calls = validated_parse_calls


if __name__ == "__main__":
    raise SystemExit(base.main())
