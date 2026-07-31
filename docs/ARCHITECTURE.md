# Architecture

This document explains, in detail, how `subtitled-cinema` is put together: the
build pipeline, the data model, how the source is parsed, how the frontend
works, how state is managed, how it's tested, and how to extend it.

> **One-line summary:** it's a **static site with a scheduled build**. A GitHub
> Actions job fetches the source listings, transforms them into a single
> `data.json`, and publishes the `public/` folder to GitHub Pages. The browser
> does all filtering, searching and sorting client-side. There is no server, no
> database, and nothing of ours stays running between builds.

---

## 1. High-level flow

```
                       GitHub Actions runner (cron: every 6 hours)
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                                                                             │
   │  build/fetch_pages.py    build/posters.py       build/build_site.py         │
   │  ───────────────────     ────────────────       ──────────────────          │
   │  download ~155 YLC →   resolve a poster    →  parse each page, merge &     │
   │  city pages into          per film, cache        dedupe cinemas, attach      │
   │  .cache/pages/*.html      to poster_cache.json   coords + posters + stamps   │
   │                                                  → write public/data.json    │
   │                                                                             │
   │                         actions/upload-pages-artifact → actions/deploy-pages │
   └───────────────────────────────────────────────────┬───────────────────────┘
                                                        │
                                                        ▼
                                          GitHub Pages (static hosting)
                                          public/index.html + data.json + assets
                                                        │
                                                        ▼
                             Visitor's browser: app.js fetches data.json and
                             renders / filters / sorts everything client-side.
```

Why this shape:

- **GitHub Pages only serves static files.** Anything "live" (fetching third-party
  pages, resolving posters) must happen *before* publish. GitHub Actions is that
  "before" step, and it's free.
- **Scraping runs server-side in the Action**, so browser cross-origin (CORS)
  restrictions never apply — those only bite code running in a visitor's browser.
- **The visitor downloads one JSON file** and a tiny vanilla-JS app. No backend
  round-trips, no framework, instant filtering.

---

## 2. The build pipeline (`build/`)

Four small, single-responsibility Python modules. They run in order in CI, and
each can be run by hand (`python3 -m build.<module>`).

### 2.1 `fetch_pages.py` — download the source

- Downloads `https://yourlocalcinema.com/<city>.html` for each city in `CITIES`
  (`manchester`, `stockport`, `altrincham`, `didsbury`) into `.cache/pages/`.
- **Validates** each response (minimum byte length + expected markup present).
- **Never overwrites a good cached copy with a bad fetch** — if a download fails
  or looks wrong, the previous `.html` snapshot is kept. This is the first half
  of the "last-checked" reliability contract: a broken source can never wipe
  working data.
- Exit code is `0` as long as every city has *some* cached copy (fresh or old).

### 2.2 `parse_ylc.py` — parse a page into normalised objects

- Turns raw HTML into `Cinema → Film → Screening` dataclasses.
- **Pure and side-effect-free.** The "current date" used for year inference is
  passed in as `ref_date`, so parsing is deterministic and fully unit-testable
  (no clock, no network).
- Details in [§4 Parsing the source](#4-parsing-the-source-the-fiddly-bit).

### 2.3 `posters.py` — resolve a poster per film

- For each film's `source_url` (e.g. `theodyssey.html`), fetches that YLC film
  page and extracts the poster image: **the single `<img>` with an empty `alt`
  attribute (`alt=""`) whose `src` is a bare filename.**
  - Chain logos carry a real `alt` ("Odeon") → excluded.
  - Site chrome (`mainlogo.png`, `more.jpg`, `glasses2020.jpg`, `trailers.jpg`,
    anything under `images/`, anything containing `logo`) → excluded.
  - Pages with no poster (e.g. National Theatre Live) correctly resolve to
    `None` → the frontend falls back to a generated tile.
- Results are cached in **`build/poster_cache.json`**, keyed by `source_url`,
  and **negatives are cached too** (so we don't refetch a page that has no
  poster). Network failures never remove a cached value.
- `fetch` is injectable, so tests resolve posters without touching the network.
- Best-effort: in CI this step has `continue-on-error: true` — a poster hiccup
  must never block a deploy.

### 2.4 `build_site.py` — merge, dedupe, enrich, write

The orchestrator. In one `build()` call it:

1. Parses all four city pages.
2. **Merges cinemas across pages by slug.** A venue like *Stockport Light*
   appears on both `manchester.html` and `stockport.html`; it becomes one cinema
   whose `cities` list is `["manchester", "stockport"]`.
3. **Dedupes screenings** within a cinema by `(film_id, starts_at)` — identical
   film+time entries are collapsed.
4. **Attaches coordinates** from `cinema_meta.COORDS` (for "nearest").
5. **Attaches posters** from `poster_cache.json`. A poster that backs *more than
   one distinct film* (a shared page like `foreignlanguage.html`, used by five
   different arthouse films) is **blanked**, so a generic image never
   mislabels a specific film.
6. **Stamps** every cinema with `last_checked` (build time).
7. Builds a **film index** (id, title, certificate, poster, how many screenings,
   how many cinemas) for the "group by film" view and the film dialog.
8. Sorts cinemas by area, screenings by time, films alphabetically.
9. Writes pretty-printed **`public/data.json`**.

`build()` reads posters **from the cache only** — it never hits the network — so
`build_site` is safe to run in unit tests and offline. Refreshing the cache is a
separate, explicit step (`python3 -m build.posters` / the CI poster step).

### 2.5 `regions.py` — which part of the UK a venue is in

The source has no region concept — only ~155 town pages. `regions.py` maps each
town page to a UK region (`TOWN_REGION`), with per-venue overrides
(`VENUE_REGION`) because a town page lists everything within travelling
distance: `wilmslow-rex` and `knutsford-curzon` appear on Manchester-area pages
but are Cheshire, not Greater Manchester.

`region_for(slug, cities)` = override, else the region of the **first** town page
the venue was found on. `build_site` stamps it onto each cinema and rolls up a
`regions` index. `REGION_ORDER` fixes the display order and pins **Greater
Manchester first** — it's this project's home patch and its most-used filter.

### 2.6 `cinema_meta.py` — hand-curated coordinates

A tiny `slug → (lat, lng)` table. The source pages don't give coordinates, so
these are curated by hand (venue-level, approximate — good enough to sort by
distance). Venues without an entry still show; they're just excluded from
distance ordering. All 12 current venues have coordinates.

---

## 3. The `data.json` contract

One file, regenerated every build. This is the **only** interface between the
Python pipeline and the JavaScript frontend — keep it stable.

```jsonc
{
  "generated_at": "2026-07-25T09:00:00",   // build time (local, Europe/London)
  "timezone": "Europe/London",
  "cities": ["manchester", "stockport", "altrincham", "didsbury"],
  "stats": { "cinemas": 12, "screenings": 133, "films": 16 },

  // ---- region index: powers the "Region" picker in the top bar ----
  // ordered by build/regions.py::REGION_ORDER — Greater Manchester first
  "regions": [
    { "name": "Greater Manchester", "cinemas": 18, "screenings": 190 }
  ],

  // ---- film index: powers "group by film" + the film picker dialog ----
  "films": [
    {
      "id": "the-odyssey",               // slug of the title
      "title": "The Odyssey",
      "certificate": "15",               // or null
      "poster_url": "https://yourlocalcinema.com/theodyssey.jpg",  // or null
      "count": 36,                       // total screenings of this film
      "cinema_count": 12                 // distinct cinemas showing it
    }
  ],

  // ---- cinemas, each with its screenings ----
  "cinemas": [
    {
      "id": "manchester-home",           // slug of the name (also the DOM id)
      "name": "Manchester Home",
      "area": "Manchester Home",         // town/area label used for sorting
      "chain": "HOME",                   // detected chain, or null
      "postcode": "M15",                 // or null
      "cities": ["manchester"],          // which source page(s) it came from
      "region": "Greater Manchester",    // UK region (build/regions.py)
      "booking_url": "https://homemcr.org/",   // chain site (best-effort)
      "last_checked": "2026-07-25T09:00:00",
      "lat": 53.4738, "lng": -2.247,     // for "nearest"; null if unknown

      "screenings": [
        {
          "title": "Portrait of a Lady on Fire",
          "film_id": "portrait-of-a-lady-on-fire",
          "source_url": "foreignlanguage.html",       // YLC film page
          "poster_url": null,                          // blanked (shared page)
          "imdb_url": "https://www.imdb.com/find/?q=Portrait+of+a+Lady+on+Fire",
          "starts_at": "2026-08-02T18:00:00",          // LOCAL wall-clock, tz-naive
          "certificate": "15",                         // or null
          "accessibility": ["subtitled"],              // and/or "audio-described"
          "screen_type": "standard",                   // or "imax"
          "language": "en",                            // "en" | "foreign" (orig+subs)
          "note": "subtitled (15)"                     // raw source span text
        }
      ]
    }
  ]
}
```

**Field notes**

- `starts_at` is **timezone-naive local time** (`YYYY-MM-DDTHH:MM:SS`). The
  frontend parses it component-by-component (never `new Date(isoString)`) to
  avoid the browser shifting it by its own timezone.
- `accessibility` is an array so a screening can be both subtitled and
  audio-described.
- `note` is the raw text from the source span (e.g. `"PARENT AND BABY subtitled"`,
  `"JAPANESE with English subtitles"`); the frontend surfaces it as a warning
  line when it contains caveats.
- **Design rule:** the *parser returns raw facts*; the *builder enriches*
  (slugs, IMDb links, coordinates, posters, dedupe, sorting). Anything that must
  be consistent across venues lives in the builder, never in a per-page path.

---

## 4. Parsing the source (the fiddly bit)

yourlocalcinema.com uses **two different markup layouts**. `parse_page()`
detects which and dispatches:

- **Layout A** (`manchester.html`): one `<div class="cinema">` per venue; the
  name is in an `<h2>`; a chain logo; a single `.film-block`.
- **Layout B** (`stockport/altrincham/didsbury.html`): a single
  `<div class="cinema-list">` where venues are separated by `<hr>`. The name is
  assembled from `<strong>` (area) + surrounding text (brand) + `<em>`
  (postcode). Each venue is followed by a `.film-block` **or** a "NONE listed"
  paragraph (dropped).

Both share the `.film-block` shape: alternating `p.film-title` (title link +
`span.showtime` describing access/certificate) and `p.showtime` (the dates).

**Robustness handling worth knowing about:**

- **Carry-forward showtimes** — `"Thu 06 Aug 10:30, 12:45, 15:00, Sun 09 Aug 10:15"`:
  bare times (`12:45`, `15:00`) inherit the previous token's day and month.
- **Year inference** — the source prints no year. We assume the *next* occurrence
  of each month: a January date parsed in July rolls to next year. See
  `infer_year()`.
- **Chain detection** — the source markup is unreliable (a Vue logo links to
  `odeon.co.uk`!). So the chain is inferred from the **cinema name** and the
  logo's **`alt` text**, and the booking URL is mapped from a canonical
  per-chain table (`CHAIN_URL`), not scraped hrefs.
- **Name assembly (Layout B)** — the area `<strong>` is often nested inside an
  `<a>`, so we search descendants; a stray injected `"Manchester"` qualifier is
  stripped (e.g. area *Altrincham* + brand *"Manchester Vue"* → *"Altrincham
  Vue"*); postcodes are pulled out via regex.
- **Access parsing** — `parse_access()` extracts accessibility tags
  (`subtitled` if "subtitle"/"caption" present; `audio-described` if
  "audio"+"describ"), the certificate (`(U|PG|12A|12|15|18|TBC)`), screen type
  (`imax`), and language (`foreign` when "english subtitles"/"foreign" appears).

---

## 5. Frontend (`public/`)

Plain static files — **no framework, no build step, no dependencies.**

- `index.html` — the shell (header, controls, results container, modal root,
  footer, PWA/OG meta).
- `assets/styles.css` — dark, mobile-first, responsive 1→2→3-column card grid.
- `assets/app.js` — the whole client (~480 lines of vanilla JS).
- `data.json` — the data, `fetch()`ed on load.
- `manifest.webmanifest` + `assets/icon.svg` — PWA install metadata.

### 5.1 Data handling

- On load, `app.js` `fetch()`es `data.json` and **flattens** it into a single
  list of screenings, each joined with its cinema's fields (name, chain,
  coords, booking url, last_checked). It also indexes `cinemaById` and
  `filmById` for the detail dialogs.
- **All filtering, searching, grouping and distance sorting happen in the
  browser.** After the first load there are no further requests (except lazy
  poster images).
- Showtimes are parsed as **local wall-clock** via `parseLocal()`
  (`new Date(y, m-1, d, h, min)`) — never `new Date(isoString)` — to avoid
  timezone drift. Past screenings (>60 min ago) are hidden with the same clock.

### 5.2 State model & URL

**Region scoping.** The region picker in the always-visible bar is not just
another row filter: choosing one **rebuilds every region-scoped control** —
the film rail, the grouped cinema picker, the date strip, the stat pill and the
hero kicker — and drops any selected film/cinema/date the region excludes
(`applyRegionScope()`). It's remembered in `localStorage` (`sc-region`) as a
personal default; a `?region=` link always wins over the remembered value, and
`?region=` (empty) explicitly means "all of the UK".

The UI state (`search`, `day`, `cinema`, `access`, `groupBy`, `near`, `coords`,
`region`, and `view` = the open dialog) is **serialised to the query string**:

```
?q=odyssey&day=today&cinema=manchester-home&access=subtitled&group=film&near=1&region=Greater+Manchester&view=film:the-odyssey
```

- Filter changes call `writeURL(false)` → `history.replaceState` (no history spam).
- Opening a dialog calls `writeURL(true)` → `history.pushState`, so the browser
  **back button closes the dialog**.
- `popstate` re-reads the URL and re-renders — back/forward fully drive the UI.
- This makes every view **shareable and bookmarkable** — a link reproduces
  exactly what the sender sees, including an open film/cinema.

### 5.3 Detail dialogs ("pick a film → all cinemas")

- **Film dialog:** tap a film (poster or title) → a dialog with the poster,
  certificate, "showing subtitled at N cinemas · M screenings", and **every
  cinema showing it**, distance-sorted, each showtime a pill linking to booking.
- **Cinema dialog:** tap a cinema name/header → all of that cinema's upcoming
  screenings grouped by day, plus an "Open in Maps" link (from coordinates, else
  a name+postcode search).
- **Accessibility:** dialogs use `role="dialog" aria-modal="true"`, are
  **focus-trapped** (Tab cycles within), close on **Esc** or overlay click, and
  **restore focus** to the element that opened them.

### 5.4 Other UX behaviours

- **Posters** load lazily over the fallback gradient-initials tile and fade in
  when decoded. A broken URL triggers `onerror` which removes the `<img>`,
  leaving the tile — a poster **never** renders broken.
- **Date strip** — All / Today / Tomorrow, then a chip per upcoming day that has
  screenings (built from the data, capped at 14).
- **Active-filter chips** — each active filter shows as a removable chip, plus
  "Clear all".
- **Nearest** — asks for geolocation once, **persists** the coords to
  `localStorage`, shows per-cinema distances, and degrades gracefully if denied.
- **Loading skeleton** while `data.json` loads; **back-to-top** button on long
  lists; sticky filter bar.
- **"Captioned" vs "Subtitles"** — English-language subtitled films are badged
  *Captioned* (accessibility captions); foreign-language films are badged
  *Subtitles* (they carry subtitles inherently). This distinction matters to the
  audience.

### 5.5 Test hooks

Three globals let tests drive the UI deterministically without a network or a
real clock:

- `window.__DATA__` — preload the dataset (skip the `fetch`).
- `window.__NOW__` — freeze "now" (so Today/Tomorrow/past-hiding are stable).
- `window.__COORDS__` — inject a location (skip the geolocation prompt).

---

## 6. Testing

Two suites, run by `make test` and in CI (`.github/workflows/ci.yml`).

- **`tests/test_parse.py` (37 tests)** — showtime/date logic (carry-forward,
  year rollover), accessibility + certificate extraction, chain detection, both
  layouts on synthetic fixtures, the real cached pages, and the merge/dedupe
  pipeline (including cross-city dedupe and the "every cinema has coordinates"
  invariant). Pure Python, no browser.
- **`tests/test_ui.py` (25 tests)** — serves `public/`, drives headless
  Chromium via Playwright, and asserts: rendering, no mobile horizontal
  overflow, every filter (day/search/cinema/access), group-by, nearest with
  distances, the **film dialog (film → all cinemas)**, **cinema dialog**,
  **deep-links** (`?view=film:…`), filter chips + clear-all, Esc-to-close, real
  posters loading, and **zero console errors**. Expected counts are recomputed
  in Python by mirroring the JS visibility rules, so they track the data rather
  than hardcoding brittle numbers. Screenshots are written to
  `tests/screenshots/`.

---

## 7. Deployment

- **`.github/workflows/build.yml`** — the deploy pipeline. Triggers: `schedule`
  (cron `0 */6 * * *`), `workflow_dispatch` (manual), and `push` to `main`.
  Steps: checkout → setup Python → `fetch_pages` → `posters` (best-effort) →
  `build_site` → upload Pages artifact → deploy. A `concurrency` group prevents
  overlapping deploys.
- **`.github/workflows/ci.yml`** — runs both test suites on push/PR (UI job
  installs Chromium and uploads screenshots as an artifact).
- **Pages config** — source is "GitHub Actions" (`build_type: workflow`), so the
  workflow deploys the artifact directly; there's no `gh-pages` branch.

---

## 8. Extending: add a cinema or a city

Cities are **data, not code**:

1. Add the city page to the `CITIES` list in `fetch_pages.py` (`build_site.py`
   imports it, so a single edit covers both).
2. Add approximate coordinates for its venues in `cinema_meta.py` (keyed by the
   name slug) so "nearest" works.
2b. Map the new town page to a region in `regions.py :: TOWN_REGION` (a test
   fails if any town page is unmapped), and add a `VENUE_REGION` override for
   any venue on it that sits in a different region.
3. If a genuinely new source layout appears, extend `parse_ylc.py` — but the two
   existing layouts already cover all of yourlocalcinema.

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for step-by-step recipes.

---

## 9. Non-goals

- **No accounts, no server, no database.** Deliberately.
- **No ticket sales** — we link out; booking stays with the cinema.
- **We don't invent data** — unconfirmed listings are stamped `last_checked` and
  linked out, never hidden-as-if-current or fabricated.
