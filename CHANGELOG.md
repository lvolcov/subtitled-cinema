# Changelog

All notable changes to `subtitled-cinema`. Dates are YYYY-MM-DD (Europe/London).

The format loosely follows [Keep a Changelog](https://keepachangelog.com/).
This is a continuously-deployed static site (GitHub Actions → GitHub Pages), so
"releases" are milestones rather than tagged versions.

---

## [v6] — 2026-07-31 — Region filter (Greater Manchester first)

### Added
- **A "Region" picker in the always-visible top bar** — the fast way to cut ~550
  UK venues down to your own part of the country. **Greater Manchester is pinned
  to the top** of the list (this project's home patch); the rest of the UK
  follows roughly north → south, then Wales, Scotland and the islands.
- Choosing a region **rescopes the whole page**, not just the listings: the film
  rail only offers films actually showing there, the cinema picker only lists
  that region's venues, the date strip only shows days with screenings there,
  and the stat pill / hero line name the region. Selections the region excludes
  (a film, a cinema, a date) are dropped rather than silently filtering to zero.
- The choice is **remembered** (`localStorage`) as a personal default, is
  **shareable** (`?region=Greater+Manchester`), and shows as a removable chip.
  A `?region=` link always beats the remembered value.
- `build/regions.py` maps all 155 source town pages to a region, with per-venue
  overrides for venues that sit outside the region of the page listing them
  (Wilmslow, Knutsford, Warrington, Northwich, St Helens, Widnes). `data.json`
  gains a `region` per cinema and a `regions` index.

### Changed
- On phones the "Near me" button collapses to its 📍 icon so the region picker
  fits without adding a row — the sticky bar is now **shorter** than before
  (164px vs 185px on a 390px viewport).

### Verified against the cinemas' own sites
- Cross-checked our Greater Manchester Cineworld listings against Cineworld's
  own booking API over a 22-day window: **13/13 screenings matched exactly** on
  film, date and time (Didsbury 4/4, Ashton-under-Lyne 5/5, Bolton 4/4), with no
  invented entries. Two HOME Manchester showtimes were confirmed on homemcr.org.
- **Gap found (source-level, not ours):** Bolton Cineworld also runs ~55
  Indian-language screenings (Malayalam/Tamil/Hindi with English subtitles) that
  yourlocalcinema doesn't list, so they don't reach us either. Another argument
  for the V2 first-party chain scrape.

### Tests
- 62 tests (37 parser/pipeline + 25 Playwright UI), up from 45 — including
  region mapping completeness, the venue-override rule, GM-pinned-first, and UI
  tests for narrowing, rail/cinema-picker rescoping, deep-links and persistence.

---

## [v5] — 2026-07-27 — Smart per-film booking links

### Added
- **Booking links now open the *film*, not the chain homepage** (`build/booking.py`).
  **Cineworld** → its title search; **Vue** → the film's own page (slug verified
  against myvue.com at build time so it never 404s, cached in
  `booking_vue_cache.json`); **everyone else** (Odeon, Everyman, Picturehouse,
  Curzon, HOME, Light, independents) → a Google search `"<title>" <cinema> tickets`
  that lands on that venue's page for the film. Each screening carries its own
  `book` URL in `data.json`.

### Known limits
- The exact **date/time** still can't be pre-selected — public listings expose no
  per-showing booking URL, so the film page is where you choose the time. Odeon
  can't be linked directly (its site sits behind a bot queue), so it uses the
  Google fallback. True per-showing deep-links need first-party chain APIs (V2).

---

## [v4] — 2026-07-27 — Whole-UK coverage + direct IMDb links + national "nearest"

### Added
- **National coverage.** Expanded from 8 Greater Manchester town pages to **all
  ~155 yourlocalcinema town pages across the UK**, discovered from YLC's own
  store-locator feed (`build/discover_towns.py`). Coverage jumps from **25 → ~550+
  cinemas** and **~200 → ~4,800 screenings** — every subtitling chain and
  independent from Aberdeen to Cornwall, London to Cardiff.
- **A third parser layout + fuller-reading routing.** YLC is migrating town pages
  to redesigned templates (malformed nesting; a new `.film-entry`/`.film-date`
  markup). Added a document-order walk (`_parse_layout_c`) that copes with both,
  and `parse_page` now runs the old hr-split **and** the new walk and keeps the
  reading that captures more venues — so a migrated page can never silently
  under-report. Heading sanitising strips leaked film text, inline `<style>`, and
  served-district lists; heading-less one-cinema pages fall back to the town name.
- **Direct IMDb links.** IMDb links now go straight to the film's `tt…` page
  instead of a search. Resolved via Wikidata (Wikipedia → Wikidata item → IMDb ID
  P345) in `build/imdb.py`, cached in `build/imdb_cache.json`; films we can't
  resolve keep the honest search link. (IMDb itself blocks bots, so Wikidata is
  the reliable, key-less bridge — and the same lookup underpins better posters.)
- **National "nearest".** Hand-curating coordinates for 550+ venues isn't
  feasible, so `build/geocode.py` resolves each venue's outward postcode to a
  district centroid via postcodes.io (free, key-less), cached in
  `build/geo_cache.json`. Hand-curated `cinema_meta.COORDS` still win where present.
- **Coverage audit tool** (`tests/audit_coverage.py`): flags any town page whose
  raw showtime count far exceeds what we parsed (undercount signal). Used to drive
  the parser fixes; only the Ireland/NI page (a distinct film-organised layout)
  remains, tracked as a follow-up.

### Fixed
- **"Nearest" pointed at the wrong city.** Most town pages don't list postcodes,
  so whole regions (e.g. Newcastle) had **no** coordinates and "Near me" surfaced
  a cinema 30+ miles away. Now real per-venue coordinates come from the YLC
  store-locator feed (`build/coords_feed.py`), matched by name tokens, with a
  Nominatim name-geocode + hand-picked overrides mopping up the rest
  (`build/geocode_name.py`) — coord coverage 56% → **100%**, and a Newcastle user
  gets Newcastle cinemas at 0.4 mi instead of Stockton at 34 mi.
- **"Near me" was hidden** inside the Filters drawer. Promoted to a bold,
  always-visible button in the top bar.
- Frontend copy still said "Greater Manchester" — now UK-wide.

### Changed
- Posters now also fall back through the Wikidata-verified film, filling more of
  the (much larger) national film set.
- `test_all_cinemas_have_coords` → `test_curated_coords_present` +
  `test_geocode_fallback_wired` (100%-hand-curated is no longer the invariant at
  national scale).

### Known gaps
- The **Ireland / Northern Ireland** page uses a film-organised layout (each film
  lists its cinemas) with titles encoded only in image filenames; it needs a
  dedicated parser + cross-page title resolution and is deferred (see
  `docs/DATA-SOURCES.md`).

---

## [v3] — 2026-07-27 — Full Greater Manchester coverage + controls redesign

### Added
- **Full-conurbation coverage.** Added four more yourlocalcinema town pages —
  `bolton`, `bury`, `ashton`, `warrington` — taking the source set to **eight**.
  Coverage jumps from **12 → 25 cinemas** (**133 → 207 screenings**), now
  including the outer Odeons (Rochdale, Oldham, Northwich, Warrington), more
  Cineworlds and Vues, and the independents **Wigan Omniplex, Rochdale Reel,
  Widnes Cheshire Reel** — plus **Odeon at 6 venues** (was 2). `build_site.py`
  now imports `CITIES` from `fetch_pages.py`, so the source list has one home.
- **Coordinates** for all 13 new venues in `cinema_meta.py` (nearest-cinema works
  everywhere).
- **Slim sticky controls + drawer.** The frozen bar was eating ~half the phone
  screen; it's now a single slim row (group toggle · search · Filters) with the
  date strip, cinema picker, access and sort tucked into a collapsible drawer.
- **Grouped multi-select cinema filter.** The old single-select is now a popover
  with checkboxes grouped by chain (Vue, Odeon, …); ticking a chain selects all
  its venues (indeterminate state when partial). URL uses `?cinemas=a,b,c`.

### Fixed
- **Mobile horizontal overflow.** The controls bar now wraps and the (larger)
  stat pill is hidden on narrow phones — no more sideways scroll.
- **Dead booking links.** Chainless/one-off venues (Reel, the Rex, Omniplex) used
  to link to `#`, and unreliable source hrefs could point at the wrong branch
  (Wigan Omniplex → Omniplex *Birmingham*). They now fall back to a Google search
  for the venue by name + postcode.
- **Leaked postcode in cinema names** ("Rochdale Odeon 1R"): the postcode regex
  now strips the inward code too.

### Changed
- **UI tests** rewritten for the rail + slim-bar DOM (20 Playwright checks,
  including a guard that the sticky area stays under half a phone screen).

---

## [v2] — 2026-07-25 — UX & accessibility pass

Driven by an axe-core + Playwright audit (see [`docs/UX-AUDIT.md`](docs/UX-AUDIT.md)).

### Added
- **Real movie posters** per film, resolved from yourlocalcinema film pages and
  cached in `build/poster_cache.json` (`build/posters.py`). Lazy-loaded with a
  fade-in and a graceful gradient-initials fallback; broken URLs never render as
  broken images.
- **Film detail dialog — "pick a film → every cinema showing it":** poster,
  certificate, "showing subtitled at N cinemas · M screenings", and all cinemas
  distance-sorted with each showtime linking to booking.
- **Cinema detail dialog:** a venue's screenings grouped by day + "Open in Maps".
- **Shareable/bookmarkable URL state** — filters and the open dialog live in the
  query string; the browser back button closes dialogs; `popstate` re-renders.
- **Date strip** — All / Today / Tomorrow, then a chip per upcoming day with
  screenings.
- **Active-filter chips + "Clear all"**, and per-group counts.
- **Persisted "nearest"** (coordinates saved to `localStorage`); distances on
  cinema headers.
- **Loading skeleton**, **back-to-top** button.
- **PWA**: `manifest.webmanifest`, SVG icon, `theme-color`. **Open Graph /
  Twitter** meta for link previews.
- Accessibility for the new dialogs: `role="dialog"`, focus trap, Esc/overlay
  close, focus restoration, skip link, reduced-motion support.

### Changed
- Badges now distinguish **"Captioned"** (English subtitled films) from
  **"Subtitles"** (foreign-language films). Cinema/film cards are interactive.
- `build_site.py` attaches `poster_url` to screenings and the film index, and
  **blanks posters shared across multiple films** (e.g. `foreignlanguage.html`).
- Tests grown to **45** (24 parser + 21 Playwright UI), now covering dialogs,
  deep-links, chips, Esc-to-close, poster loading, and zero-console-errors.
- CI `build.yml` gained a best-effort **poster-resolution** step.

### Fixed
- Modal overlay intercepted all page clicks because a `display:grid` rule beat
  the `hidden` attribute — added `.modal-root[hidden]{display:none}`.

---

## [v1] — 2026-07-25 — Initial working MVP

### Added
- **Build pipeline** (`build/`): `fetch_pages.py` (download + validate, never
  wipe cache), `parse_ylc.py` (both YLC page layouts → normalised objects),
  `cinema_meta.py` (curated coordinates), `build_site.py` (merge across cities,
  dedupe, enrich → `public/data.json`).
- **Data gathered** from four YLC city pages (Manchester, Stockport, Altrincham,
  Didsbury): **12 cinemas, ~133 screenings, 16 films**; *Stockport Light* merged
  across two pages.
- **Frontend** (`public/`): dark, mobile-first static site — search, day filter,
  cinema/access filters, group-by cinema/film/day, 📍 nearest (geolocation +
  haversine), certificate/accessibility/IMAX badges, IMDb + Book links,
  per-venue "last checked" stamps, past-screening hiding.
- **Tests**: 37 (24 parser + 13 Playwright UI), expected counts computed in
  Python by mirroring the JS rules.
- **Automation**: `build.yml` (cron every 6 h → GitHub Pages) and `ci.yml`
  (tests); `Makefile`, `requirements.txt`.
- **Docs**: README, `docs/ARCHITECTURE.md`, `docs/DATA-SOURCES.md`.

### Deployed
- Repo published at https://github.com/lvolcov/subtitled-cinema; live at
  **https://lvolcov.github.io/subtitled-cinema/**.

---

## Unreleased / roadmap

- **V2 data**: first-party cinema scraping (Odeon → Vue → HOME → Cineworld →
  independents) for exact per-showing booking deep-links, independent of YLC.
- Runtimes/synopses from a film-metadata source; vendored (self-hosted) posters.
- More cities (cities are data — see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)).
