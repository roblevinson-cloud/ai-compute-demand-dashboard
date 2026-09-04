from pathlib import Path

INDEX = Path("docs/index.html")
MARKER = 'href="./labor/"'
LINK = '<a class="module-tab" href="./labor/" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center;">Electrician labor ↗</a>'


def main() -> int:
    if not INDEX.exists():
        raise FileNotFoundError(INDEX)
    text = INDEX.read_text(encoding="utf-8")
    if MARKER in text:
        return 0
    needle = "    </nav>"
    if needle not in text:
        raise RuntimeError("dashboard module navigation not found")
    text = text.replace(needle, f"      {LINK}\n{needle}", 1)
    INDEX.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
