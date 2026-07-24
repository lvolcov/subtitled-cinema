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

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / ".cache" / "pages"
OUT = ROOT / "public" / "data.json"
CITIES = ["manchester", "stockport", "altrincham", "didsbury"]
TIMEZONE = "Europe/London"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def film_id(title: str) -> str:
    return slugify(title)


def imdb_url(title: str) -> str:
    # honest "search IMDb" link — we don't guess an exact title id
    from urllib.parse import quote_plus
    return f"https://www.imdb.com/find/?q={quote_plus(title)}"


def build(ref_date: date | None = None, now: datetime | None = None) -> dict:
    ref_date = ref_date or date.today()
    now = now or datetime.now()
    checked = now.replace(microsecond=0).isoformat()

    merged: dict[str, dict] = {}   # slug -> cinema dict
    for city in CITIES:
        html = (PAGES_DIR / f"{city}.html").read_text(encoding="utf-8")
        for cin in parse_page(html, city, ref_date):
            slug = slugify(cin.name)
            entry = merged.get(slug)
            if entry is None:
                lat, lng = COORDS.get(slug, (None, None))
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
                        "imdb_url": imdb_url(film.title),
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
        entry.pop("_seen", None)
        entry["screenings"].sort(key=lambda x: x["starts_at"])
        cinemas.append(entry)
        for s in entry["screenings"]:
            f = films.setdefault(s["film_id"], {
                "id": s["film_id"], "title": s["title"],
                "certificate": s["certificate"], "count": 0,
            })
            f["count"] += 1

    cinemas.sort(key=lambda c: (c["area"] or c["name"]).lower())
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
