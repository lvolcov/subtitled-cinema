"""
parse_ylc.py — Parse yourlocalcinema.com city pages into normalised screenings.

yourlocalcinema.com uses two markup layouts:

  Layout A ("cinema"):     one <div class="cinema"> per venue, name in <h2>,
                           an optional chain logo <a><img></a>, one .film-block.
                           (used by manchester.html)

  Layout B ("cinema-list"):one <div class="cinema-list">, venues separated by
                           <hr>, name assembled from <font>/<strong>/<em> text,
                           each venue followed by a .film-block OR a
                           "NONE listed" paragraph.
                           (used by stockport/altrincham/didsbury.html)

Both share the same .film-block shape: alternating
  <p class="film-title"><a>Title</a> <span class="showtime">access (cert)</span></p>
  <p class="showtime">Tue 28 Jul 20:00, Wed 29 Jul 10:00</p>

This module is pure and side-effect free so it can be unit tested. The only
"now" it depends on is passed in explicitly (`ref_date`) for deterministic
year inference in tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup, Tag

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# The source markup is unreliable for chains (e.g. a Vue logo links to
# odeon.co.uk), so we detect the chain from the cinema NAME and the logo's
# <img alt="..."> text, which are trustworthy. Order matters: first hit wins.
CHAIN_KEYWORDS = [
    ("vue", "Vue"),
    ("odeon", "Odeon"),
    ("everyman", "Everyman"),
    ("cineworld", "Cineworld"),
    ("picturehouse", "Picturehouse"),
    ("light", "Light"),
    ("home", "HOME"),
    ("curzon", "Curzon"),
    ("savoy", "Savoy"),
    ("regent", "Regent"),
    ("cinemac", "Cinemac"),
    ("rex", "Rex"),
]

# canonical book-out link per chain (the source hrefs are not dependable)
CHAIN_URL = {
    "Odeon": "https://www.odeon.co.uk/",
    "Vue": "https://www.myvue.com/",
    "Cineworld": "https://www.cineworld.co.uk/",
    "Picturehouse": "https://www.picturehouses.com/",
    "Light": "https://www.lightcinemas.co.uk/",
    "Everyman": "https://www.everymancinema.com/",
    "HOME": "https://homemcr.org/",
    "Curzon": "https://www.curzon.com/",
    "Regent": "https://www.theregentmarple.co.uk/",
}


def detect_chain(name: str, img_alts=()) -> Optional[str]:
    hay = (name + " " + " ".join(img_alts)).lower()
    for kw, chain in CHAIN_KEYWORDS:
        if kw in hay:
            return chain
    return None


def booking_for(chain: Optional[str], fallback_hrefs=()) -> Optional[str]:
    if chain and chain in CHAIN_URL:
        return CHAIN_URL[chain]
    return next((h for h in fallback_hrefs if h.startswith("http")), None)

CERT_RE = re.compile(r"\(\s*(U|PG|12A|12|15|18|TBC)\s*\)", re.I)
# a full date token like "Tue 28 Jul 20:00" or "28 Jul 20:00"
DATE_TOKEN_RE = re.compile(
    r"(?:(?P<wd>mon|tue|wed|thu|fri|sat|sun)\w*\s+)?"
    r"(?P<day>\d{1,2})\s+(?P<mon>[a-z]+)\s+(?P<h>\d{1,2}):(?P<m>\d{2})",
    re.I,
)
# a time-only continuation token like "12:45"
TIME_TOKEN_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})$")


@dataclass
class Screening:
    starts_at: str            # ISO 8601, local (Europe/London wall time)
    accessibility: list       # ["subtitled"] / ["audio-described"] / both
    certificate: Optional[str]
    screen_type: str          # "standard" | "imax" | ...
    note: str                 # raw span text (e.g. "PARENT AND BABY subtitled")
    language: str             # "en" | "foreign"


@dataclass
class Film:
    title: str
    source_url: Optional[str]   # yourlocalcinema film page (fallback info link)
    screenings: list = field(default_factory=list)


@dataclass
class Cinema:
    name: str
    area: str
    city: str
    chain: Optional[str]
    postcode: Optional[str]
    booking_url: Optional[str]  # chain website (best-effort book-out link)
    films: list = field(default_factory=list)

    @property
    def screening_count(self) -> int:
        return sum(len(f.screenings) for f in self.films)


# --------------------------------------------------------------------------- #
# date / attribute parsing
# --------------------------------------------------------------------------- #
def infer_year(month: int, ref: date) -> int:
    """No year is given on the source. Assume the next occurrence of `month`."""
    return ref.year if month >= ref.month else ref.year + 1


def parse_showtimes(text: str, ref: date) -> list:
    """Parse a comma-separated showtime string into ISO timestamps.

    Handles carry-forward times, e.g.
        "Thu 06 Aug 10:30, 12:45, 15:00, Sun 09 Aug 10:15"
    where bare times inherit the previous token's day/month.
    """
    out = []
    last_day = last_mon = None
    for raw in text.split(","):
        tok = raw.strip()
        if not tok:
            continue
        m = DATE_TOKEN_RE.search(tok)
        if m:
            day = int(m.group("day"))
            mon = MONTHS.get(m.group("mon").lower())
            if mon is None:
                continue
            hh, mm = int(m.group("h")), int(m.group("m"))
            last_day, last_mon = day, mon
            year = infer_year(mon, ref)
            out.append(datetime(year, mon, day, hh, mm).isoformat())
            continue
        t = TIME_TOKEN_RE.match(tok)
        if t and last_day is not None:
            hh, mm = int(t.group("h")), int(t.group("m"))
            year = infer_year(last_mon, ref)
            out.append(datetime(year, last_mon, last_day, hh, mm).isoformat())
    return out


def parse_access(span_text: str) -> dict:
    """Extract accessibility tags, certificate, screen type and language."""
    low = span_text.lower()
    access = []
    if "subtitle" in low or "caption" in low:
        access.append("subtitled")
    if "audio" in low and "describ" in low:
        access.append("audio-described")
    if not access:
        access.append("subtitled")  # these pages are subtitled-first by nature

    cert_m = CERT_RE.search(span_text)
    cert = cert_m.group(1).upper() if cert_m else None

    screen_type = "standard"
    if "imax" in low:
        screen_type = "imax"

    language = "foreign" if ("english subtitles" in low or "foreign" in low) else "en"

    return {
        "accessibility": access,
        "certificate": cert,
        "screen_type": screen_type,
        "language": language,
    }


# --------------------------------------------------------------------------- #
# film-block parsing (shared by both layouts)
# --------------------------------------------------------------------------- #
def parse_film_block(block: Tag, ref: date) -> list:
    """Return a list of Film objects from a .film-block element."""
    films = []
    # children in document order: film-title / showtime / film-title / ...
    ps = block.find_all("p", recursive=True)
    i = 0
    while i < len(ps):
        p = ps[i]
        classes = p.get("class") or []
        if "film-title" in classes:
            a = p.find("a")
            title = (a.get_text(strip=True) if a else p.get_text(strip=True))
            source_url = a.get("href") if a else None
            span = p.find("span", class_="showtime")
            span_text = span.get_text(" ", strip=True) if span else ""
            attrs = parse_access(span_text)
            # the following showtime <p> holds the dates
            times = []
            if i + 1 < len(ps):
                nxt = ps[i + 1]
                if "showtime" in (nxt.get("class") or []):
                    times = parse_showtimes(nxt.get_text(" ", strip=True), ref)
                    i += 1
            if times:
                film = Film(title=title, source_url=source_url)
                for iso in times:
                    film.screenings.append(Screening(
                        starts_at=iso,
                        accessibility=attrs["accessibility"],
                        certificate=attrs["certificate"],
                        screen_type=attrs["screen_type"],
                        note=span_text,
                        language=attrs["language"],
                    ))
                films.append(film)
        i += 1
    return films


# --------------------------------------------------------------------------- #
# layout A: <div class="cinema">
# --------------------------------------------------------------------------- #
def _parse_layout_a(soup: BeautifulSoup, city: str, ref: date) -> list:
    cinemas = []
    for div in soup.select("div.cinema"):
        h = div.find(["h2", "h3"])
        if not h:
            continue
        name = h.get_text(strip=True)
        hrefs = [a.get("href", "") for a in div.find_all("a")]
        alts = [img.get("alt", "") for img in div.find_all("img")]
        chain = detect_chain(name, alts)
        booking = booking_for(chain, hrefs)
        cin = Cinema(name=name, area=name, city=city, chain=chain,
                     postcode=None, booking_url=booking)
        for block in div.select("div.film-block"):
            cin.films.extend(parse_film_block(block, ref))
        if cin.screening_count:
            cinemas.append(cin)
    return cinemas


# --------------------------------------------------------------------------- #
# layout B: <div class="cinema-list"> split on <hr>
# --------------------------------------------------------------------------- #
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)\b")


def _name_from_segment(nodes) -> tuple:
    """Assemble (name, area, postcode) from the text nodes before a film-block.

    Layout B names look like: <strong>Wilmslow</strong>Rex <em>SK9</em>
    -> area="Wilmslow", brand="Rex", -> name "Wilmslow Rex", postcode "SK9".
    The area <strong> is often nested inside an <a>, so search descendants.
    """
    strongs, texts = [], []
    for n in nodes:
        if isinstance(n, Tag):
            for s in n.find_all("strong"):
                t = s.get_text(" ", strip=True)
                if t:
                    strongs.append(t)
            texts.append(n.get_text(" ", strip=True))
        else:
            texts.append(str(n).strip())

    area = strongs[0] if strongs else None
    full = re.sub(r"\s+", " ", " ".join(t for t in texts if t)).strip()

    postcode = None
    pm = POSTCODE_RE.search(full)
    if pm:
        postcode = pm.group(1)
        full = full.replace(postcode, " ")

    brand = full
    if area:
        brand = brand.replace(area, " ", 1)
    # drop a stray city qualifier the source sometimes injects into the brand
    # (e.g. area "Altrincham" + brand "Manchester Vue" -> "Altrincham Vue")
    if area and area.lower() != "manchester":
        brand = re.sub(r"\bManchester\b", " ", brand)
    brand = re.sub(r"[^A-Za-z0-9&/'\- ]", " ", brand)
    brand = re.sub(r"\s+", " ", brand).strip(" -–")

    if area and brand and area.lower() not in brand.lower():
        name = f"{area} {brand}"
    else:
        name = brand or area or "Unknown cinema"
    name = re.sub(r"\s+", " ", name).strip()
    return name, (area or name), postcode


def _parse_layout_b(soup: BeautifulSoup, city: str, ref: date) -> list:
    wrap = soup.select_one("div.cinema-list")
    if not wrap:
        return []
    cinemas = []
    # split children into segments delimited by <hr>
    segment = []
    segments = []
    for child in wrap.children:
        if isinstance(child, Tag) and child.name == "hr":
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(child)
    if segment:
        segments.append(segment)

    for seg in segments:
        block = None
        name_nodes = []
        for n in seg:
            if isinstance(n, Tag) and ("film-block" in (n.get("class") or [])):
                block = n
                break
            name_nodes.append(n)
        if block is None:
            continue  # "NONE listed" or footer segments
        name, area, postcode = _name_from_segment(name_nodes)
        hrefs, alts = [], []
        for n in seg:
            if isinstance(n, Tag):
                hrefs += [a.get("href", "") for a in n.find_all("a")]
                alts += [img.get("alt", "") for img in n.find_all("img")]
        chain = detect_chain(name, alts)
        booking = booking_for(chain, hrefs)
        cin = Cinema(name=name, area=area, city=city, chain=chain,
                     postcode=postcode, booking_url=booking)
        cin.films.extend(parse_film_block(block, ref))
        if cin.screening_count:
            cinemas.append(cin)
    return cinemas


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def parse_page(html: str, city: str, ref_date: Optional[date] = None) -> list:
    """Parse one city page into a list of Cinema objects (only those with shows)."""
    ref = ref_date or date.today()
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("div.cinema"):
        return _parse_layout_a(soup, city, ref)
    return _parse_layout_b(soup, city, ref)


def cinema_to_dict(c: Cinema) -> dict:
    d = asdict(c)
    d["screening_count"] = c.screening_count
    return d
