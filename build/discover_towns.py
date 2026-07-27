"""
discover_towns.py — regenerate the national town-page list from yourlocalcinema's
own data.

yourlocalcinema.com has no sitemap and its /locations.html is a JS store-locator
widget. That widget loads every YLC cinema (name, coords, and a link to its town
page) from a single JSONP feed. We read that feed, pull out every distinct
`<town>.html` a cinema links to, and print the set — which is the authoritative
list of town pages to fetch. Paste the output into build/fetch_pages.CITIES.

Run:  python3 -m build.discover_towns
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

# The store-locator widget UID is on yourlocalcinema.com/locations.html:
#   <script id="storelocatorscript" data-uid="...">
FEED = "https://cdn.storelocatorwidgets.com/json/c5ecea1f9e61be0b705fd05df9af8898"
UA = "subtitled-cinema/1.0 (town discovery; +https://github.com/lvolcov/subtitled-cinema)"
TOWN_RE = re.compile(r"yourlocalcinema\.com/([a-z0-9\-]+)\.html")
# never real town pages even if a description links to them
SKIP = {"index", "locations", "contact", "explain", "more", "trailers",
        "foreignlanguage", "sponsors", "quote", "disclosureday", "tandc"}


def fetch_feed() -> dict:
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    # the feed is JSONP: slw({...});
    m = re.match(r"\s*slw\((.*)\)\s*;?\s*$", raw, re.S)
    return json.loads(m.group(1) if m else raw)


def discover() -> dict:
    """{town_slug: number_of_cinemas_linking_to_it}, most-populated first."""
    data = fetch_feed()
    counts: dict[str, int] = {}
    for store in data.get("stores", []):
        desc = (store.get("data") or {}).get("description", "")
        for slug in TOWN_RE.findall(desc):
            if slug in SKIP:
                continue
            counts[slug] = counts.get(slug, 0) + 1
    return counts


def main() -> int:
    counts = discover()
    towns = sorted(counts)
    print(f"# {len(towns)} town pages ({sum(counts.values())} cinema links)\n")
    print("CITIES = [")
    for i in range(0, len(towns), 6):
        print("    " + ", ".join(f'"{t}"' for t in towns[i:i + 6]) + ",")
    print("]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
