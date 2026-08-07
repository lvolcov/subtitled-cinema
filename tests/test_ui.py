"""
Playwright UI tests for the frontend. Run: python3 -m unittest tests.test_ui -v

Serves a throwaway mirror of public/ over http (never public/ itself — see
_serve_root), injects a deterministic dataset + fixed "now" via
window.__DATA__ / window.__NOW__ (and window.__COORDS__ where a test needs the
"near me" path), then asserts the page renders and every control behaves.

The page is the rail + slim-bar design:
  • a film rail up top (poster + "N cinemas" count) is the primary way in;
  • a slim sticky bar holds grouping (Cinema / Film / Day), search and a
    "Filters" button that opens a drawer with the date strip, a grouped
    multi-select cinema picker, access + sort.
Expected counts are computed in Python by mirroring the JS visibility rules, so
the assertions aren't brittle magic numbers. Screenshots land in
tests/screenshots/ for visual confirmation.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build import build_site

try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:
    HAVE_PW = False

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
NOW = datetime(2026, 7, 28, 12, 0, 0)          # fixed "current time"
NOW_ISO = NOW.isoformat()
REF = date(2026, 7, 24)
PAST_MIN = 40                                   # app drops screenings >40m past
SHOTS = ROOT / "tests" / "screenshots"
CENTRE = {"lat": 53.4808, "lng": -2.2426}       # Manchester Piccadilly-ish

_server = None
_pw = None
_browser = None
_srvdir = None
DATA = None


def _flat(data):
    out = []
    for c in data["cinemas"]:
        for s in c["screenings"]:
            out.append({**s, "cinema_id": c["id"], "chain": c["chain"],
                        "cinema_name": c["name"], "region": c["region"],
                        "lat": c["lat"], "lng": c["lng"]})
    return out


def _dt(iso):
    return datetime.fromisoformat(iso)


def _future(s):
    return _dt(s["starts_at"]) >= NOW - timedelta(minutes=PAST_MIN)


def expected_visible(day="all", cinemas=None, region=None):
    """Mirror of the JS visibility logic for cross-checking."""
    n = 0
    for s in _flat(DATA):
        if not _future(s):
            continue
        if day != "all" and _dt(s["starts_at"]).strftime("%Y-%m-%d") != day:
            continue
        if cinemas and s["cinema_id"] not in cinemas:
            continue
        if region and s["region"] != region:
            continue
        n += 1
    return n


def _cinemas_in(region):
    return sorted({c["id"] for c in DATA["cinemas"] if c["region"] == region})


def _cinemas_by_chain(chain):
    return sorted({s["cinema_id"] for s in _flat(DATA) if s["chain"] == chain})


def _serve_root():
    """A throwaway mirror of public/ to serve the tests from.

    The tests need a data.json matching their pinned town subset, but public/
    data.json is the real 500+ venue site payload that gets committed and
    deployed — building the test subset over it silently guts production data.
    So: symlink public/'s files into a temp dir and write the test data.json
    there instead. Never write into public/ from a test.
    """
    tmp = Path(tempfile.mkdtemp(prefix="subcin-ui-"))
    for item in (ROOT / "public").iterdir():
        if item.name != "data.json":
            (tmp / item.name).symlink_to(item)
    (tmp / "data.json").write_text(
        json.dumps(DATA, indent=2, ensure_ascii=False), encoding="utf-8")
    return tmp


def setUpModule():
    global _server, _pw, _browser, DATA, _srvdir
    # Pin the UI tests to a small, stable subset of towns so assertions stay
    # deterministic (the full national set has, e.g., a cinema literally named
    # "St Albans Odyssey" that would break a search-for-"odyssey" test) and fast.
    build_site.CITIES = ["manchester", "stockport", "altrincham", "didsbury"]
    DATA = build_site.build(ref_date=REF, now=datetime(2026, 7, 24, 9, 0))
    _srvdir = _serve_root()
    _server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=str(_srvdir),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            urlopen(BASE + "/index.html", timeout=1); break
        except Exception:
            time.sleep(0.1)
    if HAVE_PW:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch()
    SHOTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    if _browser: _browser.close()
    if _pw: _pw.stop()
    if _server: _server.terminate(); _server.wait()
    if _srvdir: shutil.rmtree(_srvdir, ignore_errors=True)


@unittest.skipUnless(HAVE_PW, "playwright not installed")
class UI(unittest.TestCase):
    def _page(self, w=390, h=844, query="", coords=None):
        pg = _browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg._console_errors = []
        pg.on("console", lambda m: pg._console_errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: pg._console_errors.append(str(e)))
        init = (f"window.__NOW__={json.dumps(NOW_ISO)};"
                f"window.__DATA__={json.dumps(DATA)};")
        if coords:
            init += f"window.__COORDS__={json.dumps(coords)};"
        pg.add_init_script(init)
        pg.goto(BASE + "/index.html" + query)
        pg.wait_for_selector("#filmRail .rail-item")
        pg.wait_for_selector(".card")
        return pg

    def _summary_count(self, pg):
        return int(pg.text_content("#resultSummary").split()[0])

    def _open_filters(self, pg):
        if pg.get_attribute("#filtersPanel", "hidden") is not None:
            pg.click("#filtersBtn")
        pg.wait_for_selector("#filtersPanel:not([hidden])")

    def _open_cinema_menu(self, pg):
        self._open_filters(pg)
        pg.click("#cinemaBtn")
        pg.wait_for_selector("#cinemaMenu:not([hidden])")

    # ---- render ----
    def test_rail_and_cards_render(self):
        pg = self._page()
        self.assertGreater(pg.locator("#filmRail .rail-item").count(), 3)
        self.assertGreater(pg.locator(".card").count(), 15)
        self.assertGreater(pg.locator(".group").count(), 5)
        pg.close()

    def test_rail_shows_cinema_counts(self):
        pg = self._page()
        # every film tile (not the "All films" tile) carries a "N cinema(s)" badge
        counts = pg.eval_on_selector_all(
            "#filmRail .rail-item:not(.all) .rail-poster .cnt",
            "els => els.map(e => e.textContent)")
        self.assertGreater(len(counts), 0)
        self.assertTrue(all("cinema" in c for c in counts))
        pg.close()

    def test_stat_pill_shows_totals(self):
        pg = self._page()
        txt = pg.inner_text("#statPill")
        self.assertIn("cinemas", txt)
        self.assertIn("screenings", txt)
        pg.close()

    def test_no_horizontal_overflow_mobile(self):
        pg = self._page(390, 844)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        iw = pg.evaluate("window.innerWidth")
        self.assertLessEqual(sw, iw, "page overflows horizontally on mobile")
        pg.close()

    def test_frozen_bar_is_slim(self):
        # the whole point of the slim-bar redesign: the sticky area must not eat
        # the screen. nav + controls-shell together stay well under half of a
        # 844px-tall mobile viewport.
        pg = self._page(390, 844)
        frozen = pg.evaluate(
            "() => ['.nav','.controls-shell']"
            ".reduce((h,s)=>h+(document.querySelector(s)?.offsetHeight||0),0)")
        self.assertLess(frozen, 200, f"sticky controls too tall ({frozen}px)")
        pg.close()

    def test_default_visible_matches_expected(self):
        pg = self._page()
        self.assertEqual(self._summary_count(pg), expected_visible("all"))
        pg.close()

    # ---- grouping ----
    def test_group_by_film(self):
        pg = self._page()
        pg.click('.seg-btn[data-group="film"]')
        headers = pg.eval_on_selector_all(
            ".group .g-name", "els => els.map(e => e.textContent.trim())")
        self.assertIn("The Odyssey", headers)
        pg.close()

    def test_group_by_day(self):
        pg = self._page()
        pg.click('.seg-btn[data-group="time"]')
        self.assertGreater(pg.locator(".group").count(), 1)
        # summary should describe days
        self.assertIn("day", pg.text_content("#resultSummary"))
        pg.close()

    # ---- search ----
    def test_search_narrows_results(self):
        pg = self._page()
        full = self._summary_count(pg)
        pg.fill("#search", "odyssey")
        narrowed = self._summary_count(pg)
        self.assertLess(narrowed, full)
        self.assertGreater(narrowed, 0)
        titles = pg.eval_on_selector_all(
            ".card .card-title", "els => els.map(e => e.textContent.toLowerCase())")
        self.assertTrue(all("odyssey" in t for t in titles))
        pg.close()

    # ---- cinema multi-select ----
    def test_cinema_single_select(self):
        pg = self._page()
        self._open_cinema_menu(pg)
        pg.click('label.ms-opt:has(input[value="manchester-home"])')
        names = pg.eval_on_selector_all(
            ".group .g-name", "els => [...new Set(els.map(e => e.textContent.trim()))]")
        self.assertEqual(names, ["Manchester Home"])
        self.assertEqual(pg.inner_text("#cinemaBtn"), "Manchester Home")
        pg.close()

    def test_cinema_chain_group_selects_all(self):
        vue = _cinemas_by_chain("Vue")
        self.assertGreater(len(vue), 1)
        pg = self._page()
        self._open_cinema_menu(pg)
        pg.locator('.ms-chain', has_text="Vue").locator("input[data-chain]").check()
        # button summarises the whole chain
        self.assertEqual(pg.inner_text("#cinemaBtn"), f"{len(vue)} cinemas")
        # every rendered group is a Vue venue
        vue_names = {c["name"] for c in DATA["cinemas"] if c["id"] in vue}
        shown = pg.eval_on_selector_all(
            ".group .g-name", "els => [...new Set(els.map(e => e.textContent.trim()))]")
        self.assertTrue(shown and all(n in vue_names for n in shown))
        pg.close()

    def test_deep_link_cinemas_param(self):
        pg = self._page(query="?cinemas=manchester-trafford-odeon")
        names = pg.eval_on_selector_all(
            ".group .g-name", "els => [...new Set(els.map(e => e.textContent.trim()))]")
        self.assertEqual(names, ["Manchester Trafford Odeon"])
        # drawer auto-opens so the applied filter is visible
        self.assertIsNone(pg.get_attribute("#filtersPanel", "hidden"))
        self.assertEqual(self._summary_count(pg),
                         expected_visible(cinemas=["manchester-trafford-odeon"]))
        pg.close()

    # ---- region ----
    def test_region_greater_manchester_is_pinned_first(self):
        pg = self._page()
        opts = pg.eval_on_selector_all(
            "#regionFilter option", "els => els.map(e => e.textContent)")
        self.assertEqual(opts[0], "All of the UK")
        self.assertEqual(opts[1], "Greater Manchester")
        pg.close()

    def test_region_filter_narrows_the_list(self):
        gm = _cinemas_in("Greater Manchester")
        other = _cinemas_in("North West")
        self.assertTrue(gm and other, "fixture needs two regions")
        pg = self._page()
        full = self._summary_count(pg)
        pg.select_option("#regionFilter", "Greater Manchester")
        narrowed = self._summary_count(pg)
        self.assertLess(narrowed, full)
        self.assertEqual(narrowed, expected_visible(region="Greater Manchester"))
        # nothing from another region survives
        gm_names = {c["name"] for c in DATA["cinemas"] if c["id"] in gm}
        shown = pg.eval_on_selector_all(
            ".group .g-name", "els => [...new Set(els.map(e => e.textContent.trim()))]")
        self.assertTrue(shown and all(n in gm_names for n in shown))
        # and it's advertised as an active filter + in the URL
        chips = pg.inner_text("#activeChips")
        self.assertIn("Greater Manchester", chips)
        self.assertIn("region=Greater+Manchester", pg.url)
        pg.close()

    def test_region_scopes_the_cinema_picker_and_rail(self):
        nw = _cinemas_in("North West")
        pg = self._page()
        pg.select_option("#regionFilter", "North West")
        self._open_cinema_menu(pg)
        ids = pg.eval_on_selector_all(
            "#cinemaMenu .ms-opt input", "els => els.map(e => e.value)")
        self.assertEqual(sorted(ids), nw)
        # the film rail only offers films actually showing in that region
        rail = pg.eval_on_selector_all(
            "#filmRail .rail-item:not(.all)", "els => els.map(e => e.dataset.film)")
        in_region = {s["film_id"] for s in _flat(DATA)
                     if _future(s) and s["region"] == "North West"}
        self.assertTrue(rail)
        self.assertEqual(set(rail), in_region)
        pg.close()

    def test_region_deep_link_and_clearing(self):
        pg = self._page(query="?region=North+West")
        self.assertEqual(pg.eval_on_selector("#regionFilter", "e => e.value"), "North West")
        self.assertEqual(self._summary_count(pg), expected_visible(region="North West"))
        # the region chip clears it, restoring the whole country
        pg.click("#activeChips .fchip")
        self.assertEqual(self._summary_count(pg), expected_visible("all"))
        self.assertEqual(pg.eval_on_selector("#regionFilter", "e => e.value"), "")
        pg.close()

    def test_region_is_remembered_between_visits(self):
        pg = self._page()
        pg.select_option("#regionFilter", "Greater Manchester")
        self.assertEqual(pg.evaluate("localStorage.getItem('sc-region')"), "Greater Manchester")
        pg.goto(BASE + "/index.html")           # a fresh visit, no query string
        pg.wait_for_selector(".card")
        self.assertEqual(pg.eval_on_selector("#regionFilter", "e => e.value"), "Greater Manchester")
        self.assertEqual(self._summary_count(pg), expected_visible(region="Greater Manchester"))
        pg.evaluate("localStorage.removeItem('sc-region')")
        pg.close()

    # ---- access + near ----
    def test_access_filter_audio_described(self):
        pg = self._page()
        self._open_filters(pg)
        pg.select_option("#accessFilter", "audio-described")
        count = pg.locator(".card").count()
        if count:
            ad = pg.locator(".card .badge.ad").count()
            self.assertEqual(ad, count)
        pg.close()

    def test_near_me_sorts_and_shows_distance(self):
        pg = self._page(coords=CENTRE)
        self.assertEqual(pg.get_attribute("#nearBtn", "aria-pressed"), "true")
        # cinema group heads carry a distance chip when sorted by nearest
        self.assertGreater(pg.locator(".group-head .g-dist").count(), 0)
        pg.close()

    # ---- chips ----
    def test_filter_chips_and_clear_all(self):
        pg = self._page()
        pg.fill("#search", "odyssey")
        self._open_cinema_menu(pg)
        # drive the checkbox's change handler directly — the popover item can sit
        # under the sticky bar after a search, tripping Playwright's hit-testing.
        pg.eval_on_selector(
            '.ms-opt input[value="manchester-home"]',
            "el => { el.checked = true; el.dispatchEvent(new Event('change', {bubbles:true})); }")
        self.assertGreaterEqual(pg.locator("#activeChips .fchip").count(), 2)
        pg.keyboard.press("Escape")  # close the cinema popover so it can't overlay the chips
        pg.wait_for_selector("#cinemaMenu[hidden]", state="attached")
        pg.click("#activeChips .fchip.clear")
        self.assertEqual(pg.locator("#activeChips .fchip").count(), 0)
        self.assertEqual(pg.eval_on_selector("#search", "e=>e.value"), "")
        self.assertEqual(self._summary_count(pg), expected_visible("all"))
        pg.close()

    # ---- film rail selection ----
    def test_rail_select_shows_banner(self):
        pg = self._page()
        pg.click('#filmRail .rail-item[data-film="the-odyssey"]')
        pg.wait_for_selector("#filmBanner:not([hidden])")
        self.assertIn("The Odyssey", pg.inner_text("#filmBanner"))
        self.assertIn("film=the-odyssey", pg.url)
        pg.close()

    def test_deep_link_opens_film(self):
        pg = self._page(query="?film=the-odyssey")
        self.assertIsNone(pg.get_attribute("#filmBanner", "hidden"))
        self.assertIn("The Odyssey", pg.inner_text("#filmBanner"))
        pg.close()

    # ---- links ----
    def test_booking_links_present(self):
        pg = self._page()
        hrefs = pg.eval_on_selector_all(
            ".showtimes a.st", "els => els.map(e => e.getAttribute('href'))")
        self.assertGreater(len(hrefs), 0)
        self.assertTrue(all(h and h.startswith("http") for h in hrefs))
        pg.close()

    # ---- robustness ----
    def test_no_console_errors(self):
        pg = self._page()
        pg.click('#filmRail .rail-item[data-film="the-odyssey"]')
        pg.wait_for_selector("#filmBanner:not([hidden])")
        pg.click("#clearFilm")
        self.assertEqual(pg._console_errors, [])
        pg.close()

    def test_screenshots(self):
        for name, w, h in [("ui-mobile", 390, 844), ("ui-desktop", 1100, 1000)]:
            pg = self._page(w, h)
            pg.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
            pg.close()
        self.assertTrue((SHOTS / "ui-mobile.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
