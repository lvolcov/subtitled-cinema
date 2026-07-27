"""
posters_wiki.py — title-based poster fallback via Wikipedia.

Some films reach us through a *shared* yourlocalcinema page (foreignlanguage.html,
ntlive.html) that has no per-film artwork, so `posters.py` correctly resolves them
to None. This module fills those gaps by looking the film up on Wikipedia and
taking its infobox poster (PageImages, `pilicense=any` so non-free posters are
included). Keyed by film_id, cached in build/poster_wiki_cache.json; negatives are
cached too. Network failures never drop a cached value. Overrides win over search
so generic titles (e.g. "Girlfriends") can't grab the wrong film's poster.

Warm/refresh the cache:  python3 -m build.posters_wiki
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "poster_wiki_cache.json"
API = "https://en.wikipedia.org/w/api.php?"
UA = "subtitled-cinema/1.0 (poster resolver; +https://github.com/lvolcov/subtitled-cinema)"

# film_id -> a Wikipedia page TITLE to force, a direct image URL, or None to skip.
# Curated for the known shared-page films so generic titles don't mismatch.
OVERRIDES: dict[str, str | None] = {
    # verified-correct posters
    "nostalghia": "https://upload.wikimedia.org/wikipedia/en/2/28/Nostalghia_1983_Italian_poster.jpeg",
    "portrait-of-a-lady-on-fire": "https://upload.wikimedia.org/wikipedia/en/c/cb/Portrait_of_a_Lady_on_Fire.jpg",
    "kikis-delivery-service": "https://upload.wikimedia.org/wikipedia/en/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg",
    "angels-egg": "https://upload.wikimedia.org/wikipedia/en/2/21/AngelsEgg1985.jpg",
    # a theatre broadcast, not a film — no poster, keep the gradient fallback
    "national-theatre-live-the-misanthrope": None,
    # generic title, ambiguous on English Wikipedia — don't risk the wrong film
    "girlfriends": None,
}


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def _pageimage_for_title(title: str) -> str | None:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "redirects": 1,
        "titles": title, "prop": "pageimages",
        "piprop": "original|thumbnail", "pithumbsize": 500, "pilicense": "any",
    })
    data = _get(API + q)
    if not data:
        return None
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        img = (p.get("original") or p.get("thumbnail") or {}).get("source")
        if img:
            return img
    return None


def _search_poster(title: str) -> str | None:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "redirects": 1,
        "generator": "search", "gsrsearch": f"{title} film", "gsrlimit": 1,
        "prop": "pageimages", "piprop": "original|thumbnail",
        "pithumbsize": 500, "pilicense": "any",
    })
    data = _get(API + q)
    if not data:
        return None
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    p = list(pages.values())[0]
    return (p.get("original") or p.get("thumbnail") or {}).get("source")


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve(films, cache=None, throttle=1.1) -> dict:
    """films: iterable of (film_id, title). Returns {film_id: url_or_None}."""
    cache = cache if cache is not None else load_cache()
    changed = False
    for fid, title in films:
        if fid in cache:
            continue
        if fid in OVERRIDES:
            ov = OVERRIDES[fid]
            # an override that names a Wikipedia page title -> resolve it; a URL or
            # None is stored as-is.
            cache[fid] = _pageimage_for_title(ov) if (ov and not ov.startswith("http")) else ov
            changed = True
            time.sleep(throttle)
            continue
        cache[fid] = _search_poster(title)
        changed = True
        time.sleep(throttle)
    if changed:
        save_cache(cache)
    return cache


def main() -> int:
    from .build_site import build
    data = build()
    # only bother resolving films that still lack a poster after YLC extraction
    want = [(f["id"], f["title"]) for f in data["films"] if not f.get("poster_url")]
    cache = resolve(want)
    have = sum(1 for fid, _ in want if cache.get(fid))
    print(f"Wiki posters: filled {have}/{len(want)} previously-blank films")
    for fid, _ in want:
        print(f"  {fid:<40} {cache.get(fid) or '— (none)'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
