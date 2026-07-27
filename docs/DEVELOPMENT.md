# Development guide

How to set up, run, test, and extend `subtitled-cinema` locally. Pair this with
[`ARCHITECTURE.md`](ARCHITECTURE.md) (how it works) and
[`DATA-SOURCES.md`](DATA-SOURCES.md) (where the data comes from).

---

## 1. Prerequisites

- **Python 3.10+** (CI uses 3.12).
- **pip** for two dependencies:
  - `beautifulsoup4` — HTML parsing (build pipeline).
  - `playwright` — headless-browser UI tests (test-only).
- A **Chromium** for Playwright (downloaded by `playwright install`).

No Node.js is needed — the frontend is plain static files and the pipeline is
Python.

## 2. First-time setup

```bash
make install
# equivalent to:
#   python3 -m pip install --user beautifulsoup4 playwright
#   python3 -m playwright install chromium
```

## 3. The everyday commands (`make`)

| Command | What it does |
|---|---|
| `make fetch` | Download fresh source pages → `.cache/pages/*.html`. |
| `make build` | Parse + merge + enrich → `public/data.json`. Offline; uses the poster cache. |
| `make all` | `fetch` then `build`. |
| `make serve` | Serve `public/` at http://localhost:8000. |
| `make test` | Run all 45 tests (parser + Playwright UI). |
| `make test-parse` | Just the 24 Python parser/pipeline tests (fast, no browser). |
| `make test-ui` | Just the 21 Playwright UI tests. |

Refresh posters explicitly (network) — cache is committed, so this is only
needed when films change:

```bash
python3 -m build.posters
```

## 4. Typical local loop

```bash
make all          # get fresh data
make serve        # open http://localhost:8000 in a browser
# edit public/assets/{app.js,styles.css} or build/*.py
# refresh the browser; re-run `make build` if you changed the pipeline
make test         # before committing
```

The site is static, so editing `app.js`/`styles.css` just needs a browser
refresh — no build step.

---

## 5. Project layout (what lives where)

```
subtitled-cinema/
├── build/                    # Python build pipeline
│   ├── fetch_pages.py        # download YLC city pages (validates; never wipes cache)
│   ├── parse_ylc.py          # parse both page layouts → Cinema/Film/Screening (pure)
│   ├── posters.py            # resolve a poster per film → build/poster_cache.json
│   ├── cinema_meta.py        # hand-curated {slug: (lat,lng)} for "nearest"
│   ├── build_site.py         # merge + dedupe + enrich → public/data.json
│   └── poster_cache.json     # committed poster cache (CI refreshes it)
├── public/                   # exactly what GitHub Pages serves
│   ├── index.html
│   ├── assets/{styles.css, app.js, icon.svg}
│   ├── manifest.webmanifest
│   └── data.json             # GENERATED — do not hand-edit
├── tests/
│   ├── test_parse.py         # 24 parser + pipeline unit tests
│   ├── test_ui.py            # 21 Playwright UI tests
│   └── screenshots/          # written by the UI tests (git-ignored)
├── .cache/pages/*.html       # committed source snapshot (CI refreshes it)
├── .github/workflows/        # build.yml (deploy), ci.yml (tests)
├── docs/                     # ARCHITECTURE, DATA-SOURCES, DEVELOPMENT, UX-AUDIT
├── Makefile, requirements.txt, CHANGELOG.md, README.md
```

---

## 6. Common tasks (recipes)

### 6.1 Add a new city

Cities are data, not code:

1. Add the YLC page name to `CITIES` in `build/fetch_pages.py` (e.g. add
   `"bolton"`). `build/build_site.py` imports the same list, so one edit covers
   both fetch and build. (Confirm the page exists first — `curl -sI
   https://yourlocalcinema.com/bolton.html` should 200; YLC only publishes pages
   where it has data.)
2. `make fetch` to pull it, then inspect the parse:
   ```bash
   python3 -c "from datetime import date; from build.parse_ylc import parse_page; \
   print([(c.name,c.screening_count) for c in \
   parse_page(open('.cache/pages/bolton.html').read(),'bolton',date.today())])"
   ```
3. Add coordinates for any *new* venues in `build/cinema_meta.py` (see 6.2).
4. `make build && make test`.

### 6.2 Add coordinates for a venue (so "nearest" works)

`build/cinema_meta.py` maps the **name slug** → `(lat, lng)`. The slug is the
cinema name lowercased with non-alphanumerics turned to hyphens (what
`build_site.slugify()` produces, and also the cinema's `id` in `data.json`).

```python
COORDS = {
    "bolton-light": (53.5780, -2.4283),
    # ...
}
```

Find the slug by building and reading `data.json`, or:
```bash
python3 -c "from build.build_site import slugify; print(slugify('Bolton Light'))"
```

### 6.3 A poster is wrong or missing

Posters are cached in `build/poster_cache.json` keyed by `source_url`.

- To re-resolve everything: delete the file and run `python3 -m build.posters`.
- To force a single film: remove its `source_url` key from the cache and re-run.
- If a poster is *wrong because several films share one YLC page*, that's handled
  automatically — the builder blanks any poster used by >1 distinct film. If you
  see a wrong shared poster, check that the films really do map to the same
  `source_url`.
- The extraction rule lives in `build/posters.py :: _is_poster_img()` — the
  poster is the `<img alt="">` with a bare-filename `src` that isn't chrome/logo.

### 6.4 Change the refresh cadence

Edit the cron in `.github/workflows/build.yml` (`schedule: - cron: "0 */6 * * *"`).

### 6.5 Add or change a frontend feature

All client code is `public/assets/app.js` (vanilla, no framework). Keep the
`data.json` contract stable (see ARCHITECTURE §3). If you add UI that tests
should cover, remember the **test hooks**: `window.__DATA__`, `window.__NOW__`,
`window.__COORDS__`.

---

## 7. Conventions

- **Parser stays pure.** `parse_ylc.py` takes an explicit `ref_date` and does no
  I/O — so it's deterministic and unit-testable. Don't add network or `date.today()`
  inside it.
- **Parser = raw facts; builder = enrichment.** Slugs, IMDb links, coordinates,
  posters, dedupe, sorting all live in `build_site.py`, never in a per-page path.
- **`build()` is offline.** It reads the poster cache; it never fetches. Only
  `fetch_pages.py` and `posters.py` touch the network.
- **Times are local wall-clock.** `starts_at` is tz-naive; the frontend parses it
  component-wise. Never introduce `new Date(isoString)` in `app.js`.
- **Don't hand-edit generated files** (`public/data.json`, `build/poster_cache.json`).

---

## 8. Testing notes & gotchas

- **UI tests need a running static server + a browser.** `test_ui.py` starts its
  own `http.server` in `setUpModule` and launches Chromium; you just run
  `make test-ui`.
- **Expected counts are computed, not hardcoded.** `test_ui.py` mirrors the JS
  visibility rules in Python (`expected_visible()`), so tests track the data
  instead of breaking every time the source changes.
- **`hidden` + `display`:** an element with both a `display` rule and the
  `hidden` attribute needs an explicit `[hidden]{display:none}` — otherwise the
  `display` wins and the element stays visible. (This bit us with the modal
  overlay intercepting clicks; there's now `.modal-root[hidden]{display:none}`.)
- **When waiting for something to *hide* in Playwright**, use
  `wait_for_selector(sel, state="attached")` — the default `"visible"` will time
  out on a hidden element.
- **Foreground `sleep` may be blocked in some shells** when scripting Playwright
  runs — start the server in the background and poll for readiness (the test
  suite already does this).

---

## 9. Deployment

Pushing to `main` triggers `build.yml`, which fetches, resolves posters, builds,
and deploys to GitHub Pages. You can also trigger it manually
("Run workflow" / `workflow_dispatch`). See ARCHITECTURE §7. Nothing else is
required — no manual publish step.
