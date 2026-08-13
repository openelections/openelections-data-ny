"""Clinton County 2024 general (XLSX, tidy long, split fusion).

'Election District Results' sheet = per-ED grand totals; 'Summary Results' gives
county totals for the anchor cross-check.  Source 'D. Billy Jones' -> 'Billy
Jones' (matches Essex/Clinton AD-115 in the committed corpus).
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
          ("State Senate", "45"), ("State Assembly", "115")]

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
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Senate", "45", "CON"): "Daniel G. Stec",
    ("State Assembly", "115", "DEM"): "Billy Jones",
}

ANCHORS = {
    ("President", "", "DEM"): 16489, ("President", "", "WOR"): 989,
    ("President", "", "REP"): 16814, ("President", "", "CON"): 1433,
    ("President", "", "_WI"): 253,
    ("U.S. Senate", "", "DEM"): 16900, ("U.S. Senate", "", "WOR"): 1714,
    ("U.S. Senate", "", "REP"): 14718, ("U.S. Senate", "", "CON"): 1391,
    ("U.S. Senate", "", "LAR"): 143, ("U.S. Senate", "", "_WI"): 17,
    ("U.S. House", "21", "DEM"): 15673, ("U.S. House", "21", "WOR"): 1335,
    ("U.S. House", "21", "REP"): 16790, ("U.S. House", "21", "CON"): 1628,
    ("U.S. House", "21", "_WI"): 29,
    ("State Senate", "45", "REP"): 21677, ("State Senate", "45", "CON"): 3838,
    ("State Senate", "45", "_WI"): 261,
    ("State Assembly", "115", "DEM"): 26626, ("State Assembly", "115", "_WI"): 184,
}

CONFIG = CountyConfig(
    county="Clinton",
    slug="clinton",
    engine="tidy",
    source_name="Clinton.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    fusion="split",
    engine_opts={
        "reader": "xlsx",
        "sheet": "Election District Results",
        "columns": {"precinct": 0, "office": 1, "ballot": 3, "party": 5, "total": 6},
        "summary_sheet": "Summary Results",
        "summary_columns": {"office": 0, "ballot": 2, "party": 4, "total": 5},
        "special_rows": {
            "ballots cast": "total",
            "over vote count": "over",
            "under vote count": "under",
        },
        "name_aliases": {"D. Billy Jones": "Billy Jones"},
    },
)
