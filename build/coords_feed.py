"""
coords_feed.py — real per-venue coordinates from yourlocalcinema's store-locator
feed.

The same JSONP feed that lists YLC's town pages (see discover_towns.py) also
carries a lat/lng for **every** cinema. Those are per-venue points (far better
than a postcode-district centroid), the catch is only the naming: the feed says
"Cineworld Newcastle" where the parser produces "Newcastle Cineworld". Matching on
the **sorted set of significant name tokens** lines them up (Area↔Brand order
stops mattering), and a light fuzzy fallback catches venues with an extra
site/qualifier word ("Odeon Gateshead" ↔ "Gateshead Metro Centre Odeon").

The build stays offline: the *resolver* fetches the feed and caches a
token-set → coord index in build/coords_feed_cache.json; `build_site` matches its
venue names against that cached index at build time. Coordinates are sanity-checked
to UK bounds so the odd bad feed row can't place a cinema in the sea.

Warm/refresh the cache:  python3 -m build.coords_feed
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "coords_feed_cache.json"
FEED = "https://cdn.storelocatorwidgets.com/json/c5ecea1f9e61be0b705fd05df9af8898"
UA = "subtitled-cinema/1.0 (coord resolver; +https://github.com/lvolcov/subtitled-cinema)"

# words that don't help identify a venue (order-independent matching)
STOP = {
    "the", "and", "at", "de", "lux", "cinema", "cinemas", "co", "st", "tyne",
    "wear", "wales", "scotland", "england", "centre", "center", "imax",
    "picturehouse", "picturehouses", "the", "new",
}
# generous UK bounding box (incl. Northern Isles); rejects flipped/garbled rows
UK_BOUNDS = (49.0, 61.5, -9.0, 2.1)   # min_lat, max_lat, min_lng, max_lng


def tokens(name: str) -> frozenset:
    ws = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return frozenset(w for w in ws if w not in STOP and len(w) > 1)


def _key(tok: frozenset) -> str:
    return " ".join(sorted(tok))


def fetch_index() -> dict:
    """{sorted-token-string: [lat,lng]} from the live feed, UK-bounds filtered,
    with ambiguous (same tokens, different coords) keys dropped."""
    req = urllib.request.Request(FEED, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    m = re.match(r"\s*slw\((.*)\)\s*;?\s*$", raw, re.S)
    data = json.loads(m.group(1) if m else raw)
    min_lat, max_lat, min_lng, max_lng = UK_BOUNDS
    index: dict[str, list] = {}
    ambiguous: set[str] = set()
    for store in data.get("stores", []):
        d = store.get("data") or {}
        lat, lng = d.get("map_lat"), d.get("map_lng")
        if lat is None or lng is None:
            continue
        if not (min_lat < lat < max_lat and min_lng < lng < max_lng):
            continue
        tok = tokens(store.get("name", ""))
        if not tok:
            continue
        k = _key(tok)
        coord = [round(lat, 5), round(lng, 5)]
        if k in index and index[k] != coord:
            ambiguous.add(k)
        index[k] = coord
    for k in ambiguous:
        index.pop(k, None)
    return index


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(index: dict) -> None:
    CACHE.write_text(json.dumps(index, indent=0, ensure_ascii=False), encoding="utf-8")


def _as_sets(index: dict):
    """Cache (string keys) -> [(token_frozenset, coord)] for matching."""
    return [(frozenset(k.split()), v) for k, v in index.items()]


def match(name: str, index_sets) -> list | None:
    """Coord for a venue name: exact token-set match, then a conservative fuzzy
    fallback (>=2 shared tokens and Jaccard >= 0.5)."""
    vt = tokens(name)
    if not vt:
        return None
    best, best_score = None, 0.0
    for tok, coord in index_sets:
        if tok == vt:
            return coord
        inter = len(vt & tok)
        if inter < 2:
            continue
        score = inter / len(vt | tok)
        if score > best_score:
            best, best_score = coord, score
    return best if best_score >= 0.5 else None


def main() -> int:
    index = fetch_index()
    save_cache(index)
    print(f"Cached {len(index)} venue coordinates from the YLC store-locator feed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
