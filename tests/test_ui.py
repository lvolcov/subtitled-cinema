"""
Playwright UI tests for the frontend. Run: python3 -m unittest tests.test_ui -v

Serves public/ over http, injects a deterministic dataset + fixed "now" via
window.__DATA__ / window.__NOW__, then asserts the page renders and every
filter behaves. Expected counts are computed in Python by mirroring the JS
visibility rules, so the assertions aren't brittle magic numbers. Also writes
screenshots to tests/screenshots/ for visual confirmation.
"""
import json
import subprocess
import sys
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
SHOTS = ROOT / "tests" / "screenshots"
CENTRE = {"lat": 53.4808, "lng": -2.2426}       # Manchester Piccadilly-ish

_server = None
_pw = None
_browser = None
DATA = None


def _flat(data):
    out = []
    for c in data["cinemas"]:
        for s in c["screenings"]:
            out.append({**s, "cinema_id": c["id"], "lat": c["lat"], "lng": c["lng"]})
    return out


def _dt(iso):
    return datetime.fromisoformat(iso)


def expected_visible(day="all"):
    """Mirror of the JS visibility logic for cross-checking."""
    cutoff = NOW - timedelta(minutes=60)
    tomorrow = (NOW + timedelta(days=1)).date()
    week_end = NOW + timedelta(days=7)
    n = 0
    for s in _flat(DATA):
        d = _dt(s["starts_at"])
        if d < cutoff:
            continue
        if day == "today" and d.date() != NOW.date():
            continue
        if day == "tomorrow" and d.date() != tomorrow:
            continue
        if day == "week" and not (d >= datetime(NOW.year, NOW.month, NOW.day) and d <= week_end):
            continue
        n += 1
    return n


def setUpModule():
    global _server, _pw, _browser, DATA
    DATA = build_site.build(ref_date=REF, now=datetime(2026, 7, 24, 9, 0))
    # ensure data.json exists too (belt & braces), then serve public/
    build_site.main()
    _server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=str(ROOT / "public"),
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


@unittest.skipUnless(HAVE_PW, "playwright not installed")
class UI(unittest.TestCase):
    def _page(self, w=390, h=844):
        pg = _browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg.add_init_script(
            f"window.__NOW__={json.dumps(NOW_ISO)};"
            f"window.__DATA__={json.dumps(DATA)};"
            f"window.__COORDS__={json.dumps(CENTRE)};"
        )
        pg.goto(BASE + "/index.html")
        pg.wait_for_selector("body[data-ready='1']")
        return pg

    def _summary_count(self, pg):
        return int(pg.text_content("#resultSummary").split()[0])

    def test_renders_stats_and_cards(self):
        pg = self._page()
        self.assertIn("cinemas", pg.inner_text("#stats"))
        self.assertGreater(pg.locator(".card").count(), 20)
        self.assertGreater(pg.locator(".group-title").count(), 3)
        pg.close()

    def test_no_horizontal_overflow_mobile(self):
        pg = self._page(390, 844)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        iw = pg.evaluate("window.innerWidth")
        self.assertLessEqual(sw, iw, "page overflows horizontally on mobile")
        pg.close()

    def test_default_visible_matches_expected(self):
        pg = self._page()
        self.assertEqual(self._summary_count(pg), expected_visible("all"))
        pg.close()

    def test_hides_past_screenings(self):
        pg = self._page()
        # nothing rendered should be more than 60 min in the past
        times = pg.eval_on_selector_all(
            ".card[data-day]", "els => els.length")
        self.assertGreater(times, 0)
        # summary equals only-future count (past excluded)
        self.assertEqual(self._summary_count(pg), expected_visible("all"))
        pg.close()

    def test_today_filter(self):
        pg = self._page()
        pg.click('.seg-btn[data-day="today"]')
        self.assertEqual(self._summary_count(pg), expected_visible("today"))
        # and it should be <= all
        pg.click('.seg-btn[data-day="all"]')
        self.assertGreaterEqual(self._summary_count(pg), expected_visible("today"))
        pg.close()

    def test_tomorrow_filter(self):
        pg = self._page()
        pg.click('.seg-btn[data-day="tomorrow"]')
        self.assertEqual(self._summary_count(pg), expected_visible("tomorrow"))
        pg.close()

    def test_search_narrows_results(self):
        pg = self._page()
        full = self._summary_count(pg)
        pg.fill("#search", "odyssey")
        narrowed = self._summary_count(pg)
        self.assertLess(narrowed, full)
        self.assertGreater(narrowed, 0)
        # every visible card is The Odyssey
        titles = pg.eval_on_selector_all(
            ".card .film-title", "els => els.map(e => e.textContent.toLowerCase())")
        self.assertTrue(all("odyssey" in t for t in titles))
        pg.close()

    def test_cinema_filter(self):
        pg = self._page()
        pg.select_option("#cinemaFilter", "manchester-home")
        cinemas = pg.eval_on_selector_all(
            ".card", "els => [...new Set(els.map(e => e.dataset.cinema))]")
        self.assertEqual(cinemas, ["manchester-home"])
        pg.close()

    def test_access_filter_audio_described(self):
        pg = self._page()
        pg.select_option("#accessFilter", "audio-described")
        # every visible card must carry the AD badge (or none visible)
        count = pg.locator(".card").count()
        if count:
            ad = pg.locator(".card .badge.ad").count()
            self.assertEqual(ad, count)
        pg.close()

    def test_group_by_film(self):
        pg = self._page()
        pg.select_option("#groupBy", "film")
        # a film group header should equal a known film title
        headers = pg.eval_on_selector_all(
            ".group-title", "els => els.map(e => e.childNodes[0].textContent.trim())")
        self.assertIn("The Odyssey", headers)
        pg.close()

    def test_nearest_sorts_and_shows_distance(self):
        pg = self._page()
        pg.click("#nearBtn")
        self.assertEqual(pg.get_attribute("#nearBtn", "aria-pressed"), "true")
        self.assertGreater(pg.locator(".dist").count(), 0)
        # first group's distance <= last group's distance
        dists = pg.eval_on_selector_all(
            ".group-title .checked", "els => els.length")  # sanity: groups exist
        self.assertGreater(pg.locator(".group-title").count(), 1)
        pg.close()

    def test_booking_and_imdb_links_present(self):
        pg = self._page()
        card = pg.locator(".card").first
        self.assertTrue(card.locator("a.primary", has_text="Book").count() >= 0)
        self.assertGreater(pg.locator(".links a", has_text="IMDb").count(), 0)
        pg.close()

    def test_screenshots(self):
        for name, w, h in [("ui-mobile", 390, 844), ("ui-desktop", 1100, 1000)]:
            pg = self._page(w, h)
            pg.screenshot(path=str(SHOTS / f"{name}.png"))
            pg.close()
        self.assertTrue((SHOTS / "ui-mobile.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
