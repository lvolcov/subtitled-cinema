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
# Whole-UK coverage. yourlocalcinema.com publishes one page per town where it has
# data; each page lists every accessible screening within a radius, so the pages
# overlap heavily and are merged/deduped downstream. This is the full set of town
# pages (derived from YLC's own store-locator feed — see build/discover_towns.py),
# so between them they reach essentially every subtitling cinema in the UK. Pages
# with no current subtitled shows simply contribute nothing until they do.
CITIES = [
    "aberdeen", "aberystwyth", "accrington", "acton", "altrincham", "ashton",
    "aylesbury", "ayr", "banbury", "barnstable", "basingstoke", "bath",
    "beckenham", "berwick", "birmingham", "blackpool", "bolton", "bournemouth",
    "bracknell", "bradford", "braintree", "brentford", "bridgend", "brighton",
    "bristol", "brixton", "bromborough", "bury", "cambridge", "canterbury",
    "cardiff", "carlisle", "carmarthen", "castleford", "chelmsford", "chelsea",
    "cheltenham", "chesterfield", "chichester", "cleethorpes", "clevedon", "colchester",
    "cornwall", "coventry", "crawley", "crewe", "crouchend", "croydon",
    "dagenham", "darlington", "derby", "didsbury", "doncaster", "dudley",
    "dumfries", "dundee", "dunfermline", "eastbourne", "edinburgh", "enfield",
    "epsom", "exeter", "falkirk", "feltham", "finchley", "fulham",
    "glasgow", "greenwich", "guildford", "harrogate", "harrow", "hartlepool",
    "hastings", "hatfield", "hereford", "horsham", "huddersfield", "hull",
    "huntingdon", "inverness", "ipswich", "ireland", "isleofman", "islington",
    "jersey", "kettering", "kilmarnock", "kingston", "leeds", "leicester",
    "lincoln", "liverpool", "livingston", "llandudno", "luton", "maidenhead",
    "maidstone", "manchester", "mansfield", "middlesbrough", "morecambe", "newcastle",
    "northampton", "norwich", "nottingham", "orkney", "oxford", "peckham",
    "perth", "plymouth", "portsmouth", "preston", "reading", "redditch",
    "reigate", "rugby", "salisbury", "scunthorpe", "sheffield", "shetland",
    "shrewsbury", "southampton", "southend", "southport", "staines", "stevenage",
    "stirling", "stockport", "stoke", "stratford", "sunderland", "swansea",
    "swindon", "tamworth", "taunton", "telford", "thurrock", "torbay",
    "tunbridge", "uxbridge", "walsall", "wandsworth", "warrington", "waterloo",
    "watford", "weston", "weymouth", "wimbledon", "woking", "wolverhampton",
    "worcester", "workington", "wrexham", "yeovil", "york",
]
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
