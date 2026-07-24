# Architecture

`subtitled-cinema` is a **static site with a scheduled build**. There is no live backend: a GitHub Actions job fetches source listings, builds a single `data.json`, and publishes `public/` to GitHub Pages. The browser does the rest.

## Pipeline (runs in GitHub Actions, every 6 hours)

Three small Python steps under `build/`:

1. **`fetch_pages.py`** — downloads the source city pages into `.cache/pages/`. A failed or suspicious fetch **never overwrites** a good cached copy, so a bad run can't wipe data.
2. **`parse_ylc.py`** — parses each page into normalised `Cinema → Film → Screening` objects. Pure and side-effect-free (the "now" used for year inference is passed in), so it's fully unit-testable.
3. **`posters.py`** — resolves a real poster per film from its yourlocalcinema film page (the one `<img alt="">`), caching results in `build/poster_cache.json`. Runs between fetch and build; failures are best-effort and never block a deploy.
4. **`build_site.py`** — merges cinemas across the four city pages, **dedupes** (a venue like Stockport Light appears on two pages; identical film+time screenings are collapsed), attaches coordinates, posters and a `last_checked` stamp, and writes `public/data.json`. Posters that back multiple different films (a shared page like `foreignlanguage.html`) are blanked so they never mislabel.

Then `actions/upload-pages-artifact` + `deploy-pages` publish `public/`.

Because scraping happens **server-side in the Action**, there are no browser cross-origin (CORS) limits, and nothing of ours has to stay running.

## Parsing the source (the fiddly bit)

yourlocalcinema.com uses **two markup layouts**, both handled by `parse_ylc.py`:

- **Layout A** (`manchester.html`): one `<div class="cinema">` per venue, name in `<h2>`, a chain logo, one `.film-block`.
- **Layout B** (`stockport/altrincham/didsbury.html`): a single `<div class="cinema-list">` with venues separated by `<hr>`; the name is assembled from `<strong>`/text/`<em>` (area, brand, postcode); each venue is followed by a `.film-block` or a "NONE listed" note.

Both share the `.film-block` shape (alternating `p.film-title` / `p.showtime`). Notable robustness handling:

- **Showtimes** like `"Thu 06 Aug 10:30, 12:45, 15:00, Sun 09 Aug 10:15"` — bare times **carry forward** the previous token's day/month.
- **Year inference** — the source prints no year; we assume the next occurrence of each month (so a January date seen in July rolls to next year).
- **Chain detection** — the source markup is unreliable (a Vue logo links to `odeon.co.uk`), so the chain is inferred from the **cinema name** and the logo's `alt` text, and the booking URL is mapped from a canonical per-chain table.

## `data.json` schema

One file, regenerated each build:

```jsonc
{
  "generated_at": "2026-07-25T09:00:00",
  "timezone": "Europe/London",
  "cities": ["manchester", "stockport", "altrincham", "didsbury"],
  "stats": { "cinemas": 12, "screenings": 133, "films": 16 },

  "films": [                       // powers the "group by film" view
    { "id": "the-odyssey", "title": "The Odyssey", "certificate": "15", "count": 36 }
  ],

  "cinemas": [
    {
      "id": "manchester-home",
      "name": "Manchester Home",
      "area": "Manchester Home",
      "chain": "HOME",
      "postcode": null,
      "cities": ["manchester"],           // which source page(s) it came from
      "booking_url": "https://homemcr.org/",
      "last_checked": "2026-07-25T09:00:00",
      "lat": 53.4738, "lng": -2.247,      // for "nearest"; null if unknown
      "screenings": [
        {
          "title": "Portrait of a Lady on Fire",
          "film_id": "portrait-of-a-lady-on-fire",
          "source_url": "foreignlanguage.html",
          "imdb_url": "https://www.imdb.com/find/?q=Portrait...",
          "starts_at": "2026-08-02T18:00:00",   // local wall-clock, tz-naive
          "certificate": "15",
          "accessibility": ["subtitled"],        // and/or "audio-described"
          "screen_type": "standard",             // or "imax"
          "language": "foreign",                 // "en" | "foreign" (orig+subs)
          "note": "JAPANESE with English subtitles"
        }
      ]
    }
  ]
}
```

Design rule: **the parser returns raw facts; the builder enriches** (ids, imdb links, coordinates, dedupe, sorting). Enrichment that should be consistent across venues never lives in a per-page scraper.

## Frontend (`public/`)

Plain static files — no framework, no build:

- `index.html` ships the shell; `app.js` fetches `data.json` and **flattens** it into a screening list joined with its cinema.
- **All filtering, search, grouping and distance sorting happen in the browser** — instant, no requests after first load.
- Showtimes are parsed as **local wall-clock** (`new Date(y,m,d,h,min)`) to avoid timezone drift; past screenings (>60 min) are hidden using the same clock.
- **Dark, mobile-first**; responsive 1→2→3 column card grid; sticky filter bar.
- Every venue block shows its **last-checked** date and links out to the cinema, so nothing is ever silently wrong.
- **Detail dialogs & URL state:** tapping a film opens a dialog listing **every cinema showing it** (distance-sorted, each showtime a booking link); tapping a cinema lists all its screenings + a Maps link. All filters and the open dialog are serialised to the query string (`?day=…&cinema=…&view=film:the-odyssey`), so views are shareable and the back button closes dialogs. Dialogs are focus-trapped, Esc-closable, and restore focus (ARIA `role="dialog"`).
- **Posters** load lazily over the fallback gradient tile and fade in; a broken URL simply removes the `<img>`, leaving the tile — a poster never shows as broken.
- **Installable:** `manifest.webmanifest` + `theme-color` + an SVG icon make it a PWA; Open Graph tags give shared links a proper preview.
- **Test hooks:** `window.__DATA__` (preload data), `window.__NOW__` (freeze the clock) and `window.__COORDS__` (inject a location without the geolocation prompt) make the UI deterministically testable.

## Testing

- **`tests/test_parse.py`** (24 tests) — showtime/date logic, accessibility + certificate extraction, chain detection, both layouts on synthetic fixtures, the real cached pages, and the merge/dedupe pipeline (incl. the cross-city dedupe and "every cinema has coordinates" invariants).
- **`tests/test_ui.py`** (13 tests) — serves `public/`, drives headless Chromium, and asserts rendering + every filter. Expected counts are recomputed in Python by mirroring the JS visibility rules, so they track the data rather than hardcoding numbers. Also emits screenshots.

## Adding a cinema or city

Cities are **data, not code**:

1. Add the city page to the `CITIES` list in `fetch_pages.py` / `build_site.py`.
2. Add approximate coordinates for its venues in `cinema_meta.py` (keyed by slug) so "nearest" works.
3. If a new source with a different layout appears, extend `parse_ylc.py` — but the two existing layouts already cover yourlocalcinema.

## Non-goals

- No accounts, no server, no database.
- No ticket sales — we link out; booking stays with the cinema.
- We don't invent data: unconfirmed listings are stamped, not hidden-as-if-current.
