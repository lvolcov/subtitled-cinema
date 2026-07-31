"""
regions.py — map each yourlocalcinema town page to a UK region, so the site can
offer a "Region" filter ("show me Greater Manchester") instead of only a
155-town / 550-venue cinema list.

Two levels, in priority order:

  1. VENUE_REGION — per-venue overrides, keyed by the cinema's slug (see
     build_site.slugify). Needed because a YLC town page lists everything within
     travelling distance, so e.g. manchester/stockport/altrincham pages carry a
     few Cheshire and Merseyside venues that aren't in Greater Manchester.
  2. TOWN_REGION  — the region of the town page a venue was first found on.

REGION_ORDER puts **Greater Manchester first** (this project's home patch and
its most-used filter), then the rest of the UK roughly north → south, then the
nations and islands. The frontend renders regions in this order.
"""
from __future__ import annotations

GREATER_MANCHESTER = "Greater Manchester"

REGION_ORDER = [
    GREATER_MANCHESTER,
    "North West",
    "North East",
    "Yorkshire",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Wales",
    "Scotland",
    "Islands",
    "Ireland",
]

# town page -> region
TOWN_REGION = {
    # --- Greater Manchester (the seven town pages covering the conurbation) ---
    "manchester": GREATER_MANCHESTER,
    "stockport": GREATER_MANCHESTER,
    "altrincham": GREATER_MANCHESTER,
    "didsbury": GREATER_MANCHESTER,
    "bolton": GREATER_MANCHESTER,
    "bury": GREATER_MANCHESTER,
    "ashton": GREATER_MANCHESTER,

    # --- North West (Cheshire, Lancashire, Merseyside, Cumbria) ---
    "accrington": "North West",
    "blackpool": "North West",
    "bromborough": "North West",
    "carlisle": "North West",
    "crewe": "North West",
    "liverpool": "North West",
    "morecambe": "North West",
    "preston": "North West",
    "southport": "North West",
    "warrington": "North West",
    "workington": "North West",

    # --- North East ---
    "berwick": "North East",
    "darlington": "North East",
    "hartlepool": "North East",
    "middlesbrough": "North East",
    "newcastle": "North East",
    "sunderland": "North East",

    # --- Yorkshire & the Humber ---
    "bradford": "Yorkshire",
    "castleford": "Yorkshire",
    "doncaster": "Yorkshire",
    "harrogate": "Yorkshire",
    "huddersfield": "Yorkshire",
    "hull": "Yorkshire",
    "leeds": "Yorkshire",
    "sheffield": "Yorkshire",
    "york": "Yorkshire",

    # --- East Midlands ---
    "chesterfield": "East Midlands",
    "cleethorpes": "East Midlands",
    "derby": "East Midlands",
    "kettering": "East Midlands",
    "leicester": "East Midlands",
    "lincoln": "East Midlands",
    "mansfield": "East Midlands",
    "northampton": "East Midlands",
    "nottingham": "East Midlands",
    "scunthorpe": "East Midlands",

    # --- West Midlands ---
    "birmingham": "West Midlands",
    "coventry": "West Midlands",
    "dudley": "West Midlands",
    "hereford": "West Midlands",
    "redditch": "West Midlands",
    "rugby": "West Midlands",
    "shrewsbury": "West Midlands",
    "stoke": "West Midlands",
    "tamworth": "West Midlands",
    "telford": "West Midlands",
    "walsall": "West Midlands",
    "wolverhampton": "West Midlands",
    "worcester": "West Midlands",

    # --- East of England ---
    "braintree": "East of England",
    "cambridge": "East of England",
    "chelmsford": "East of England",
    "colchester": "East of England",
    "hatfield": "East of England",
    "huntingdon": "East of England",
    "ipswich": "East of England",
    "luton": "East of England",
    "norwich": "East of England",
    "southend": "East of England",
    "stevenage": "East of England",
    "thurrock": "East of England",
    "watford": "East of England",

    # --- London ---
    "acton": "London",
    "beckenham": "London",
    "brentford": "London",
    "brixton": "London",
    "chelsea": "London",
    "crouchend": "London",
    "croydon": "London",
    "dagenham": "London",
    "enfield": "London",
    "feltham": "London",
    "finchley": "London",
    "fulham": "London",
    "greenwich": "London",
    "harrow": "London",
    "islington": "London",
    "kingston": "London",
    "peckham": "London",
    "stratford": "London",
    "uxbridge": "London",
    "wandsworth": "London",
    "waterloo": "London",
    "wimbledon": "London",

    # --- South East ---
    "aylesbury": "South East",
    "banbury": "South East",
    "basingstoke": "South East",
    "bracknell": "South East",
    "brighton": "South East",
    "canterbury": "South East",
    "chichester": "South East",
    "crawley": "South East",
    "eastbourne": "South East",
    "epsom": "South East",
    "guildford": "South East",
    "hastings": "South East",
    "horsham": "South East",
    "maidenhead": "South East",
    "maidstone": "South East",
    "oxford": "South East",
    "portsmouth": "South East",
    "reading": "South East",
    "reigate": "South East",
    "southampton": "South East",
    "staines": "South East",
    "tunbridge": "South East",
    "woking": "South East",

    # --- South West ---
    "barnstable": "South West",
    "bath": "South West",
    "bournemouth": "South West",
    "bristol": "South West",
    "cheltenham": "South West",
    "clevedon": "South West",
    "cornwall": "South West",
    "exeter": "South West",
    "plymouth": "South West",
    "salisbury": "South West",
    "swindon": "South West",
    "taunton": "South West",
    "torbay": "South West",
    "weston": "South West",
    "weymouth": "South West",
    "yeovil": "South West",

    # --- Wales ---
    "aberystwyth": "Wales",
    "bridgend": "Wales",
    "cardiff": "Wales",
    "carmarthen": "Wales",
    "llandudno": "Wales",
    "swansea": "Wales",
    "wrexham": "Wales",

    # --- Scotland ---
    "aberdeen": "Scotland",
    "ayr": "Scotland",
    "dumfries": "Scotland",
    "dundee": "Scotland",
    "dunfermline": "Scotland",
    "edinburgh": "Scotland",
    "falkirk": "Scotland",
    "glasgow": "Scotland",
    "inverness": "Scotland",
    "kilmarnock": "Scotland",
    "livingston": "Scotland",
    "orkney": "Scotland",
    "perth": "Scotland",
    "shetland": "Scotland",
    "stirling": "Scotland",

    # --- Islands / Crown dependencies, and the all-Ireland page ---
    "isleofman": "Islands",
    "jersey": "Islands",
    "ireland": "Ireland",
}

# venue slug -> region, when the town page it was found on is in a different
# region from the venue itself (YLC pages reach across county lines).
VENUE_REGION = {
    # listed on Greater Manchester pages, but actually Cheshire / Merseyside
    "knutsford-curzon": "North West",
    "wilmslow-rex": "North West",
    "northwich-odeon": "North West",
    "st-helens-cineworld": "North West",
    "widnes-cheshire-reel": "North West",
    "warrington-odeon": "North West",
    "warrington-cineworld": "North West",
}


def region_for(slug: str, cities: list[str]) -> str | None:
    """Region for a venue: explicit override, else its first town page's region."""
    if slug in VENUE_REGION:
        return VENUE_REGION[slug]
    for city in cities:
        region = TOWN_REGION.get(city)
        if region:
            return region
    return None


def sort_key(region: str | None) -> tuple:
    """Sort helper — REGION_ORDER first (Greater Manchester top), then A–Z."""
    if region in REGION_ORDER:
        return (0, REGION_ORDER.index(region), "")
    return (1, 0, region or "zzz")
