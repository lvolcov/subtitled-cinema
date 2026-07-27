"""
imdb.py — resolve a real IMDb title id (tt…) for each film, so "IMDb" links go
straight to the film's page instead of a search.

There is no free IMDb API, and IMDb blocks bots. Wikidata is the reliable, free,
key-less bridge: look the film up on Wikipedia to get its Wikidata item, then read
the item's IMDb ID (property P345). This gives an exact tt id we can trust (it's
editorially curated), and we reuse the same override titles as the poster resolver
so generic names ("Girlfriends") don't grab the wrong film.

Keyed by film_id, cached in build/imdb_cache.json; negatives cached too (so we
don't refetch films that genuinely have no Wikidata IMDb id). Network failures
never drop a cached value.

Warm/refresh the cache:  python3 -m build.imdb
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .posters_wiki import OVERRIDES as WIKI_OVERRIDES

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "imdb_cache.json"
WP_API = "https://en.wikipedia.org/w/api.php?"
WD_API = "https://www.wikidata.org/w/api.php?"
UA = "subtitled-cinema/1.0 (imdb id resolver; +https://github.com/lvolcov/subtitled-cinema)"

# film_id -> a forced Wikipedia page TITLE, or None to skip resolution entirely.
# Films that are theatre broadcasts / ambiguous generic titles get pinned here so
# we never link to the wrong tt id. Reuses the poster overrides where those name a
# page title (a poster override that is a direct image URL tells us nothing about
# the article, so it is ignored for id resolution).
OVERRIDES: dict[str, str | None] = {
    fid: (val if (val is None or not val.startswith("http")) else None)
    for fid, val in WIKI_OVERRIDES.items()
}


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def _qid_for_title(title: str) -> str | None:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "redirects": 1,
        "titles": title, "prop": "pageprops", "ppprop": "wikibase_item",
    })
    data = _get(WP_API + q)
    if not data:
        return None
    for p in data.get("query", {}).get("pages", {}).values():
        qid = (p.get("pageprops") or {}).get("wikibase_item")
        if qid:
            return qid
    return None


def _qid_from_search(title: str) -> str | None:
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "redirects": 1,
        "generator": "search", "gsrsearch": f"{title} film", "gsrlimit": 1,
        "prop": "pageprops", "ppprop": "wikibase_item",
    })
    data = _get(WP_API + q)
    if not data:
        return None
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    return (list(pages.values())[0].get("pageprops") or {}).get("wikibase_item")


def _imdb_for_qid(qid: str) -> str | None:
    q = urllib.parse.urlencode({
        "action": "wbgetclaims", "format": "json", "entity": qid, "property": "P345",
    })
    data = _get(WD_API + q)
    if not data:
        return None
    claims = data.get("claims", {}).get("P345") or []
    for c in claims:
        val = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(val, str) and val.startswith("tt"):
            return val
    return None


def _resolve_one(fid: str, title: str) -> str | None:
    if fid in OVERRIDES:
        forced = OVERRIDES[fid]
        if forced is None:
            return None
        qid = _qid_for_title(forced)
    else:
        qid = _qid_for_title(title) or _qid_from_search(title)
    if not qid:
        return None
    return _imdb_for_qid(qid)


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
    """films: iterable of (film_id, title). Returns {film_id: 'tt…' or None}."""
    cache = cache if cache is not None else load_cache()
    changed = False
    for fid, title in films:
        if fid in cache:
            continue
        cache[fid] = _resolve_one(fid, title)
        changed = True
        time.sleep(throttle)
    if changed:
        save_cache(cache)
    return cache


def url_for(tt: str | None, title: str) -> str:
    """A direct IMDb title link when we have a tt id, else an honest search link."""
    if tt:
        return f"https://www.imdb.com/title/{tt}/"
    return "https://www.imdb.com/find/?q=" + urllib.parse.quote_plus(title)


def main() -> int:
    from .build_site import build
    data = build()
    want = [(f["id"], f["title"]) for f in data["films"]]
    cache = resolve(want)
    have = sum(1 for fid, _ in want if cache.get(fid))
    print(f"IMDb ids: resolved {have}/{len(want)} films to a direct tt link")
    for fid, _ in want:
        print(f"  {fid:<44} {cache.get(fid) or '— (search fallback)'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
