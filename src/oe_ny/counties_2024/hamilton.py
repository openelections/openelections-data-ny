"""Hamilton County 2024 general (XLSX single sheet, block-per-office, name-dash).

Smallest NY county (11 EDs), wholly in NY-21/SD-49/AD-118.  No per-precinct
total column; the AD-118 REP 'Total' row prints 2362 vs the true per-precinct
sum 2358 (a 4-vote BOE quirk), so capture_total is off and the anchor is the
per-precinct sum.  Source header typos fixed via name_aliases.
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
          ("State Senate", "49"), ("State Assembly", "118")]

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "WOR"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("President", "", "CON"): "Donald J. Trump",
    ("U.S. Senate", "", "DEM"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "WOR"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "REP"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "CON"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "LAR"): "Diane Sare",
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "WOR"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
}

ANCHORS = {
    ("President", "", "DEM"): 1136, ("President", "", "WOR"): 75,
    ("President", "", "REP"): 2052, ("President", "", "CON"): 171,
    ("President", "", "_WI"): 5,
    ("U.S. Senate", "", "DEM"): 1168, ("U.S. Senate", "", "WOR"): 115,
    ("U.S. Senate", "", "REP"): 1873, ("U.S. Senate", "", "CON"): 180,
    ("U.S. Senate", "", "LAR"): 13, ("U.S. Senate", "", "_WI"): 1,
    ("U.S. House", "21", "DEM"): 1019, ("U.S. House", "21", "WOR"): 83,
    ("U.S. House", "21", "REP"): 2089, ("U.S. House", "21", "CON"): 205,
    ("U.S. House", "21", "_WI"): 3,
    ("State Senate", "49", "REP"): 2324, ("State Senate", "49", "CON"): 295,
    ("State Senate", "49", "_WI"): 7,
    ("State Assembly", "118", "REP"): 2358, ("State Assembly", "118", "CON"): 310,
    ("State Assembly", "118", "_WI"): 15,
}

CONFIG = CountyConfig(
    county="Hamilton",
    slug="hamilton",
    engine="tabular",
    source_name="Hamilton.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    engine_opts={
        "mode": "blocks",
        "sheet": "Contest overview",
        "title_marker": "(Vote for 1)",
        "office_titles": [
            ("President and Vice President", "President", ""),
            ("United States Senator", "U.S. Senate", ""),
            ("Representative In Congress", "U.S. House", "21"),
            ("Representative in Congress", "U.S. House", "21"),
            ("State Senator", "State Senate", "49"),
            ("Member of Assembly", "State Assembly", "118"),
        ],
        "header_style": "name_dash_party",
        "ed_label": "ED",
        "writein_prefixes": ("write-in", "write in"),
        "over_prefixes": ("void",),
        "capture_total": False,
        "president_comma": True,
        "name_aliases": {
            "Kristen E. Gillibrand": "Kirsten E. Gillibrand",
            "Michael D.Sapraicone": "Michael D. Sapraicone",
            "Robert J. Smullen": "Robert Smullen",
        },
    },
)
