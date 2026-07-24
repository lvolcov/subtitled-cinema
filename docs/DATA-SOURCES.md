# Data sources

## V1 (current): yourlocalcinema.com aggregation

The site currently sources from **four yourlocalcinema.com city pages** — the same data Lucas already uses, but auto-refreshed and presented far better:

| Page | URL |
|---|---|
| Manchester | https://yourlocalcinema.com/manchester.html |
| Stockport | https://yourlocalcinema.com/stockport.html |
| Altrincham | https://yourlocalcinema.com/altrincham.html |
| Didsbury | https://yourlocalcinema.com/didsbury.html |

These are static, hand-maintained pages (no API) that aggregate subtitled/captioned listings cinemas send to YLC. We fetch, parse and re-present them. This was chosen for V1 because it ships a genuinely better product immediately without wiring up every cinema.

### Venues found (12 with subtitled screenings)

| Cinema | Chain | Area | From page(s) |
|---|---|---|---|
| Manchester Trafford Odeon | Odeon | Manchester | manchester |
| Manchester Great Northern Odeon | Odeon | Manchester | manchester |
| Manchester Quayside Vue | Vue | Manchester | manchester |
| Manchester Printworks Vue | Vue | Manchester | manchester |
| Manchester Home | HOME | Manchester | manchester |
| Manchester Everyman | Everyman | Manchester | manchester |
| Stockport Light | Light | Stockport | manchester + stockport |
| Wilmslow Rex | Rex | Wilmslow | stockport |
| Altrincham Vue | Vue | Altrincham | altrincham |
| Altrincham Everyman | Everyman | Altrincham | altrincham |
| Knutsford Curzon | Curzon | Knutsford | altrincham |
| Didsbury Cineworld | Cineworld | Didsbury | didsbury |

Venues the source lists as having **no** subtitled screenings (e.g. Manchester The Block, Backyard, Cultplex, Heaton Moor Savoy, Macclesfield Cinemac, Marple Regent) are parsed out and dropped until they have shows.

### Notes on the data

- **Audio-described:** the accessibility parser tags and badges AD screenings, but these YLC pages are subtitled-first — there are currently **0** AD screenings in the feed. The feature is unit-tested with a fixture and will light up automatically if the source starts listing AD shows.
- **Foreign-language with English subtitles:** well represented (~32 screenings, all HOME arthouse — e.g. *Portrait of a Lady on Fire*, *Nostalghia*, *Kiki's Delivery Service*). Badged "Orig + subs".
- **Booking links** currently point at the **chain website** (the source doesn't expose per-showing links reliably). Exact per-showing deep-links are a V2 goal.
- **Coordinates** are hand-curated in `build/cinema_meta.py` (venue-level, approximate) to power "nearest". All 12 current venues have coordinates.

## Reliability & the "last checked" contract

- `fetch_pages.py` validates each download (size + expected markup) and **never overwrites a good cached copy with a bad fetch**.
- Every venue in the UI shows a `last_checked` date and links out, so a stale entry is visible and verifiable rather than silently wrong.
- `.cache/pages/*.html` is committed as a working fallback snapshot; CI regenerates it every run.

## V2 (roadmap): direct cinema scraping

To get **exact per-showing booking deep-links** and remove the dependency on YLC, scrape the cinemas' own booking systems, which expose accessibility flags:

| Source | Covers (current venues) | Notes |
|---|---|---|
| **Odeon** JSON booking API | Trafford, Great Northern | one adapter, both venues |
| **Vue** JSON showtimes | Quayside, Printworks, Altrincham | one adapter, accessibility flag |
| **Cineworld/Picturehouse** API | Didsbury | "subtitled" attribute |
| **HOME** site scrape | Manchester HOME | main foreign-language-with-subs source |
| Independents | Everyman, Light, Curzon, Rex | per-site HTML scrapers, more fragile |

Build order: Odeon → Vue → HOME → Cineworld → independents. Each adapter must emit the same normalised `Screening` schema the builder already consumes, so the frontend and `data.json` don't change.
