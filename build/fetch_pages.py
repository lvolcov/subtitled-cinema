"""
fetch_pages.py — download the source city pages into .cache/pages/.

In production this runs first in CI so the build works from fresh listings.
Kept deliberately dumb: fetch, save, report. Network failures are surfaced but
never delete an existing cached page (so a bad fetch can't wipe good data).

Run:  python3 -m build.fetch_pages
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / ".cache" / "pages"
CITIES = ["manchester", "stockport", "altrincham", "didsbury"]
BASE = "https://yourlocalcinema.com/{city}.html"
UA = "subtitled-cinema/1.0 (+https://github.com/) build bot"


def fetch(city: str) -> bool:
    url = BASE.format(city=city)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - report, keep old cache
        print(f"  ! {city}: fetch failed ({e}) — keeping cached copy")
        return False
    if len(html) < 2000 or "film-block" not in html and "cinema" not in html:
        print(f"  ! {city}: response looks wrong ({len(html)} bytes) — keeping cached copy")
        return False
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    (PAGES_DIR / f"{city}.html").write_text(html, encoding="utf-8")
    print(f"  ✓ {city}: {len(html)} bytes")
    return True


def main() -> int:
    print("Fetching source pages…")
    ok = sum(fetch(c) for c in CITIES)
    print(f"Fetched {ok}/{len(CITIES)} pages OK")
    # success as long as we have a cached copy for every city (fresh or old)
    have = all((PAGES_DIR / f"{c}.html").exists() for c in CITIES)
    return 0 if have else 1


if __name__ == "__main__":
    sys.exit(main())
