from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "china-auto"
INDEX = SITE / "index.html"
CURRENT = SITE / "current.html"
HISTORY = SITE / "history.html"


def main():
    if not INDEX.exists() or not CURRENT.exists():
        raise SystemExit("China auto frontend files are missing")

    # Preserve the original full China-reported historical dashboard exactly once.
    if not HISTORY.exists():
        HISTORY.write_text(INDEX.read_text(encoding="utf-8"), encoding="utf-8")
        print("Preserved historical dashboard at docs/china-auto/history.html")

    current = CURRENT.read_text(encoding="utf-8")
    current = current.replace(
        'href="./">Verified 2020–2024 History',
        'href="history.html">Verified 2020–2024 History',
    )
    CURRENT.write_text(current, encoding="utf-8")
    INDEX.write_text(current, encoding="utf-8")
    print("Promoted current pulse dashboard to docs/china-auto/index.html")


if __name__ == "__main__":
    main()
