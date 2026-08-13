"""Sullivan County 2024 general (XLSX 'Results', tidy long, split fusion).

New 2024 fusion line POP = People Over Politics (AD-100 Democrat).  Total Votes
Cast = candidates + write-ins only (Under/Over reported separately), so those
control rows are ignored rather than added to the per-precinct arithmetic.
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
          ("State Senate", "51"), ("State Assembly", "100"),
          ("State Assembly", "101")]

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
    ("U.S. House", "19", "DEM"): "Josh Riley",
    ("U.S. House", "19", "WOR"): "Josh Riley",
    ("U.S. House", "19", "REP"): "Marcus Molinaro",
    ("U.S. House", "19", "CON"): "Marcus Molinaro",
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Assembly", "100", "DEM"): "Paula Elaine Kay",
    ("State Assembly", "100", "POP"): "Paula Elaine Kay",
    ("State Assembly", "100", "REP"): "Louis J. Ingrassia, Jr.",
    ("State Assembly", "100", "CON"): "Louis J. Ingrassia, Jr.",
    ("State Assembly", "101", "REP"): "Brian M. Maher",
    ("State Assembly", "101", "CON"): "Brian M. Maher",
}

CONFIG = CountyConfig(
    county="Sullivan",
    slug="sullivan",
    engine="tidy",
    source_name="Sullivan.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    fusion="split",
    extra_parties=("POP",),
    engine_opts={
        "sheet": "Results",
        "columns": {"office": 0, "precinct": 2, "ballot": 3, "party": 4, "total": 5},
        "special_rows": {
            "total votes cast": "total",
            "total ballots cast": "ignore",
            "total registered voters": "ignore",
            "under votes": "ignore",
            "over votes": "ignore",
        },
    },
)
