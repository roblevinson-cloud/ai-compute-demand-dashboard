"""Keep old bookmarks on the unified monitor; never overwrite it with old UI."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs/china-auto'
def main():
    if not (SITE/'index.html').exists():raise SystemExit('Unified dashboard missing')
    redirect='<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=./"><title>China Auto Export Monitor</title><p><a href="./">Open the unified monthly monitor</a></p></html>'
    for name in ('current.html','history.html'):(SITE/name).write_text(redirect)
if __name__=='__main__':main()
