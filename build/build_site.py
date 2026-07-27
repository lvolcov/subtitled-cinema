"""
build_site.py — the whole build pipeline.

  1. read the cached city pages  (in production: fetched fresh by CI)
  2. parse each into normalised cinemas/screenings
  3. merge + dedupe cinemas across cities, attach coords + last-checked
  4. write public/data.json

Run:  python3 -m build.build_site
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from .parse_ylc import parse_page
from .cinema_meta import COORDS
from . import posters
from . import posters_wiki
from . import imdb
from . import geocode
from . import geocode_name
from . import coords_feed

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / ".cache" / "pages"
OUT = ROOT / "public" / "data.json"
# Kept in sync with build.fetch_pages.CITIES — the set of yourlocalcinema town
# pages we cover across Greater Manchester and its ring.
from .fetch_pages import CITIES
TIMEZONE = "Europe/London"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def film_id(title: str) -> str:
    return slugify(title)


def imdb_url(title: str, tt: str | None = None) -> str:
    # direct title link when we resolved a tt id (build.imdb, via Wikidata);
    # otherwise an honest "search IMDb" link rather than a guessed id.
    return imdb.url_for(tt, title)


def build(ref_date: date | None = None, now: datetime | None = None) -> dict:
    ref_date = ref_date or date.today()
    now = now or datetime.now()
    checked = now.replace(microsecond=0).isoformat()

    # posters come from the pre-warmed caches only (build stays offline);
    # `python3 -m build.posters` / `python3 -m build.posters_wiki` / CI refreshes
    # them before building. YLC per-film artwork first, Wikipedia (by film_id) as a
    # fallback for films that arrive via a shared page (foreign-language, NT Live).
    poster_cache = posters.load_cache()
    wiki_cache = posters_wiki.load_cache()
    imdb_cache = imdb.load_cache()      # film_id -> "tt…" (direct IMDb links)
    geo_cache = geocode.load_cache()    # outward postcode -> [lat,lng] (nearest)
    feed_coords = coords_feed._as_sets(coords_feed.load_cache())  # per-venue coords
    name_geo = geocode_name.load_cache()   # venue name -> [lat,lng] (Nominatim)

    def coords_for(name, postcode):
        # hand-curated (most precise) -> feed per-venue -> postcode district
        # centroid -> name geocode (Nominatim, last resort)
        slug = slugify(name)
        if slug in COORDS:
            return COORDS[slug]
        hit = coords_feed.match(name, feed_coords)
        if hit:
            return hit[0], hit[1]
        if postcode and geo_cache.get(postcode):
            g = geo_cache[postcode]
            return g[0], g[1]
        g = name_geo.get(name)
        if g:
            return g[0], g[1]
        return None, None

    # A single yourlocalcinema page (e.g. foreignlanguage.html) can back several
    # different films — its image isn't film-specific, so don't use it as a
    # poster. Find source_urls shared across >1 distinct film and blank them.
    _src_films: dict[str, set] = {}
    for city in CITIES:
        html = (PAGES_DIR / f"{city}.html").read_text(encoding="utf-8")
        for cin in parse_page(html, city, ref_date):
            for film in cin.films:
                _src_films.setdefault(film.source_url, set()).add(film_id(film.title))
    shared = {su for su, fids in _src_films.items() if len(fids) > 1}

    def poster_for(source_url, fid):
        # Wikipedia fallback (by film_id) covers shared-page films with no YLC art.
        ylc = None if source_url in shared else poster_cache.get(source_url)
        return ylc or wiki_cache.get(fid)

    merged: dict[str, dict] = {}   # slug -> cinema dict
    for city in CITIES:
        html = (PAGES_DIR / f"{city}.html").read_text(encoding="utf-8")
        for cin in parse_page(html, city, ref_date):
            slug = slugify(cin.name)
            entry = merged.get(slug)
            if entry is None:
                lat, lng = coords_for(cin.name, cin.postcode)
                entry = {
                    "id": slug,
                    "name": cin.name,
                    "area": cin.area,
                    "chain": cin.chain,
                    "postcode": cin.postcode,
                    "cities": [],
                    "booking_url": cin.booking_url,
                    "last_checked": checked,
                    "lat": lat,
                    "lng": lng,
                    "_seen": set(),          # (film_id, starts_at) dedupe keys
                    "screenings": [],
                }
                merged[slug] = entry
            if city not in entry["cities"]:
                entry["cities"].append(city)
            if not entry["postcode"] and cin.postcode:
                entry["postcode"] = cin.postcode

            for film in cin.films:
                fid = film_id(film.title)
                for s in film.screenings:
                    key = (fid, s.starts_at)
                    if key in entry["_seen"]:
                        continue
                    entry["_seen"].add(key)
                    entry["screenings"].append({
                        "title": film.title,
                        "film_id": fid,
                        "source_url": film.source_url,
                        "poster_url": poster_for(film.source_url, fid),
                        "imdb_url": imdb_url(film.title, imdb_cache.get(fid)),
                        "starts_at": s.starts_at,
                        "certificate": s.certificate,
                        "accessibility": s.accessibility,
                        "screen_type": s.screen_type,
                        "language": s.language,
                        "note": s.note,
                    })

    cinemas = []
    films: dict[str, dict] = {}
    for entry in merged.values():
        # a venue's postcode can arrive on a later page than its first sighting;
        # backfill a coordinate now if we still lack one.
        if entry["lat"] is None or entry["lng"] is None:
            entry["lat"], entry["lng"] = coords_for(entry["name"], entry["postcode"])
        entry.pop("_seen", None)
        entry["screenings"].sort(key=lambda x: x["starts_at"])
        cinemas.append(entry)
        for s in entry["screenings"]:
            f = films.setdefault(s["film_id"], {
                "id": s["film_id"], "title": s["title"],
                "certificate": s["certificate"], "poster_url": s.get("poster_url"),
                "count": 0, "cinemas": set(),
            })
            f["count"] += 1
            f["cinemas"].add(entry["id"])

    cinemas.sort(key=lambda c: (c["area"] or c["name"]).lower())
    for f in films.values():
        f["cinema_count"] = len(f.pop("cinemas"))
    film_list = sorted(films.values(), key=lambda f: f["title"].lower())

    total_screenings = sum(len(c["screenings"]) for c in cinemas)
    return {
        "generated_at": checked,
        "timezone": TIMEZONE,
        "cities": CITIES,
        "stats": {
            "cinemas": len(cinemas),
            "screenings": total_screenings,
            "films": len(film_list),
        },
        "films": film_list,
        "cinemas": cinemas,
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    s = data["stats"]
    print(f"Wrote {OUT.relative_to(ROOT)} — "
          f"{s['cinemas']} cinemas, {s['screenings']} screenings, {s['films']} films")
    return 0


if __name__ == "__main__":
    sys.exit(main())
