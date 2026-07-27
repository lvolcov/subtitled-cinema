"""
audit_coverage.py — independent completeness check for the whole-UK town set.

For every town page it compares what the parser captured against a parser-independent
count of showtime lines in the raw HTML (date tokens like "Tue 28 Jul 20:00"), and
flags any page whose raw showtime count is well above what we parsed — the signal of
a layout the parser is under-reading. Pages that are genuinely empty ("NONE listed")
show 0/0 and are fine.

Run:   python3 -m tests.audit_coverage            # all towns
       python3 -m tests.audit_coverage a b c      # just towns a, b, c
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from build.fetch_pages import CITIES
from build.parse_ylc import parse_page

PAGES = Path(__file__).resolve().parent.parent / ".cache" / "pages"
REF = date(2026, 7, 27)
# a showtime token in the raw page, e.g. "Tue 28 Jul 20:00" or "28 Jul 20:00"
RAW_TIME = re.compile(
    r"(?:(?:mon|tue|wed|thu|fri|sat|sun)\w*\s+)?\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}:\d{2}",
    re.I,
)


def audit(towns) -> int:
    flagged = []
    for town in towns:
        f = PAGES / f"{town}.html"
        if not f.exists():
            print(f"  ?? {town}: no cached page")
            continue
        html = f.read_text(encoding="utf-8")
        cins = parse_page(html, town, REF)
        parsed_venues = len(cins)
        parsed_shows = sum(c.screening_count for c in cins)
        raw_shows = len(RAW_TIME.findall(html))
        # heuristic: flag if the raw page clearly has many more showtimes than we
        # captured (allow generous slack for de-dupe / carry-forward times).
        under = raw_shows > 4 and parsed_shows < 0.5 * raw_shows
        tag = "UNDER" if under else "ok"
        if under:
            flagged.append(town)
        print(f"  [{tag:>5}] {town:<16} venues={parsed_venues:<3} "
              f"parsed_shows={parsed_shows:<4} raw_shows={raw_shows}")
    print(f"\nflagged (possible undercount): {flagged or 'none'}")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(audit(sys.argv[1:] or CITIES))
