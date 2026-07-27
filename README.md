# subtitled-cinema

**A fast, honest, mobile-first guide to subtitled, captioned and audio-described cinema screenings across Greater Manchester.**

A free, self-updating alternative to [yourlocalcinema.com](https://yourlocalcinema.com) — which is a hand-typed static site that goes stale. This one refreshes itself automatically on GitHub Actions and publishes to GitHub Pages. No server, no hosting bill.

![status](https://img.shields.io/badge/status-working%20MVP-35d07f) ![tests](https://img.shields.io/badge/tests-45%20passing-2ad1ff)

---

## The problem this solves

If you rely on subtitles, finding a screening you can actually watch is painful. Cinemas bury "subtitled" / hard-of-hearing (HOH) showings behind accessibility filters and list them inconsistently. The one site that aggregates them is a manually-maintained wall of text that's often out of date and unpleasant on a phone.

`subtitled-cinema` re-publishes those accessible screenings in a clean, searchable, phone-first page — with certificate + accessibility badges, a link out to book, and an honest "last checked" stamp on every venue.

## What it does today

- **Aggregates accessible screenings** across **25 cinemas** covering the whole of Greater Manchester and its ring (Manchester, Salford, Stockport, Altrincham, Bolton, Bury, Rochdale, Oldham, Ashton, Wigan, Warrington and more) — every subtitling chain venue plus the independents (Reel, the Rex, Omniplex).
- **Subtitled / captioned** screenings, plus **foreign-language films with English subtitles** (HOME's arthouse programme), plus **audio-described** support (parsed and badged when the source lists any).
- **🎬 Real movie posters** for each film, with a graceful gradient-initials fallback.
- **Pick a film → see every cinema showing it.** A film rail up top (poster + a "showing at N cinemas" count) is the main way in; tap one to filter the whole list to that film, grouped by cinema and sorted by distance, each showtime linking out to booking.
- **Tap a cinema** name to filter to just that venue; cinema cards link out to Maps.
- **Browse & filter**: search, a **date strip** (All / Today / Tomorrow / then each upcoming day), a **grouped multi-select cinema picker** (tick a whole chain — Vue, Odeon… — or individual venues), access type, and **group by cinema / film / day**. Filters live in a slim collapsible drawer; active filters show as removable chips with a "Clear all".
- **📍 Nearest** — with your permission, sorts by distance (persisted) and shows miles.
- **Shareable & bookmarkable** — filters and the open film/cinema live in the URL, so links share exactly what you see and the back button works.
- **Installable (PWA)** with Open Graph link previews; certificate / captioned / subtitles / IMAX / audio-described badges; IMDb links.
- **Accessible**: 0 axe violations, full keyboard + screen-reader support, skip link, reduced-motion aware.
- **Honest about freshness** — every venue shows when it was last checked; past screenings (>40 min ago) drop off automatically.

Live numbers from the last build: **25 cinemas · 207 screenings · 17 films**.

## How it works

GitHub Pages only serves static files, so all the work happens **before** publish, inside **GitHub Actions** (see [`.github/workflows/build.yml`](.github/workflows/build.yml)):

```
     ┌──────────────────── GitHub Actions (cron: every 6h) ────────────────────┐
     │                                                                          │
source  fetch_pages.py     posters.py         build_site.py                     │
pages ─▶ download 4    ─▶  resolve a       ─▶ parse + merge + dedupe   ─▶ ───────┼─▶ GitHub Pages
     │   city pages         poster/film         + coords + posters              │      (public URL)
     │                      (cached)            → public/data.json + site       │
     │                                                                          │
     └──────────────────────────────────────────────────────────────────────────┘
```

The visitor just loads a fast static page (`index.html` + `data.json`); all filtering, search and distance sorting happen in the browser. Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Project layout

```
subtitled-cinema/
├── build/                    # the pipeline (Python)
│   ├── fetch_pages.py        # download source pages -> .cache/pages/
│   ├── parse_ylc.py          # parse both page layouts -> normalised screenings
│   ├── posters.py            # resolve movie posters -> build/poster_cache.json
│   ├── cinema_meta.py        # hand-curated coordinates for "nearest"
│   └── build_site.py         # merge + dedupe + posters -> public/data.json
├── public/                   # the site GitHub Pages serves
│   ├── index.html
│   ├── assets/{styles.css, app.js, icon.svg}
│   ├── manifest.webmanifest
│   └── data.json             # generated
├── tests/
│   ├── test_parse.py         # 24 parser + pipeline unit tests
│   ├── test_ui.py            # 21 Playwright UI tests (+ screenshots)
│   └── screenshots/          # visual output from the UI tests
├── .cache/pages/             # committed source snapshot (CI refreshes it)
├── .github/workflows/        # build+deploy, and CI tests
├── docs/                     # ARCHITECTURE.md, DATA-SOURCES.md
├── Makefile
└── requirements.txt
```

## Quickstart

```bash
make install     # beautifulsoup4 + playwright chromium
make all         # fetch fresh listings + build public/data.json
make serve       # http://localhost:8000
make test        # 45 tests (parser + Playwright UI)
```

No build step for the site itself — `public/` is plain static files.

## Testing

- **`tests/test_parse.py`** — showtime parsing (carry-forward times, year rollover), accessibility/certificate extraction, chain detection, both page layouts, and the merge/dedupe pipeline.
- **`tests/test_ui.py`** — drives the real page in headless Chromium: renders, no mobile overflow, every filter (day/search/cinema/access), group-by, nearest-with-distance, the **film detail modal (film → all cinemas)**, **cinema detail**, **deep-links** (`?view=film:…`), filter chips + clear-all, Esc-to-close, **real posters load**, and **zero console errors**. Expected counts are computed in Python by mirroring the JS rules, so they're not brittle magic numbers. Writes screenshots to `tests/screenshots/`.

## Decisions at a glance

| Decision | Choice |
|---|---|
| Audience | Public alternative to yourlocalcinema.com |
| Hosting | GitHub Pages (free, static) |
| Stack | Python build pipeline · vanilla static frontend (no framework) |
| Updates | Automatic via GitHub Actions, **every 6 hours** |
| Launch area | Greater Manchester + ring (8 yourlocalcinema town pages); built to add cities as data |
| What counts | Subtitled/captioned **+** audio-described; English subs **&** foreign-with-English-subs |
| Design | Dark, mobile-first |
| On scrape failure | Keep last data, stamp "last checked", link out (fetch never wipes cache) |

## Roadmap

- **V1 (now):** source from yourlocalcinema's eight Greater Manchester town pages — fast to ship, immediately better UX, full-conurbation coverage.
- **V2:** scrape the cinema chains directly (Odeon/Vue/Cineworld JSON APIs) for exact **per-showing booking deep-links** and independence from YLC. See [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md).
- Runtimes/synopses via a film metadata source; vendored (self-hosted) posters; more cities.

## Troubleshooting & FAQ

**The listings look out of date.** The site rebuilds every 6 hours; new
screenings appear within that window. Every venue also shows a "last checked"
date and links out to the cinema — always confirm there before travelling.

**A poster is missing / shows a coloured tile with initials.** Some films have no
poster on the source (e.g. National Theatre Live), and the foreign-language
arthouse titles share one source page so their poster is deliberately blanked to
avoid mislabelling. The tile is the intended fallback. To refresh posters:
`python3 -m build.posters`.

**"Nearest" does nothing.** It needs location permission; if denied it silently
falls back to A–Z. Grant location and tap 📍 Nearest again (the choice is
remembered).

**Booking opens the chain homepage, not the exact showing.** Correct for now —
the source doesn't expose per-showing links. Exact deep-links are the V2 goal
(see [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md)).

**A GitHub Actions run shows a "Node.js 20 is deprecated" warning.** Harmless —
it's a GitHub platform notice, not a failure, and not fixable from this repo.

**How do I add a cinema or a whole city?** Cities are data, not code — see the
recipes in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full technical detail: pipeline modules, exact `data.json` schema, parsing internals, frontend state/URL model, testing, deployment, extension.
- [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) — where the data comes from, every venue found, poster resolution, data caveats, the freshness contract, and the V2 first-party-scraping plan.
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — setup, `make` commands, common recipes (add a city/cinema/poster), conventions, and testing gotchas.
- [`docs/UX-AUDIT.md`](docs/UX-AUDIT.md) — the accessibility/usability audit that drove v2: method, findings, what shipped, and a bug it caught.
- [`CHANGELOG.md`](CHANGELOG.md) — version history (v1 MVP, v2 UX pass) and roadmap.
