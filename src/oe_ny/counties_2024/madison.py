"""Madison County 2024 general (XLSX, tidy long, split fusion).

Custom precinct-name cleanup: drop a placeholder ' LD N' suffix and collapse
'City of Oneida Ward W E' -> 'City of Oneida W' to match the committed 2022 set.
Source 'Brian D. Miller' -> 'Brian Miller' (committed AD-122).
"""
import re

from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "22"),
          ("State Senate", "53"), ("State Assembly", "121"),
          ("State Assembly", "122"), ("State Assembly", "127"),
          ("State Assembly", "131")]


def _precinct(label: str) -> str:
    s = re.sub(r"\s+", " ", str(label)).strip()
    s = re.sub(r" LD \d+$", "", s)
    s = re.sub(r"^City of Oneida Ward (\d+) \d+$", r"City of Oneida \1", s)
    return s


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
    ("U.S. House", "22", "DEM"): "John W. Mannion",
    ("U.S. House", "22", "WOR"): "John W. Mannion",
    ("U.S. House", "22", "REP"): "Brandon M. Williams",
    ("U.S. House", "22", "CON"): "Brandon M. Williams",
    ("State Senate", "53", "DEM"): "James Meyers",
    ("State Senate", "53", "WOR"): "James Meyers",
    ("State Senate", "53", "REP"): "Joseph A. Griffo",
    ("State Senate", "53", "CON"): "Joseph A. Griffo",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
    ("State Assembly", "122", "DEM"): "Adrienne Martini",
    ("State Assembly", "122", "WOR"): "Adrienne Martini",
    ("State Assembly", "122", "REP"): "Brian Miller",
    ("State Assembly", "122", "CON"): "Brian Miller",
    ("State Assembly", "127", "DEM"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "WOR"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "REP"): "Timothy R. Kelly",
    ("State Assembly", "127", "CON"): "Timothy R. Kelly",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}

ANCHORS = {
    ("President", "", "DEM"): 13652, ("President", "", "WOR"): 977,
    ("President", "", "REP"): 17084, ("President", "", "CON"): 1941,
    ("President", "", "_WI"): 365,
    ("U.S. Senate", "", "DEM"): 13633, ("U.S. Senate", "", "WOR"): 1505,
    ("U.S. Senate", "", "REP"): 15700, ("U.S. Senate", "", "CON"): 2027,
    ("U.S. Senate", "", "LAR"): 157, ("U.S. Senate", "", "_WI"): 35,
    ("U.S. House", "22", "DEM"): 13230, ("U.S. House", "22", "WOR"): 1382,
    ("U.S. House", "22", "REP"): 16578, ("U.S. House", "22", "CON"): 2146,
    ("U.S. House", "22", "_WI"): 40,
    ("State Senate", "53", "DEM"): 11344, ("State Senate", "53", "WOR"): 1202,
    ("State Senate", "53", "REP"): 18053, ("State Senate", "53", "CON"): 2354,
    ("State Senate", "53", "_WI"): 18,
    ("State Assembly", "121", "DEM"): 2828, ("State Assembly", "121", "REP"): 3527,
    ("State Assembly", "121", "CON"): 508, ("State Assembly", "121", "_WI"): 5,
    ("State Assembly", "122", "DEM"): 6372, ("State Assembly", "122", "WOR"): 673,
    ("State Assembly", "122", "REP"): 11015, ("State Assembly", "122", "CON"): 1380,
    ("State Assembly", "122", "_WI"): 13,
    ("State Assembly", "127", "DEM"): 2146, ("State Assembly", "127", "WOR"): 157,
    ("State Assembly", "127", "REP"): 1610, ("State Assembly", "127", "CON"): 220,
    ("State Assembly", "127", "_WI"): 3,
    ("State Assembly", "131", "REP"): 1451, ("State Assembly", "131", "CON"): 297,
    ("State Assembly", "131", "_WI"): 12,
}

CONFIG = CountyConfig(
    county="Madison",
    slug="madison",
    engine="tidy",
    source_name="Madison.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    fusion="split",
    precinct_name=_precinct,
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
        "name_aliases": {"Brian D. Miller": "Brian Miller"},
    },
)
