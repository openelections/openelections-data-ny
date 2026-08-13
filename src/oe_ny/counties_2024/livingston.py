"""Livingston County 2024 general (XLSX, tidy long, split fusion)."""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "24"),
          ("State Senate", "54"), ("State Assembly", "133")]

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
    ("U.S. House", "24", "DEM"): "David Wagenhauser",
    ("U.S. House", "24", "REP"): "Claudia Tenney",
    ("U.S. House", "24", "CON"): "Claudia Tenney",
    ("State Senate", "54", "DEM"): "Scott Comegys",
    ("State Senate", "54", "REP"): "Pamela A. Helming",
    ("State Senate", "54", "CON"): "Pamela A. Helming",
    ("State Assembly", "133", "DEM"): "Colleen Walsh-Williams",
    ("State Assembly", "133", "REP"): "Andrea K. Bailey",
    ("State Assembly", "133", "CON"): "Andrea K. Bailey",
}

ANCHORS = {
    ("President", "", "DEM"): 11468, ("President", "", "WOR"): 680,
    ("President", "", "REP"): 16746, ("President", "", "CON"): 2034,
    ("President", "", "_WI"): 257,
    ("U.S. Senate", "", "DEM"): 11550, ("U.S. Senate", "", "WOR"): 1280,
    ("U.S. Senate", "", "REP"): 15282, ("U.S. Senate", "", "CON"): 2088,
    ("U.S. Senate", "", "LAR"): 127, ("U.S. Senate", "", "_WI"): 17,
    ("U.S. House", "24", "DEM"): 10323, ("U.S. House", "24", "REP"): 17217,
    ("U.S. House", "24", "CON"): 2399, ("U.S. House", "24", "_WI"): 19,
    ("State Senate", "54", "DEM"): 9544, ("State Senate", "54", "REP"): 17607,
    ("State Senate", "54", "CON"): 2463, ("State Senate", "54", "_WI"): 9,
    ("State Assembly", "133", "DEM"): 9437, ("State Assembly", "133", "REP"): 17799,
    ("State Assembly", "133", "CON"): 2490, ("State Assembly", "133", "_WI"): 14,
}

CONFIG = CountyConfig(
    county="Livingston",
    slug="livingston",
    engine="tidy",
    source_name="Livingston.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    fusion="split",
    engine_opts={
        "sheet": "Election District Results",
        "columns": {"precinct": 0, "office": 1, "ballot": 3, "party": 5, "total": 6},
        "summary_sheet": "Summary Results",
        "summary_columns": {"office": 0, "ballot": 2, "party": 4, "total": 5},
        "special_rows": {
            "ballots cast": "total",
            "over vote count": "over",
            "under vote count": "under",
        },
    },
)
