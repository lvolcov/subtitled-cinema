# subtitled-cinema

**A fast, honest, mobile-first guide to subtitled, captioned and audio-described cinema screenings across Greater Manchester.**

A free, self-updating alternative to [yourlocalcinema.com](https://yourlocalcinema.com) — which is a hand-typed static site that goes stale. This one refreshes itself automatically on GitHub Actions and publishes to GitHub Pages. No server, no hosting bill.

![status](https://img.shields.io/badge/status-working%20MVP-35d07f) ![tests](https://img.shields.io/badge/tests-37%20passing-2ad1ff)

---

## The problem this solves

If you rely on subtitles, finding a screening you can actually watch is painful. Cinemas bury "subtitled" / hard-of-hearing (HOH) showings behind accessibility filters and list them inconsistently. The one site that aggregates them is a manually-maintained wall of text that's often out of date and unpleasant on a phone.

`subtitled-cinema` re-publishes those accessible screenings in a clean, searchable, phone-first page — with certificate + accessibility badges, a link out to book, and an honest "last checked" stamp on every venue.

## What it does today

- **Aggregates accessible screenings** across **12 cinemas** in Greater Manchester (Manchester, Stockport, Altrincham, Didsbury and nearby towns).
- **Subtitled / captioned** screenings, plus **foreign-language films with English subtitles** (HOME's arthouse programme), plus **audio-described** support (parsed and badged when the source lists any).
- **Browse & filter**: search box, day (All / Today / Tomorrow / This week), by cinema, by access type, and **group by cinema / film / day**.
- **📍 Nearest** — with your permission, sorts cinemas by distance and shows miles.
- **Certificate + accessibility + IMAX + "orig + subs" badges**, generated poster tiles, IMDb search link, and a **Book** link to the cinema chain.
- **Honest about freshness** — every venue shows when it was last checked; past screenings (>60 min ago) drop off automatically.

Live numbers from the last build: **12 cinemas · 133 screenings · 16 films**.

## How it works

GitHub Pages only serves static files, so all the work happens **before** publish, inside **GitHub Actions** (see [`.github/workflows/build.yml`](.github/workflows/build.yml)):

```
        ┌──────────────── GitHub Actions (cron: every 6h) ────────────────┐
        │                                                                 │
  source│  fetch_pages.py  ──▶  build_site.py  ──▶  public/data.json      │
  pages ┼─▶ download 4     ──▶  parse + merge  ──▶  + static site  ──▶ ────┼─▶ GitHub Pages
        │   city pages          + dedupe             (dark, mobile)        │      (public URL)
        │                                                                 │
        └─────────────────────────────────────────────────────────────────┘
```

The visitor just loads a fast static page (`index.html` + `data.json`); all filtering, search and distance sorting happen in the browser. Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Project layout

```
subtitled-cinema/
├── build/                    # the pipeline (Python)
│   ├── fetch_pages.py        # download source pages -> .cache/pages/
│   ├── parse_ylc.py          # parse both page layouts -> normalised screenings
│   ├── cinema_meta.py        # hand-curated coordinates for "nearest"
│   └── build_site.py         # merge + dedupe -> public/data.json
├── public/                   # the site GitHub Pages serves
│   ├── index.html
│   ├── assets/{styles.css, app.js}
│   └── data.json             # generated
├── tests/
│   ├── test_parse.py         # 24 parser + pipeline unit tests
│   ├── test_ui.py            # 13 Playwright UI tests (+ screenshots)
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
make test        # 37 tests (parser + Playwright UI)
```

No build step for the site itself — `public/` is plain static files.

## Testing

- **`tests/test_parse.py`** — showtime parsing (carry-forward times, year rollover), accessibility/certificate extraction, chain detection, both page layouts, and the merge/dedupe pipeline.
- **`tests/test_ui.py`** — drives the real page in headless Chromium: renders, no mobile overflow, every filter (day/search/cinema/access), group-by, nearest-with-distance, and links. Expected counts are computed in Python by mirroring the JS rules, so they're not brittle magic numbers. Writes screenshots to `tests/screenshots/`.

## Decisions at a glance

| Decision | Choice |
|---|---|
| Audience | Public alternative to yourlocalcinema.com |
| Hosting | GitHub Pages (free, static) |
| Stack | Python build pipeline · vanilla static frontend (no framework) |
| Updates | Automatic via GitHub Actions, **every 6 hours** |
| Launch area | Greater Manchester (Manchester/Stockport/Altrincham/Didsbury); built to add cities as data |
| What counts | Subtitled/captioned **+** audio-described; English subs **&** foreign-with-English-subs |
| Design | Dark, mobile-first |
| On scrape failure | Keep last data, stamp "last checked", link out (fetch never wipes cache) |

## Roadmap

- **V1 (now):** source from yourlocalcinema's four city pages — fast to ship, immediately better UX.
- **V2:** scrape the cinema chains directly (Odeon/Vue/Cineworld JSON APIs) for exact **per-showing booking deep-links** and independence from YLC. See [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md).
- Real posters/runtimes via a film metadata source; more cities.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline, `data.json` schema, frontend, testing.
- [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) — where the data comes from, the venues found, and the path to direct scraping.
