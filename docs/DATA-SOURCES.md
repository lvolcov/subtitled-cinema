# Data sources

Everything about where the listings come from, how reliable each part is, the
exact caveats in the current data, and the plan to move to first-party cinema
sources.

---

## 1. V1 (current): yourlocalcinema.com aggregation

The site sources from **eight yourlocalcinema.com (YLC) town pages** spanning the
whole of Greater Manchester and its ring — the same listings Lucas already
relied on, but fetched automatically, cleaned up, and re-presented far better.
Each YLC page lists every accessible screening within a radius of that town, so
the pages **overlap heavily** and are merged/deduped downstream; together they
reach every subtitling cinema in the conurbation (including the outer Odeons and
the independents that the four core towns miss). YLC only publishes a page where
it has data — the towns below are the full set that currently 200s.

| Page | URL | Layout |
|---|---|---|
| Manchester | https://yourlocalcinema.com/manchester.html | A (`div.cinema`) |
| Stockport | https://yourlocalcinema.com/stockport.html | B (`div.cinema-list`) |
| Altrincham | https://yourlocalcinema.com/altrincham.html | B (`div.cinema-list`) |
| Didsbury | https://yourlocalcinema.com/didsbury.html | B (`div.cinema-list`) |
| Bolton | https://yourlocalcinema.com/bolton.html | B (`div.cinema-list`) |
| Bury | https://yourlocalcinema.com/bury.html | B (`div.cinema-list`) |
| Ashton | https://yourlocalcinema.com/ashton.html | B (`div.cinema-list`) |
| Warrington | https://yourlocalcinema.com/warrington.html | B (`div.cinema-list`) |

These are **static, hand-maintained HTML pages** — no API. Cinemas send their
accessible-screening info to YLC, who type it up. We fetch, parse, and
re-present it.

**Why start here (rather than scraping each cinema directly):** it ships a
genuinely better product *immediately* — every venue in one place, auto-refreshed
every 6 hours, searchable, mobile-first — without the multi-week effort of
wiring up and maintaining a scraper per cinema chain. Direct scraping is the V2
plan (§5).

### 1.1 Venues found (25 with subtitled screenings)

| # | Cinema | Chain | Area | Postcode | From page(s) | Coords |
|---|---|---|---|---|---|---|
| 1 | Altrincham Vue | Vue | Altrincham | WA14 | altrincham | ✓ |
| 2 | Altrincham Everyman | Everyman | Altrincham | WA14 | altrincham | ✓ |
| 3 | Ashton-Under-Lyne Cineworld | Cineworld | Ashton-Under-Lyne | — | ashton | ✓ |
| 4 | Bolton Cineworld | Cineworld | Bolton | BL1 | bolton | ✓ |
| 5 | Bolton Light | Light | Bolton | BL1 | bolton | ✓ |
| 6 | Bolton Vue | Vue | Bolton | — | bolton | ✓ |
| 7 | Didsbury Cineworld | Cineworld | Didsbury | M20 | didsbury | ✓ |
| 8 | Knutsford Curzon | Curzon | Knutsford | WA16 | altrincham | ✓ |
| 9 | Manchester Everyman | Everyman | Manchester | — | manchester | ✓ |
| 10 | Manchester Great Northern Odeon | Odeon | Manchester | — | manchester | ✓ |
| 11 | Manchester Home | HOME | Manchester | — | manchester | ✓ |
| 12 | Manchester Printworks Vue | Vue | Manchester | — | manchester | ✓ |
| 13 | Manchester Quayside Vue | Vue | Manchester | — | manchester | ✓ |
| 14 | Manchester Trafford Odeon | Odeon | Manchester | — | manchester | ✓ |
| 15 | Northwich Odeon | Odeon | Northwich | CW9 | warrington | ✓ |
| 16 | Oldham Odeon | Odeon | Oldham | — | ashton | ✓ |
| 17 | Rochdale Odeon | Odeon | Rochdale | OL11 | bury | ✓ |
| 18 | Rochdale Reel | Independent | Rochdale | — | bury | ✓ |
| 19 | St Helens Cineworld | Cineworld | St Helens | WA10 | warrington | ✓ |
| 20 | Stockport Light | Light | Stockport | SK1 | manchester **+** stockport | ✓ |
| 21 | Warrington Cineworld | Cineworld | Warrington | WA1 | warrington | ✓ |
| 22 | Warrington Odeon | Odeon | Warrington | WA5 | warrington | ✓ |
| 23 | Widnes Cheshire Reel | Independent | Widnes | WA8 | warrington | ✓ |
| 24 | Wigan Omniplex | Independent | Wigan | — | bolton | ✓ |
| 25 | Wilmslow Rex | Rex | Wilmslow | SK9 | stockport | ✓ |

*Stockport Light* appears on two source pages; the build **merges** it into one
cinema whose `cities` list contains both (the same dedupe protects every venue
that shows up across the overlapping town pages). All 25 have hand-curated
coordinates, so "nearest" works everywhere.

**Independents & one-off venues** (Rochdale Reel, Widnes Cheshire Reel, Wigan
Omniplex, Wilmslow Rex) have no reliable chain booking site, so their book-out
link is a Google search for the venue by name + postcode — the YLC source hrefs
for these point at the wrong branch (e.g. a Wigan Omniplex logo links to Omniplex
*Birmingham*), so a name search is the honest, correct-destination fallback.

**Venues deliberately dropped:** the source lists several venues as having *no*
subtitled screenings — Manchester The Block, Backyard, Cultplex; Heaton Moor
Savoy; Macclesfield Cinemac; Marple Regent. These parse out cleanly and are
excluded until they actually have shows (so the site never lists an empty venue).

### 1.2 Posters

Posters come from each film's YLC film page (e.g. `theodyssey.html`), resolved by
`build/posters.py` and cached in `build/poster_cache.json`.

- **Extraction rule:** the poster is the single `<img alt="">` (empty alt) whose
  `src` is a bare filename. Chain logos have a real `alt`; site chrome and
  anything containing `logo` or under `images/` is excluded. Pages with no
  poster (e.g. *National Theatre Live*) resolve to `None`.
- **Shared-page guard:** some films share one YLC page — notably the five
  arthouse titles all backed by `foreignlanguage.html`. That page's image isn't
  film-specific, so any poster used by more than one distinct film is **blanked**.
  Those films get the clean gradient-initials fallback tile instead of a wrong
  shared image.

Current coverage: **10 of 16 films** have a real poster; the 6 without (the
foreign-language arthouse titles + NT Live) show fallback tiles.

### 1.3 Data caveats (be honest about these)

- **Audio-described:** the parser tags and badges AD screenings, but the YLC
  pages are subtitled-first and currently list **0** AD screenings. The feature
  is built and unit-tested with a fixture, and lights up automatically if the
  source ever includes AD shows.
- **Foreign-language with English subtitles:** well represented (~32 screenings,
  almost all HOME arthouse — *Portrait of a Lady on Fire*, *Nostalghia*, *Kiki's
  Delivery Service*, *Angel's Egg*, *Girlfriends*). These are badged **"Subtitles"**
  (they carry subtitles inherently), distinct from English films badged
  **"Captioned"** (accessibility captions).
- **Booking links** point at the **chain website**, not the exact showing — the
  source doesn't expose per-showing booking URLs reliably. Exact per-showing
  deep-links are the main V2 goal.
- **No runtimes / synopses** — the source doesn't provide them. Certificates
  (U/PG/12A/15/18) *are* parsed. IMDb links are "search" links, not resolved
  title IDs (honest rather than guessing).
- **Coordinates are approximate** (venue-level, hand-curated). Fine for distance
  sorting, not for turn-by-turn.

---

## 2. Freshness & the "last checked" contract

Two guarantees keep stale data from silently misleading anyone:

1. **A bad fetch never wipes good data.** `fetch_pages.py` validates each
   download (byte length + expected markup) and keeps the previous cached copy
   if a fetch fails or looks wrong.
2. **Every venue shows when it was last checked**, and always links out to the
   cinema. A stale entry is therefore *visible and verifiable*, never presented
   as freshly confirmed.

`.cache/pages/*.html` and `public/data.json` are **committed** as a working
fallback snapshot; CI regenerates both on every run (every 6 hours).

---

## 3. Refresh cadence

- **Every 6 hours** via the GitHub Actions cron (`0 */6 * * *`), plus on every
  push to `main` and on manual dispatch.
- New screenings therefore appear within ~6 hours of the source being updated,
  with negligible load on YLC (4 page fetches + up to 16 film-page fetches for
  posters, and posters are cached so most builds fetch none).

---

## 4. Licensing / etiquette

- We fetch public pages with a descriptive User-Agent and a low, scheduled
  cadence.
- Posters are currently **hot-linked** from YLC's server. Vendoring (downloading
  and self-hosting) them is a V2 nicety — it removes the hot-link dependency and
  makes the site fully self-contained.
- This is a non-commercial, open-source, accessibility-focused project that
  drives traffic *to* the cinemas' own booking pages.

---

## 5. V2 (roadmap): first-party cinema scraping

To get **exact per-showing booking deep-links** and drop the dependency on YLC,
scrape the cinemas' own booking systems, which expose accessibility flags:

| Source | Covers (current venues) | Notes |
|---|---|---|
| **Odeon** JSON booking API | Trafford, Great Northern | one adapter, both venues; per-showing URLs |
| **Vue** JSON showtimes | Quayside, Printworks, Altrincham | one adapter, accessibility flag |
| **Cineworld / Picturehouse** API | Didsbury | public showtimes API, "subtitled" attribute |
| **HOME** site scrape | Manchester HOME | main foreign-language-with-subtitles source |
| Independents | Everyman, Light, Curzon, Rex | per-site HTML scrapers; more fragile |

**Suggested build order:** Odeon → Vue → HOME → Cineworld → independents.

**Key constraint:** each adapter must emit the **same normalised `Screening`
schema** that `build_site` already consumes. If it does, the frontend and
`data.json` don't change at all — V2 is purely a swap/augmentation of the
`fetch`+`parse` front of the pipeline. That's the whole point of keeping the
parser's output and the builder's enrichment cleanly separated.

Other V2 candidates: runtimes/synopses from a film-metadata source; vendored
posters; and expanding beyond Greater Manchester (cities are data — see
[`DEVELOPMENT.md`](DEVELOPMENT.md)).
