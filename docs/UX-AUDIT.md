# UX & accessibility audit

A record of the usability/accessibility review that drove the v2 release, the
findings, and exactly what was implemented in response. Kept so future changes
have a baseline to measure against.

---

## Method

- **Automated a11y:** [axe-core](https://github.com/dequelabs/axe-core) 4.10 run
  against the rendered page (mobile viewport) via Playwright.
- **Console/error hygiene:** captured `console.error` + `pageerror` during load
  and interaction.
- **Interaction & layout:** scripted Playwright scenarios across mobile (390px)
  and desktop (1100px) — filters, keyboard navigation, focusability, long-title
  overflow, horizontal-overflow checks.
- **Heuristic review:** against the project's core audience (people who rely on
  subtitles) and the two explicitly requested features (real posters; pick a
  film → see every cinema showing it).

## Baseline (before v2)

- **axe violations: 0.** Semantic HTML, labelled controls, and visible focus
  styles gave a clean automated baseline.
- **Console errors: 0.**
- **Gaps were functional, not automated-catchable:** no posters, no way to pick a
  film and see all its cinemas, cards weren't interactive, no shareable state,
  coarse day filter only, no active-filter feedback, no cinema/directions view,
  "nearest" didn't persist, no loading state, not installable, poor link
  previews.

---

## Findings → what shipped

| # | Finding | Severity | Implemented |
|---|---|---|---|
| 1 | Generic initials only; no real artwork | High | **Real movie posters** per film (from YLC film pages, cached), lazy-loaded, fade-in, graceful fallback tile, `onerror` removes broken images. |
| 2 | Couldn't pick a film to see all its cinemas | High (requested) | **Film dialog:** tap a film → poster + "showing at N cinemas · M screenings" + every cinema, distance-sorted, each showtime a booking link. |
| 3 | Cards weren't interactive (`cursor:auto`) | Medium | Poster, film title and cinema name are all buttons that open detail dialogs. |
| 4 | No way to explore a venue / get directions | Medium | **Cinema dialog:** all of a venue's screenings grouped by day + "Open in Maps". |
| 5 | Nothing shareable/bookmarkable | Medium | **URL state** — filters + open dialog serialised to the query string; back button closes dialogs; `popstate` re-renders. |
| 6 | Only All/Today/Tomorrow/Week | Medium | **Date strip** — plus a chip per upcoming day that has screenings. |
| 7 | No feedback on active filters | Medium | **Removable filter chips + "Clear all"**, and per-group counts. |
| 8 | "Nearest" didn't persist; no distance context | Low | Coordinates persisted to `localStorage`; distances shown on cinema headers; graceful denial. |
| 9 | No loading state | Low | **Skeleton** while `data.json` loads. |
| 10 | Not installable; poor social previews | Low | **PWA** (`manifest.webmanifest` + SVG icon + `theme-color`) and **Open Graph / Twitter** meta. |
| 11 | Captioned vs foreign-subtitle wording unclear | Low (audience-relevant) | English subtitled films badged **"Captioned"**; foreign-language films badged **"Subtitles"**. |
| 12 | Long lists hard to navigate | Low | **Back-to-top** button; sticky filter bar. |

### New-feature accessibility (added carefully, re-audited)

Because the dialogs are new interactive surfaces, they were built to preserve the
clean a11y baseline:

- `role="dialog" aria-modal="true"` with an `aria-labelledby` title.
- **Focus trap** (Tab cycles within the dialog), **Esc** and overlay-click close,
  and **focus restoration** to the element that opened it.
- Posters are decorative next to a visible title, so `alt=""` (avoids
  double-announcement); the film dialog's context is conveyed by the heading.
- Skip-link to the listings; reduced-motion honoured (`prefers-reduced-motion`).

### Post-v2 verification

- **axe violations: 0** (maintained).
- **Console errors: 0**, including after opening/closing dialogs.
- **No horizontal overflow** at 390px.
- Verified on the live production URL: film dialog renders "The Odyssey · showing
  subtitled at 12 cinemas · 36 screenings"; posters load; manifest served.

---

## A real bug the audit caught

`.modal-root { display: grid }` **overrode the `hidden` attribute**, so the modal
overlay stayed in the layout and silently **intercepted every click** on the page
(clicks resolved to the invisible overlay, not the cards). Fixed with an explicit
`.modal-root[hidden] { display: none }`. This is exactly the class of regression
the expanded UI tests (Esc-to-close, open-dialog, zero-console-errors) now guard.

---

## Not addressed (and why)

- **Audio-described listings** — feature is built and tested, but the source
  currently lists 0 AD screenings; nothing to display yet.
- **Runtimes / synopses / resolved IMDb IDs** — not in the source; deferred to a
  film-metadata source in V2 (IMDb links are honest "search" links meanwhile).
- **Node-runtime deprecation warning in Actions logs** — a GitHub platform notice
  (actions forced onto Node 24), not something fixable from this repo.
