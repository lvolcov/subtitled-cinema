"""
posters.py — resolve a poster image for each film from its yourlocalcinema
film page.

On those pages the poster is the one <img> with an *empty* alt attribute
(alt="") whose src is a bare filename — chain logos carry a real alt ("Odeon")
and site chrome (mainlogo/more/glasses/trailers, images/*) is either pathed or
alt-less. So `alt == ""` + bare filename selects exactly the poster, and pages
without one (e.g. National Theatre Live) correctly resolve to None.

Results are cached in build/poster_cache.json keyed by the film's source_url so
we don't refetch every build. Network failures never remove a cached value.

Run standalone to warm/refresh the cache:  python3 -m build.posters
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "poster_cache.json"
BASE = "https://yourlocalcinema.com/"
UA = "subtitled-cinema/1.0 poster bot"

# site chrome / logos that are never a poster (bare filenames)
BLOCK = {
    "mainlogo.png", "more.jpg", "glasses2020.jpg", "trailers.jpg",
}


def _is_poster_img(img) -> bool:
    if img.get("alt", None) != "":          # must be present AND empty
        return False
    src = (img.get("src") or "").strip()
    if not src or "/" in src:               # bare filename only (no images/…)
        return False
    low = src.lower()
    if low in BLOCK or "logo" in low:        # skip site chrome / logo strips
        return False
    return True


def extract_poster_src(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        if _is_poster_img(img):
            return img["src"].strip()
    return None


def _fetch(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:                        # noqa: BLE001
        return None


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:                    # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve(source_urls, cache=None, fetch=_fetch) -> dict:
    """Return {source_url: poster_url_or_None}. Uses/updates the cache.

    `fetch` is injectable so tests can avoid the network.
    """
    cache = cache if cache is not None else load_cache()
    changed = False
    for su in source_urls:
        if not su or not su.endswith(".html"):
            continue
        if su in cache:
            continue
        html = fetch(BASE + su)
        poster = None
        if html:
            src = extract_poster_src(html)
            if src:
                poster = BASE + src
        cache[su] = poster                   # cache negatives too (avoid refetch)
        changed = True
    if changed:
        save_cache(cache)
    return cache


def main() -> int:
    from .build_site import build
    data = build()
    srcs = sorted({s["source_url"] for c in data["cinemas"]
                   for s in c["screenings"] if s.get("source_url")})
    cache = resolve(srcs)
    have = sum(1 for su in srcs if cache.get(su))
    print(f"Posters resolved: {have}/{len(srcs)} films have artwork")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
