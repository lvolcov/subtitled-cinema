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

from bs4 import BeautifulSoup, NavigableString, Tag

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


# chain booking domains -> chain, for when a logo has no alt text but does link out
CHAIN_DOMAINS = {
    "odeon.co.uk": "Odeon", "myvue.com": "Vue", "cineworld": "Cineworld",
    "picturehouses.com": "Picturehouse", "lightcinemas": "Light",
    "everymancinema": "Everyman", "homemcr": "HOME", "curzon.com": "Curzon",
    "theregentmarple": "Regent",
}


def detect_chain(name: str, img_alts=(), hrefs=()) -> Optional[str]:
    hay = (name + " " + " ".join(img_alts)).lower()
    for kw, chain in CHAIN_KEYWORDS:
        if kw in hay:
            return chain
    href_hay = " ".join(hrefs).lower()
    for domain, chain in CHAIN_DOMAINS.items():
        if domain in href_hay:
            return chain
    return None


def booking_for(chain: Optional[str], fallback_hrefs=(),
                name: Optional[str] = None, postcode: Optional[str] = None) -> Optional[str]:
    """Best-effort book-out link. Prefer the chain's own site; otherwise a Google
    search for the venue by name — the source hrefs are unreliable (a logo often
    links to the wrong brand/branch, e.g. Wigan Omniplex -> Omniplex Birmingham),
    so a name search lands people on the right cinema. Source href only as a last
    resort. Never returns a dead '#'.
    """
    if chain and chain in CHAIN_URL:
        return CHAIN_URL[chain]
    if name:
        from urllib.parse import quote_plus
        terms = " ".join(t for t in (name, postcode, "cinema tickets") if t)
        return "https://www.google.com/search?q=" + quote_plus(terms)
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
        booking = booking_for(chain, hrefs, name=name)
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
# Capture the outward code (e.g. "OL11") as the stored postcode, but also match
# and strip any following inward code ("1RB", or a source-truncated "1R") so it
# doesn't leak into the cinema name ("Rochdale Odeon 1R").
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?)(?:\s*\d[A-Z]{0,2})?\b")


# junk that leaks into venue headings on badly-nested aggregation pages
_HEADING_CUTS = ("subtitled", "captioned", "audio described", "none listed",
                 "click for", "ask cinema", "ask the cinema")


def _is_namable(name: str) -> bool:
    """Whether a heading gave us a real venue name (vs an unnamable fragment)."""
    return bool(name) and name != "Unknown cinema" and any(ch.isalpha() for ch in name)


def _venue_name(name: str, city: str, chain: Optional[str] = None) -> tuple:
    """Fall back to the town (plus chain, if a logo told us one) when a heading
    gave us nothing usable — some pages list a single cinema with no heading at all
    (e.g. island towns, or a lone Curzon). Better to show its shows under
    "Oxford Curzon" / "Orkney" than to drop them. Returns (name, used_fallback)."""
    if _is_namable(name):
        return name, False
    label = city.replace("-", " ").title()
    if chain:
        label = f"{label} {chain}"
    return label, True


def _truncate_heading(full: str) -> str:
    """Trim film/showtime text and site chrome that malformed markup dumps into a
    venue heading, and strip stray link-target tokens (target=, layerNN)."""
    cut = len(full)
    m = DATE_TOKEN_RE.search(full)
    if m:
        cut = min(cut, m.start())
    low = full.lower()
    for kw in _HEADING_CUTS:
        i = low.find(kw)
        if i >= 0:
            cut = min(cut, i)
    full = full[:cut]
    full = re.sub(r"\b(?:target|layer\d+)\b", " ", full, flags=re.I)
    return re.sub(r"\s+", " ", full).strip(" -–,")


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

    # an "area" is sometimes a long comma-list of served districts — keep the last
    # one (nearest the venue), e.g. "Tottenham, …, Whitechapel" -> "Whitechapel".
    area = strongs[0] if strongs else None
    if area and "," in area:
        area = area.split(",")[-1].strip()
    full = re.sub(r"\s+", " ", " ".join(t for t in texts if t)).strip()
    # a served-districts list (many commas) collapses to the venue's own district
    if full.count(",") >= 3:
        full = full.split(",")[-1].strip()
    full = _truncate_heading(full)
    if area:
        area = _truncate_heading(area)

    postcode = None
    pm = POSTCODE_RE.search(full)
    if pm:
        postcode = pm.group(1)
        full = full.replace(pm.group(0), " ")

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
        chain = detect_chain(name, alts, hrefs)
        name, fell_back = _venue_name(name, city, chain)
        if fell_back:
            area = name
        booking = booking_for(chain, hrefs, name=name, postcode=postcode)
        cin = Cinema(name=name, area=area, city=city, chain=chain,
                     postcode=postcode, booking_url=booking)
        cin.films.extend(parse_film_block(block, ref))
        if cin.screening_count:
            cinemas.append(cin)
    return cinemas


# --------------------------------------------------------------------------- #
# layout C: newer templates (document-order walk)
# --------------------------------------------------------------------------- #
# yourlocalcinema is migrating town pages to redesigned templates. They keep the
# same logical shape — an <hr>-delimited venue heading (chain logo + area/brand/
# postcode text) followed by that venue's listings — but the markup is malformed
# (unclosed <strong>/<a>/<font> swallow everything into nested tags) and the
# listings come in two flavours: the old `.film-block` (p.film-title + p.showtime)
# OR a newer `.film-entry` (title + cert) paired with a following `.film-date`
# (showtimes). The <hr>-on-direct-children split in layout B can't see through the
# bad nesting, so we walk the container in document order instead, treating each
# film unit as a leaf (its inner text isn't venue-name context).
_NAME_NOISE = (
    "none listed", "click for info", "ask the cinema", "ask cinema", "important!",
    "also:", "check local", "check with", "foreign-language", "foreign language",
    "shows!", "provide acces", "schedule", "subtitles will", "definitely",
    "set out", "short notice",
)


def _find_listing_container(soup: BeautifulSoup):
    """The nearest ancestor of the first film unit that also holds the <hr>
    separators (cinema-list on redesigned pages, a blockquote on .film-entry ones)."""
    unit = soup.find(class_=["film-block", "film-entry"])
    if unit is None:
        return None
    node = unit.parent
    while node is not None and getattr(node, "name", None) not in ("body", "html", "[document]"):
        if node.find("hr"):
            return node
        node = node.parent
    return soup.select_one("div.cinema-list") or soup.body or soup


def _is_unit(t: Tag) -> bool:
    return bool({"film-block", "film-entry", "film-date"} & set(t.get("class") or []))


def _walk_events(container: Tag) -> list:
    """('hr',None) | ('unit',tag) | ('text',str) | ('img',alt) in document order.
    Does not descend into film units — their text is listings, not venue names."""
    events = []

    def rec(node):
        for ch in node.children:
            if isinstance(ch, Tag):
                if ch.name in ("style", "script", "head", "noscript"):
                    continue                       # never venue-name text
                if ch.name == "hr":
                    events.append(("hr", None))
                elif _is_unit(ch):
                    events.append(("unit", ch))
                elif ch.name == "img":
                    events.append(("img", ch.get("alt", "") or ""))
                else:
                    rec(ch)
            elif isinstance(ch, NavigableString):
                s = str(ch).strip()
                if s:
                    events.append(("text", s))

    rec(container)
    return events


def _looks_like_listing(s: str) -> bool:
    """A film/showtime line that leaked into the heading region (some aggregation
    pages have badly nested markup) — never part of a venue name."""
    low = s.lower()
    return bool(DATE_TOKEN_RE.search(s)) or "subtitled" in low or "captioned" in low \
        or "audio described" in low or bool(CERT_RE.search(s))


def _name_from_fragments(texts, alts) -> tuple:
    """(name, area, postcode) from the ordered heading text before a venue's units."""
    keep = [t for t in texts
            if not any(n in t.lower() for n in _NAME_NOISE)
            and not _looks_like_listing(t)]
    full = _truncate_heading(re.sub(r"\s+", " ", " ".join(keep)).strip())
    postcode = None
    pm = POSTCODE_RE.search(full)
    if pm:
        postcode = pm.group(1)
        full = full.replace(pm.group(0), " ")
    name = re.sub(r"[^A-Za-z0-9&/'\-, ]", " ", full)
    name = re.sub(r"\s+", " ", name).strip(" -–,")
    area = keep[0].strip(" ,") if keep else name
    return (name or "Unknown cinema"), (area or name), postcode


def _films_from_units(units, ref: date) -> list:
    """Turn an ordered list of film units into Film objects. Handles both the
    `.film-block` and the paired `.film-entry`/`.film-date` markups."""
    films = []
    i = 0
    while i < len(units):
        u = units[i]
        cls = set(u.get("class") or [])
        if "film-block" in cls:
            films.extend(parse_film_block(u, ref))
            i += 1
            continue
        if "film-entry" in cls:
            a = u.find("a")
            title = (a.get_text(strip=True) if a else u.get_text(" ", strip=True))
            source_url = a.get("href") if a else None
            span = u.find("span")
            span_text = span.get_text(" ", strip=True) if span else ""
            attrs = parse_access(span_text or u.get_text(" ", strip=True))
            times = []
            if i + 1 < len(units) and "film-date" in set(units[i + 1].get("class") or []):
                times = parse_showtimes(units[i + 1].get_text(" ", strip=True), ref)
                i += 2
            else:
                i += 1
            if title and times:
                film = Film(title=title, source_url=source_url)
                for iso in times:
                    film.screenings.append(Screening(
                        starts_at=iso, accessibility=attrs["accessibility"],
                        certificate=attrs["certificate"], screen_type=attrs["screen_type"],
                        note=span_text, language=attrs["language"]))
                films.append(film)
            continue
        i += 1
    return films


def _parse_layout_c(soup: BeautifulSoup, city: str, ref: date) -> list:
    container = _find_listing_container(soup)
    if container is None:
        return []
    cinemas = []
    seg_texts, seg_alts, seg_units = [], [], []

    def flush():
        if not seg_units:
            return
        name, area, postcode = _name_from_fragments(seg_texts, seg_alts)
        chain = detect_chain(name, seg_alts)
        name, fell_back = _venue_name(name, city, chain)
        if fell_back:
            area = name
        booking = booking_for(chain, (), name=name, postcode=postcode)
        cin = Cinema(name=name, area=area, city=city, chain=chain,
                     postcode=postcode, booking_url=booking)
        cin.films.extend(_films_from_units(seg_units, ref))
        if cin.screening_count and _is_namable(cin.name):
            cinemas.append(cin)

    for kind, val in _walk_events(container):
        if kind == "hr":
            flush()
            seg_texts, seg_alts, seg_units = [], [], []
        elif kind == "unit":
            seg_units.append(val)
        elif kind == "text":
            if not seg_units:            # heading text only, before the listings
                seg_texts.append(val)
        elif kind == "img" and val:
            seg_alts.append(val)
    flush()
    return cinemas


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def parse_page(html: str, city: str, ref_date: Optional[date] = None) -> list:
    """Parse one city page into a list of Cinema objects (only those with shows).

    Tries the two original layouts first (unchanged); when they find nothing —
    a page has been migrated to a redesigned/malformed template — falls back to
    the document-order walk that copes with the newer markup.
    """
    ref = ref_date or date.today()
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("div.cinema"):
        cinemas = _parse_layout_a(soup, city, ref)
        if cinemas:
            return cinemas
    # The old hr-split (B) and the document-order walk (C) each win on different
    # templates — B on some malformed aggregation pages, C on redesigned ones where
    # bad nesting hides the venues from B. Run both and keep the fuller reading so a
    # migrated page can never silently under-report its venues.
    b = _parse_layout_b(soup, city, ref)
    c = _parse_layout_c(soup, city, ref)

    def _score(cs):
        return (sum(x.screening_count for x in cs), len(cs))

    return b if _score(b) >= _score(c) else c


def cinema_to_dict(c: Cinema) -> dict:
    d = asdict(c)
    d["screening_count"] = c.screening_count
    return d
