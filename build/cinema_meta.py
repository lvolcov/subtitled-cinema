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
}
