"""
geocode.py — approximate coordinates for a cinema from its postcode, so "nearest"
works nationwide without hand-curating hundreds of venues.

The parser already pulls each venue's *outward* postcode (e.g. "CF10", "NN15").
postcodes.io is a free, key-less UK API that returns the centroid of an outward
code (`/outcodes/CF10`). An outward-code centroid is a district-level point —
plenty accurate for "sort cinemas by distance", not for turn-by-turn — and it is
the honest, automatable complement to the hand-curated coordinates in
cinema_meta.COORDS (which still win when present).

Keyed by outward code, cached in build/geo_cache.json; negatives cached too.
Crown-dependency codes (Jersey/IoM) aren't in postcodes.io and resolve to None.

Warm/refresh the cache:  python3 -m build.geocode
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "geo_cache.json"
API = "https://api.postcodes.io/outcodes/"
UA = "subtitled-cinema/1.0 (geocoder; +https://github.com/lvolcov/subtitled-cinema)"


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def _coord_for_outcode(outcode: str):
    data = _get(API + urllib.parse.quote(outcode))
    if not data or data.get("status") != 200:
        return None
    res = data.get("result") or {}
    lat, lng = res.get("latitude"), res.get("longitude")
    if lat is None or lng is None:
        return None
    return [round(lat, 5), round(lng, 5)]


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve(outcodes, cache=None, throttle=0.4) -> dict:
    """outcodes: iterable of outward codes. Returns {outcode: [lat,lng] or None}."""
    cache = cache if cache is not None else load_cache()
    changed = False
    for oc in outcodes:
        if not oc or oc in cache:
            continue
        cache[oc] = _coord_for_outcode(oc)
        changed = True
        time.sleep(throttle)
    if changed:
        save_cache(cache)
    return cache


def main() -> int:
    from .build_site import build
    data = build()
    want = sorted({c["postcode"] for c in data["cinemas"]
                   if c.get("postcode") and not (c.get("lat") and c.get("lng"))})
    cache = resolve(want)
    have = sum(1 for oc in want if cache.get(oc))
    print(f"Geocoded {have}/{len(want)} outward codes lacking hand-curated coords")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
