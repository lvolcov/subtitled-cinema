# Data sources

Everything about where the listings come from, how reliable each part is, the
exact caveats in the current data, and the plan to move to first-party cinema
sources.

---

## 1. V1 (current): yourlocalcinema.com aggregation

The site sources from **all ~155 yourlocalcinema.com (YLC) town pages across the
UK** — the same listings people already relied on, but fetched automatically,
cleaned up, and re-presented far better. Each YLC page lists every accessible
screening within a radius of that town, so the pages **overlap heavily** and are
merged/deduped downstream; together they reach essentially every subtitling
cinema in the country (~550 venues, ~4,800 screenings on a typical day).

These are **static, hand-maintained HTML pages** — no API. Cinemas send their
accessible-screening info to YLC, who type it up. We fetch, parse, and
re-present it.

### 1.1 Discovering the town pages

YLC has no sitemap, and its `/locations.html` is a JavaScript store-locator
widget. That widget loads every YLC cinema — name, coordinates, and a link to its
town page — from a single JSONP feed
(`cdn.storelocatorwidgets.com/json/<uid>`). `build/discover_towns.py` reads that
feed and extracts every distinct `<town>.html` a cinema links to, which is the
authoritative list of pages to fetch. Paste its output into
`build/fetch_pages.CITIES`. (The list is a committed snapshot so builds stay
deterministic and offline-parseable; re-run the script when YLC adds towns.)

### 1.2 Page layouts (three, and counting)

YLC is mid-migration between templates, so the parser handles three shapes and
`parse_page` keeps whichever reading captures the most venues:

| Layout | Marker | Notes |
|---|---|---|
| A | `div.cinema` | original; name in `<h2>`, one `.film-block`. |
| B | `div.cinema-list` split on `<hr>` | original; name from `<font>/<strong>/<em>`. |
| C | document-order walk | redesigned/malformed pages: badly-nested `.film-block`, or a newer `.film-entry`/`.film-date` markup. |

Because layouts B and C each win on different pages, running both and keeping the
fuller result means a page migrated to a new template can never silently
under-report its venues (`tests/audit_coverage.py` guards this).

### 1.3 Venues, names and dedupe

A venue that appears on several overlapping town pages is **merged** into one
cinema whose `cities` list contains every page it came from (e.g. *Stockport
Light* from both `manchester` and `stockport`). Chains are detected from the
venue name, the logo's `alt`, and — when a logo has no alt — the booking domain it
links to (so a bare Curzon logo still resolves to Curzon). A few source pages list
a lone cinema with **no heading text at all**; rather than drop its shows, the
venue falls back to the town name (plus chain if a logo gives one) — e.g. "Oxford
Curzon", "Orkney". Its screenings are always captured; only the name is generic.

**Independents & one-off venues** with no reliable chain booking site get a
Google search for the venue by name + postcode as their book-out link — the YLC
source hrefs for these often point at the wrong branch (e.g. a Wigan Omniplex logo
links to Omniplex *Birmingham*), so a name search is the honest, correct fallback.

**Venues deliberately dropped:** the source marks many venues "NONE listed" (no
current subtitled shows). These parse out cleanly and are excluded until they
actually have shows, so the site never lists an empty venue.

### 1.4 IMDb links (direct `tt…`, via Wikidata)

Each film links straight to its IMDb title page. There is no free IMDb API and
IMDb blocks bots, so `build/imdb.py` resolves the id through **Wikidata**: look
the film up on Wikipedia → its Wikidata item → the item's IMDb ID (property
P345). That id is editorially curated (trustworthy), and the same lookup improves
posters. Films we can't resolve keep an honest IMDb *search* link rather than a
guessed id. Cached in `build/imdb_cache.json` (negatives cached too).

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

Films that arrive only via a shared page (or have no YLC art) fall back to a
**Wikipedia** poster (`build/posters_wiki.py`, keyed by film id, `pilicense=any`
so non-free posters are included) — the same Wikidata-verified article that gives
us the IMDb id. Anything still unresolved shows the clean gradient-initials tile.

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
  (U/PG/12A/15/18) *are* parsed. **IMDb links are direct `tt…` links** where
  Wikidata resolves the id (most mainstream films); the rest keep an honest IMDb
  *search* link.
- **Coordinates** come, in priority order, from: hand-curated `cinema_meta.COORDS`
  → the **YLC store-locator feed** (real per-venue lat/lng, matched to our venue by
  sorted name tokens since the feed writes "Cineworld Newcastle" where we parse
  "Newcastle Cineworld" — `build/coords_feed.py`, UK-bounds sanity-checked) → a
  postcode-district centroid from postcodes.io (`build/geocode.py`) → geocoding
  the venue **name** via OpenStreetMap Nominatim (`build/geocode_name.py`, with a
  handful of hand-picked overrides for odd names/typos). Together these place
  **100%** of venues. Fine for "sort by distance", not for turn-by-turn. (The town
  pages themselves rarely list a postcode, so the feed — not geocoding — is what
  actually makes national "nearest" work; name-geocoding mops up the rest.)

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
  with modest load on YLC (~155 town-page fetches; film-page/poster/IMDb/geocode
  lookups are all cached, so most builds fetch only the town pages).

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

## 5. Known gaps & roadmap

### 5.1 Ireland / Northern Ireland page (near-term)

The one YLC page not yet parsed is `ireland.html`. Unlike every other page it is
**film-organised** (each film card lists the cinemas showing it, rather than each
cinema listing its films), and the film's title exists only as an image filename
(`theodyssey.jpg`), not as text. Parsing it needs a dedicated layout plus
cross-page title resolution (map the film-page slug to the real title using the
other pages, so its films de-dupe against the national set instead of creating
"Theodyssey" vs "The Odyssey"). It's the biggest single chunk of remaining
coverage (~80 cinemas, incl. Northern Ireland) and is the top follow-up.
`tests/audit_coverage.py` flags it until then.

### 5.2 First-party cinema scraping (V2)

To get **exact per-showing booking deep-links** and drop the dependency on YLC,
scrape the cinemas' own booking systems, which expose accessibility flags — Odeon
/ Vue / Cineworld / Picturehouse all have JSON showtime APIs with a "subtitled"
attribute; the chains cover most of the ~550 venues, with per-site scrapers for
the independents. **Suggested build order:** Odeon → Vue → Cineworld → HOME →
independents.

**Key constraint:** each adapter must emit the **same normalised `Screening`
schema** that `build_site` already consumes. If it does, the frontend and
`data.json` don't change at all — V2 is purely a swap/augmentation of the
`fetch`+`parse` front of the pipeline. That's the whole point of keeping the
parser's output and the builder's enrichment cleanly separated.

Other candidates: runtimes/synopses from a film-metadata source; vendored
(self-hosted) posters; hand-curating coordinates for the busiest venues to
sharpen "nearest".
