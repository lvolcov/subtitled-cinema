"""
geocode_name.py — last-resort coordinates by geocoding a venue's *name*.

Some venues get no coordinate from the hand-curated list, the YLC locator feed
(coords_feed.py), or a postcode (geocode.py) — usually because the feed spells
the name too differently to match, or the page lists no postcode. For those we
ask OpenStreetMap's **Nominatim** geocoder, which understands place/venue names
("Odeon Luxe Acton", "Barbican Centre", "Alnwick Playhouse"). We try the full
name, then "<name> cinema", then fall back to the town (the venue's `area`) so we
at least land in the right place for "nearest".

Nominatim's usage policy: <=1 request/second and a real User-Agent — respected
here (results are cached in build/geo_name_cache.json, negatives too, so a warm
build makes zero calls). Restricted to GB and sanity-checked to UK bounds.

Warm/refresh the cache:  python3 -m build.geocode_name
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "geo_name_cache.json"
API = "https://nominatim.openstreetmap.org/search?"
UA = "subtitled-cinema/1.0 (cinema geocoder; +https://github.com/lvolcov/subtitled-cinema; volcovlucas@gmail.com)"
UK_BOUNDS = (49.0, 61.5, -9.0, 2.1)   # min_lat, max_lat, min_lng, max_lng


def _query(q: str):
    url = API + urllib.parse.urlencode({
        "q": q, "format": "json", "limit": 1, "countrycodes": "gb", "addressdetails": 0,
    })
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None
    if not data:
        return None
    try:
        lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
    except (KeyError, ValueError, IndexError):
        return None
    min_lat, max_lat, min_lng, max_lng = UK_BOUNDS
    if not (min_lat < lat < max_lat and min_lng < lng < max_lng):
        return None
    return [round(lat, 5), round(lng, 5)]


# hand-picked coordinates for venues Nominatim can't place from their name
# (odd/ambiguous names, or a source typo) — researched individually.
OVERRIDES = {
    "Brighton Duke of Yorks Picturehouse": [50.8353, -0.1379],   # Preston Circus
    "Colywn": [53.2932, -3.7276],                                # Colwyn Bay (source typo)
    "Shetland Vue": [60.1547, -1.1490],                          # Mareel, Lerwick
    "Sidcup Castle": [51.4260, 0.1027],                          # Sidcup, Bexley
    "Derby QUAD Cathedral Quarter": [52.9232, -1.4755],          # QUAD, Market Place
    "Edinburgh West Luxe Odeon": [55.9413, -3.2096],             # Odeon Luxe, Fountain Park
    "Huntingdon Odeon": [52.3305, -0.1843],                      # Odeon Huntingdon
    "Middlesbrough Everyman": [54.5745, -1.2350],                # Everyman, Captain Cook Sq
    "Stirling Macroberts Arts Centre Stirling University Complex": [56.1456, -3.9197],  # Macrobert, Univ. of Stirling
}


def _brand_first(name: str) -> str:
    """"Middlesbrough Everyman" -> "Everyman Middlesbrough" (our names are
    Area-Brand; Nominatim usually indexes Brand-Area)."""
    words = name.split()
    return f"{words[-1]} {' '.join(words[:-1])}" if len(words) > 1 else name


def _resolve_one(name: str, area: str | None, throttle: float):
    if name in OVERRIDES:
        return OVERRIDES[name]
    seen = []
    for q in (name, _brand_first(name), f"{name} cinema", area, f"{area}, UK" if area else None):
        if not q or q in seen:
            continue
        seen.append(q)
        hit = _query(q)
        time.sleep(throttle)          # Nominatim: <=1 req/sec
        if hit:
            return hit
    return None


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve(venues, cache=None, throttle=1.1) -> dict:
    """venues: iterable of (name, area). Returns {name: [lat,lng] or None}."""
    cache = cache if cache is not None else load_cache()
    changed = False
    for name, area in venues:
        if name in cache:
            continue
        cache[name] = _resolve_one(name, area, throttle)
        changed = True
    if changed:
        save_cache(cache)
    return cache


def main() -> int:
    from .build_site import build
    data = build()
    want = [(c["name"], c.get("area")) for c in data["cinemas"] if not c.get("lat")]
    cache = resolve(want)
    have = sum(1 for n, _ in want if cache.get(n))
    print(f"Name-geocoded {have}/{len(want)} venues that had no coordinate")
    for n, _ in want:
        print(f"  {n:<48} {cache.get(n) or '— (none)'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
