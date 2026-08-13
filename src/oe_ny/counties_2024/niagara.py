"""Niagara County 2024 general (CSV, tidy long, COMBINED fusion -> primary line).

Source has no totals; anchors are the official NYS ENR countywide numbers.
Source 'William C. Conrad, III' -> 'William C. Conrad III' (committed AD-140).
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "23"),
          ("U.S. House", "24"), ("U.S. House", "26"), ("State Senate", "62"),
          ("State Assembly", "140"), ("State Assembly", "144"),
          ("State Assembly", "145")]

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("U.S. Senate", "", "DEM"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "REP"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "LAR"): "Diane Sare",
    ("U.S. House", "23", "DEM"): "Thomas A. Carle",
    ("U.S. House", "23", "REP"): "Nicholas A. Langworthy",
    ("U.S. House", "24", "DEM"): "David Wagenhauser",
    ("U.S. House", "24", "REP"): "Claudia Tenney",
    ("U.S. House", "26", "DEM"): "Timothy M. Kennedy",
    ("U.S. House", "26", "REP"): "Anthony G. Marecki",
    ("State Senate", "62", "REP"): "Robert G. Ortt",
    ("State Assembly", "140", "DEM"): "William C. Conrad III",
    ("State Assembly", "144", "DEM"): "Michelle M. Roman",
    ("State Assembly", "144", "REP"): "Paul A. Bologna",
    ("State Assembly", "145", "DEM"): "Jeffrey Elder",
    ("State Assembly", "145", "REP"): "Angelo J. Morinello",
}

ANCHORS = {
    ("President", "", "DEM"): 43438, ("President", "", "REP"): 58678,
    ("President", "", "_WI"): 802,
    ("U.S. Senate", "", "DEM"): 44641, ("U.S. Senate", "", "REP"): 53851,
    ("U.S. Senate", "", "LAR"): 409, ("U.S. Senate", "", "_WI"): 53,
    ("U.S. House", "23", "DEM"): 3857, ("U.S. House", "23", "REP"): 7179,
    ("U.S. House", "23", "_WI"): 9,
    ("U.S. House", "24", "DEM"): 14795, ("U.S. House", "24", "REP"): 27174,
    ("U.S. House", "24", "_WI"): 15,
    ("U.S. House", "26", "DEM"): 22520, ("U.S. House", "26", "REP"): 20462,
    ("U.S. House", "26", "_WI"): 18,
    ("State Senate", "62", "REP"): 73640, ("State Senate", "62", "_WI"): 511,
    ("State Assembly", "140", "DEM"): 6403, ("State Assembly", "140", "_WI"): 28,
    ("State Assembly", "144", "DEM"): 14275, ("State Assembly", "144", "REP"): 23333,
    ("State Assembly", "144", "_WI"): 17,
    ("State Assembly", "145", "DEM"): 19087, ("State Assembly", "145", "REP"): 30110,
    ("State Assembly", "145", "_WI"): 18,
}

CONFIG = CountyConfig(
    county="Niagara",
    slug="niagara",
    engine="tidy",
    source_name="Niagara.csv",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    fusion="primary-only",
    engine_opts={
        "reader": "csv",
        "columns": {"precinct": "District Name", "office": "Contest",
                    "ballot": "Candidate Issue", "party": "Party",
                    "total": "Total Votes"},
        "fusion_sep": ";",
        "name_aliases": {"William C. Conrad, III": "William C. Conrad III"},
    },
)
