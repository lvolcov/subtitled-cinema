"""
cinema_meta.py — static, hand-curated metadata that the source pages don't
provide: approximate coordinates for the "nearest cinema" feature.

Keyed by the slug of the cinema name (see build_site.slugify). Coordinates are
approximate (venue-level), good enough to sort by distance. Venues without an
entry still appear — they're just excluded from distance ordering.
"""

# slug -> (lat, lng)
COORDS = {
    "manchester-trafford-odeon": (53.4668, -2.3487),
    "manchester-great-northern-odeon": (53.4779, -2.2489),
    "manchester-quayside-vue": (53.4709, -2.2967),
    "manchester-printworks-vue": (53.4855, -2.2377),
    "manchester-home": (53.4738, -2.2470),
    "manchester-everyman": (53.4760, -2.2530),
    "stockport-light": (53.4084, -2.1494),
    "wilmslow-rex": (53.3269, -2.2314),
    "altrincham-vue": (53.3875, -2.3490),
    "altrincham-everyman": (53.3873, -2.3513),
    "knutsford-curzon": (53.3027, -2.3717),
    "didsbury-cineworld": (53.4188, -2.2196),
    # Greater Manchester ring (added with the bolton/bury/ashton/warrington pages)
    "bolton-vue": (53.5876, -2.5540),
    "bolton-cineworld": (53.5788, -2.4283),
    "bolton-light": (53.5820, -2.4290),
    "wigan-omniplex": (53.5487, -2.6461),
    "rochdale-odeon": (53.5920, -2.1780),
    "rochdale-reel": (53.6136, -2.1553),
    "ashton-under-lyne-cineworld": (53.4890, -2.1090),
    "oldham-odeon": (53.5210, -2.1370),
    "northwich-odeon": (53.2590, -2.5180),
    "st-helens-cineworld": (53.4530, -2.7370),
    "warrington-odeon": (53.3950, -2.6180),
    "warrington-cineworld": (53.3860, -2.5810),
    "widnes-cheshire-reel": (53.3620, -2.7290),
}
