"""
booking.py — a "smart" booking link per screening, instead of the chain homepage.

Clicking a showtime should land you on *that film* at the cinema's own site, not
its front page. What's actually achievable per chain (public listings expose no
per-showing booking URL, so the exact date/time can't be pre-selected — the film
page lists its times to pick from):

- **Cineworld** — `cineworld.co.uk/search?q=<title>`: a title search that lands on
  the film. Robust (title-based, no slug guessing).
- **Vue** — `myvue.com/film/<slug>`: a real film page, but only ~half our titles
  slugify to Vue's exact slug (YLC spells "SpiderMan", Vue "spider-man"; plenty of
  special-event titles don't exist on Vue at all). So we *verify* the slug against
  myvue.com at build time (Vue returns clean 200/404) and only use it when valid.
- **Everyone else** (Odeon — its site sits behind a queue that hides good vs bad
  URLs; Everyman/Picturehouse/Curzon/HOME/Light/Omniplex/independents) — a Google
  search `"<title>" <cinema name> tickets`. The cinema name already carries the
  chain + area, so the top result is that venue's page for the film. Never a dead
  or wrong-branch link.

The build stays offline: `resolve_vue()` (a network resolver, cached in
build/booking_vue_cache.json) verifies Vue slugs; `link_for()` is pure and used by
build_site with the loaded cache.

Warm/refresh the Vue cache:  python3 -m build.booking
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VUE_CACHE = ROOT / "build" / "booking_vue_cache.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def chain_slug(title: str) -> str:
    """Slugify the way the chains do: split camelCase ("SpiderMan" -> "Spider-Man"),
    '&' -> 'and', then lowercase-hyphenate."""
    t = re.sub(r"([a-z])([A-Z])", r"\1-\2", title)
    t = t.replace("&", " and ")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t.lower()).strip("-")
    return re.sub(r"-+", "-", t)


def cineworld_link(title: str) -> str:
    return "https://www.cineworld.co.uk/search?q=" + urllib.parse.quote_plus(title)


def vue_link(slug: str) -> str:
    return "https://www.myvue.com/film/" + slug


def google_link(title: str, cinema: str) -> str:
    q = f'"{title}" {cinema} tickets'
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(q)


def link_for(chain, title, cinema_name, vue_cache) -> str:
    """The best booking link for one screening. `vue_cache` maps a Vue slug ->
    bool (does the film page exist)."""
    if chain == "Cineworld":
        return cineworld_link(title)
    if chain == "Vue" and vue_cache.get(chain_slug(title)):
        return vue_link(chain_slug(title))
    return google_link(title, cinema_name)


# --------------------------------------------------------------------------- #
# Vue slug verification (network resolver)
# --------------------------------------------------------------------------- #
def _vue_slug_exists(slug: str) -> bool:
    url = vue_link(slug)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 - 404s and errors alike mean "don't use it"
        return False


def load_vue_cache() -> dict:
    if VUE_CACHE.exists():
        try:
            return json.loads(VUE_CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_vue_cache(cache: dict) -> None:
    VUE_CACHE.write_text(json.dumps(cache, indent=0, ensure_ascii=False), encoding="utf-8")


def resolve_vue(titles, cache=None, throttle=0.5) -> dict:
    """titles: iterable of film titles shown at a Vue. Returns {slug: bool}."""
    cache = cache if cache is not None else load_vue_cache()
    changed = False
    for title in titles:
        slug = chain_slug(title)
        if slug in cache:
            continue
        cache[slug] = _vue_slug_exists(slug)
        changed = True
        time.sleep(throttle)
    if changed:
        save_vue_cache(cache)
    return cache


def main() -> int:
    from .build_site import build
    data = build()
    vue_titles = {s["title"] for c in data["cinemas"] if c["chain"] == "Vue"
                  for s in c["screenings"]}
    cache = resolve_vue(sorted(vue_titles))
    ok = sum(1 for t in vue_titles if cache.get(chain_slug(t)))
    print(f"Vue film pages: {ok}/{len(vue_titles)} titles link directly (rest -> Google)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
