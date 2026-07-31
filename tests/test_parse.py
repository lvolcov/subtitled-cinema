"""Unit tests for the parser + build pipeline. Run: python3 -m unittest -v"""
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.parse_ylc import (
    parse_showtimes, parse_access, detect_chain, parse_page, infer_year,
)
from build import build_site

REF = date(2026, 7, 24)
PAGES = ROOT / ".cache" / "pages"


class ShowtimeParsing(unittest.TestCase):
    def test_single(self):
        self.assertEqual(parse_showtimes("Tue 28 Jul 20:00", REF),
                         ["2026-07-28T20:00:00"])

    def test_carry_forward_times(self):
        # bare times inherit the previous token's day/month
        got = parse_showtimes("Thu 06 Aug 10:30, 12:45, 15:00, Sun 09 Aug 10:15", REF)
        self.assertEqual(got, [
            "2026-08-06T10:30:00", "2026-08-06T12:45:00",
            "2026-08-06T15:00:00", "2026-08-09T10:15:00",
        ])

    def test_multi_dates(self):
        got = parse_showtimes("Sat 25 Jul 12:00, Mon 27 Jul 12:00", REF)
        self.assertEqual(got, ["2026-07-25T12:00:00", "2026-07-27T12:00:00"])

    def test_no_weekday(self):
        self.assertEqual(parse_showtimes("28 Jul 19:30", REF), ["2026-07-28T19:30:00"])

    def test_garbage_ignored(self):
        self.assertEqual(parse_showtimes("NONE listed. Ask cinema", REF), [])

    def test_year_rollover(self):
        # month earlier than ref month -> next year
        self.assertEqual(infer_year(1, date(2026, 7, 1)), 2027)
        self.assertEqual(infer_year(9, date(2026, 7, 1)), 2026)
        self.assertEqual(parse_showtimes("Fri 15 Jan 20:00", date(2026, 7, 1)),
                         ["2027-01-15T20:00:00"])


class AccessParsing(unittest.TestCase):
    def test_subtitled_cert(self):
        a = parse_access("subtitled (12a)")
        self.assertEqual(a["accessibility"], ["subtitled"])
        self.assertEqual(a["certificate"], "12A")
        self.assertEqual(a["language"], "en")

    def test_audio_described(self):
        a = parse_access("AUDIO DESCRIBED (PG)")
        self.assertIn("audio-described", a["accessibility"])
        self.assertEqual(a["certificate"], "PG")

    def test_foreign(self):
        a = parse_access("JAPANESE with English subtitles")
        self.assertEqual(a["language"], "foreign")
        self.assertIn("subtitled", a["accessibility"])

    def test_imax(self):
        self.assertEqual(parse_access("subtitled IMAX (15)")["screen_type"], "imax")

    def test_defaults_to_subtitled(self):
        # these pages are subtitled-first even when the span is terse
        self.assertEqual(parse_access("(15)")["accessibility"], ["subtitled"])


class ChainDetection(unittest.TestCase):
    def test_from_name(self):
        self.assertEqual(detect_chain("Manchester Printworks Vue"), "Vue")
        self.assertEqual(detect_chain("Didsbury Cineworld"), "Cineworld")
        self.assertEqual(detect_chain("Wilmslow Rex"), "Rex")

    def test_from_alt_when_name_generic(self):
        self.assertEqual(detect_chain("Some Cinema", ["Odeon"]), "Odeon")

    def test_unknown(self):
        self.assertIsNone(detect_chain("Independent Picturehouse-less venue".replace("Picturehouse", "X")))


class LayoutA(unittest.TestCase):
    HTML = """
    <div class="cinema">
      <a href="https://www.odeon.co.uk/"><img alt="Odeon"></a>
      <h2>Test Trafford Odeon</h2>
      <div class="film-block">
        <p class="film-title"><a href="a.html">Film A</a> <span class="showtime">subtitled (15)</span></p>
        <p class="showtime">Tue 28 Jul 20:00, Wed 29 Jul 18:00</p>
        <p class="film-title"><a href="b.html">Film B</a> <span class="showtime">subtitled (U)</span></p>
        <p class="showtime">Sat 25 Jul 11:00</p>
      </div>
    </div>"""

    def test_parses(self):
        cinemas = parse_page(self.HTML, "testcity", REF)
        self.assertEqual(len(cinemas), 1)
        c = cinemas[0]
        self.assertEqual(c.name, "Test Trafford Odeon")
        self.assertEqual(c.chain, "Odeon")
        self.assertEqual(c.booking_url, "https://www.odeon.co.uk/")
        self.assertEqual(len(c.films), 2)
        self.assertEqual(c.screening_count, 3)


class LayoutB(unittest.TestCase):
    HTML = """
    <div class="cinema-list">
      <hr>
      <font><a href="stockport.html"><strong>Wilmslow</strong></a>Rex </font><em>SK9</em>
      <div class="film-block">
        <p class="film-title"><a href="c.html">Film C</a> <span class="showtime">subtitled (15)</span></p>
        <p class="showtime">Mon 27 Jul 17:00</p>
      </div>
      <hr>
      <font><a href="stockport.html"><strong>Heaton Moor</strong></a> Savoy </font><em>SK4</em>
      <p class="showtime">NONE listed. Ask cinema.</p>
      <hr>
    </div>"""

    def test_parses_named_venue_only(self):
        cinemas = parse_page(self.HTML, "stockport", REF)
        # the "NONE listed" venue has no screenings -> dropped
        self.assertEqual(len(cinemas), 1)
        c = cinemas[0]
        self.assertEqual(c.name, "Wilmslow Rex")
        self.assertEqual(c.area, "Wilmslow")
        self.assertEqual(c.postcode, "SK9")
        self.assertEqual(c.chain, "Rex")
        self.assertEqual(c.screening_count, 1)


@unittest.skipUnless(PAGES.exists(), "cached pages not present")
class RealPages(unittest.TestCase):
    def _cinemas(self, city):
        html = (PAGES / f"{city}.html").read_text(encoding="utf-8")
        return parse_page(html, city, REF)

    def test_manchester_has_expected_cinemas(self):
        names = {c.name for c in self._cinemas("manchester")}
        for expected in ["Manchester Trafford Odeon", "Manchester Home",
                         "Manchester Printworks Vue"]:
            self.assertIn(expected, names)

    def test_all_pages_parse_nonempty(self):
        for city in ["manchester", "stockport", "altrincham", "didsbury"]:
            cins = self._cinemas(city)
            self.assertTrue(cins, f"{city} yielded no cinemas")
            self.assertTrue(all(c.screening_count > 0 for c in cins))

    def test_every_screening_has_valid_timestamp(self):
        for city in ["manchester", "stockport", "altrincham", "didsbury"]:
            for c in self._cinemas(city):
                for f in c.films:
                    for s in f.screenings:
                        # must round-trip as ISO
                        datetime.fromisoformat(s.starts_at)


@unittest.skipUnless(PAGES.exists(), "cached pages not present")
class BuildPipeline(unittest.TestCase):
    def setUp(self):
        self.data = build_site.build(ref_date=REF,
                                      now=datetime(2026, 7, 24, 9, 0, 0))

    def test_stats_consistent(self):
        s = self.data["stats"]
        self.assertEqual(s["cinemas"], len(self.data["cinemas"]))
        self.assertEqual(s["screenings"],
                         sum(len(c["screenings"]) for c in self.data["cinemas"]))
        self.assertGreater(s["screenings"], 50)

    def test_stockport_light_deduped_across_cities(self):
        light = [c for c in self.data["cinemas"] if c["id"] == "stockport-light"]
        self.assertEqual(len(light), 1, "Stockport Light should be merged, not duplicated")
        self.assertIn("manchester", light[0]["cities"])
        self.assertIn("stockport", light[0]["cities"])

    def test_no_duplicate_screenings(self):
        for c in self.data["cinemas"]:
            keys = [(s["film_id"], s["starts_at"]) for s in c["screenings"]]
            self.assertEqual(len(keys), len(set(keys)), f"dupes in {c['id']}")

    def test_curated_coords_present(self):
        # every hand-curated venue keeps its coordinate (nationwide scale means we
        # can't hand-curate all 500+ venues, so this is the invariant that holds
        # regardless of the geocode cache).
        from build.cinema_meta import COORDS
        for c in self.data["cinemas"]:
            if c["id"] in COORDS:
                self.assertIsNotNone(c["lat"], f"{c['id']} lost its curated coord")

    def test_all_cinemas_have_coords(self):
        # with the feed + postcode + name-geocode chain, every venue should now be
        # placeable (regression against whole regions having no coordinates).
        missing = [c["id"] for c in self.data["cinemas"] if c["lat"] is None]
        self.assertEqual(missing, [], f"venues without coords: {missing}")

    def test_coord_sources_wired(self):
        # any venue that has coords but isn't hand-curated must have got them from
        # one of the automatic sources — the YLC locator feed (matched by name),
        # the postcode geocode cache, or the name geocode — proving the path.
        from build.cinema_meta import COORDS
        from build import geocode, geocode_name, coords_feed
        geo = geocode.load_cache()
        name_geo = geocode_name.load_cache()
        feed = coords_feed._as_sets(coords_feed.load_cache())
        for c in self.data["cinemas"]:
            if c["lat"] is None or c["id"] in COORDS:
                continue
            coord = [c["lat"], c["lng"]]
            from_feed = coords_feed.match(c["name"], feed)
            from_geo = geo.get(c["postcode"]) if c["postcode"] else None
            from_name = name_geo.get(c["name"])
            self.assertTrue(coord in (from_feed, from_geo, from_name),
                            f"{c['id']} coord not from feed/postcode/name geocode")

    def test_nearest_returns_a_local_venue(self):
        # regression for the "Newcastle -> Stockton 34mi" bug: a user in a city
        # with cinemas should get one within a few miles, not a distant fallback.
        from math import radians, sin, cos, asin, sqrt

        def miles(a, b):
            dlat, dlng = radians(b[0] - a[0]), radians(b[1] - a[1])
            h = sin(dlat / 2) ** 2 + cos(radians(a[0])) * cos(radians(b[0])) * sin(dlng / 2) ** 2
            return 3959 * 2 * asin(sqrt(h))

        newcastle = (54.9783, -1.6178)
        placed = [(c["lat"], c["lng"]) for c in self.data["cinemas"] if c["lat"]]
        nearest = min(miles(newcastle, p) for p in placed)
        self.assertLess(nearest, 5, f"nearest cinema to Newcastle is {nearest:.1f} mi away")

    def test_every_screening_has_a_smart_book_link(self):
        # each showtime links to the film (chain site or a scoped search), never a
        # dead/homepage link.
        for c in self.data["cinemas"]:
            for s in c["screenings"]:
                self.assertTrue(s.get("book", "").startswith("https://"),
                                f"{c['id']} / {s['title']} has no smart book link")

    def test_screenings_sorted(self):
        for c in self.data["cinemas"]:
            times = [s["starts_at"] for s in c["screenings"]]
            self.assertEqual(times, sorted(times))

    # ---- regions (the "show me one part of the UK" filter) ----
    def test_every_cinema_has_a_region(self):
        missing = [c["id"] for c in self.data["cinemas"] if not c["region"]]
        self.assertEqual(missing, [], f"venues with no region: {missing}")

    def test_region_index_matches_cinemas(self):
        from collections import Counter
        counted = Counter(c["region"] for c in self.data["cinemas"])
        indexed = {r["name"]: r["cinemas"] for r in self.data["regions"]}
        self.assertEqual(dict(counted), indexed)
        screenings = {r["name"]: r["screenings"] for r in self.data["regions"]}
        for name, n in screenings.items():
            self.assertEqual(n, sum(len(c["screenings"]) for c in self.data["cinemas"]
                                    if c["region"] == name))

    def test_greater_manchester_is_first_region(self):
        # this project's home patch is pinned to the top of the filter
        self.assertEqual(self.data["regions"][0]["name"], "Greater Manchester")

    def test_manchester_venues_are_greater_manchester(self):
        by_id = {c["id"]: c for c in self.data["cinemas"]}
        for cid in ["manchester-home", "manchester-printworks-vue", "stockport-light",
                    "altrincham-vue", "bolton-light", "wigan-omniplex"]:
            if cid in by_id:      # subset builds (UI tests) pin fewer towns
                self.assertEqual(by_id[cid]["region"], "Greater Manchester", cid)

    def test_cheshire_venues_on_gm_pages_are_overridden(self):
        # YLC town pages reach across county lines: these appear on Manchester-area
        # pages but aren't in Greater Manchester.
        by_id = {c["id"]: c for c in self.data["cinemas"]}
        for cid in ["wilmslow-rex", "knutsford-curzon", "warrington-odeon"]:
            if cid in by_id:
                self.assertEqual(by_id[cid]["region"], "North West", cid)


class RegionMap(unittest.TestCase):
    def test_every_town_page_is_mapped(self):
        from build.fetch_pages import CITIES
        from build.regions import TOWN_REGION
        missing = [c for c in CITIES if c not in TOWN_REGION]
        self.assertEqual(missing, [], f"town pages with no region: {missing}")

    def test_regions_are_known_names(self):
        from build.regions import TOWN_REGION, VENUE_REGION, REGION_ORDER
        for r in set(TOWN_REGION.values()) | set(VENUE_REGION.values()):
            self.assertIn(r, REGION_ORDER)

    def test_venue_override_wins_over_town_page(self):
        from build import regions
        self.assertEqual(regions.region_for("wilmslow-rex", ["stockport"]), "North West")
        self.assertEqual(regions.region_for("manchester-home", ["manchester"]),
                         "Greater Manchester")
        self.assertIsNone(regions.region_for("somewhere-new", ["not-a-town"]))

    def test_sort_key_puts_greater_manchester_first(self):
        from build import regions
        names = ["Wales", "London", "Greater Manchester", "Scotland"]
        self.assertEqual(sorted(names, key=regions.sort_key)[0], "Greater Manchester")


if __name__ == "__main__":
    unittest.main(verbosity=2)
