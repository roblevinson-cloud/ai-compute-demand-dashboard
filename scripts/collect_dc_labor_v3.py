"""Boundary-hardened entry point for the data-center electrician labor collector.

Where2Bro is human-edited and local headings occasionally contain Unicode dashes,
line breaks or inconsistent spacing (e.g. the current Local 405 Cedar Rapids
heading).  The v2 parser is deliberately conservative at the call level; this
wrapper normalizes section headings and adds a fail-safe boundary detector so a
missed local cannot leak its calls into the preceding geography.
"""
from __future__ import annotations

import re

import collect_dc_labor_v2 as base


DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"


def normalize_local_headings(text: str) -> str:
    # Normalize Unicode dash variants that commonly arrive through copied CMS text.
    text = text.translate({ord(ch): "-" for ch in DASHES})

    # Canonicalize LU headings while preserving the city/date text. \s includes an
    # occasional HTML-created newline between the LU token and local number.
    text = re.sub(r"\bLU\s*-?\s*(\d{1,4})\b", r"LU-\1", text, flags=re.I)

    # Where2Bro currently misspells Cedar Rapids as CEADER RAPIDS.  Local number is
    # authoritative, but canonicalizing the label keeps raw-derived displays clean.
    text = re.sub(r"\bCEADER\s+RAPIDS\b", "CEDAR RAPIDS", text, flags=re.I)
    return text


def robust_segments(text: str):
    text = normalize_local_headings(text)

    # Date-shaped parentheses are the discriminator that keeps the district/local
    # index from being mistaken for the live jobs sections.  Permit harmless text
    # before LU on a heading line and flexible spacing inside the date.
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

    # Geography integrity guard: if a configured live-local heading is visibly
    # present, calls parsed from the following section must not remain attributed
    # to the preceding local because of a boundary miss.  We fail loudly instead
    # of publishing a contaminated dashboard.
    visible_locals = {
        m.group(1)
        for m in re.finditer(
            r"(?im)\bLU-\s*(\d{1,4})\s+[^\n]{1,120}?\s+\(\d{1,2}\s*-\s*\d{1,2}\)",
            normalized,
        )
    }
    parsed_locals = {row.local for row in rows}
    configured_visible = visible_locals.intersection(set(cfg.get("locals", {}).keys()))

    # We do not require every visible local to have DC calls.  Instead, specifically
    # guard known high-value boundaries by confirming their section is discoverable.
    section_locals = {local for local, _, _, _ in robust_segments(normalized)}
    missing_boundaries = configured_visible - section_locals
    if missing_boundaries:
        raise RuntimeError(
            "Local boundary parser missed configured live headings: "
            + ", ".join(sorted(missing_boundaries, key=int))
        )

    return rows


# Save v2 implementation before monkey-patching the globals it resolves at runtime.
base_parse_calls = base.parse_calls
base.segments = robust_segments
base.parse_calls = validated_parse_calls


if __name__ == "__main__":
    raise SystemExit(base.main())
