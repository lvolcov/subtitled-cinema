# Changelog

All notable changes to `subtitled-cinema`. Dates are YYYY-MM-DD (Europe/London).

The format loosely follows [Keep a Changelog](https://keepachangelog.com/).
This is a continuously-deployed static site (GitHub Actions → GitHub Pages), so
"releases" are milestones rather than tagged versions.

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
