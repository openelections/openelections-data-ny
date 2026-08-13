"""Saratoga County 2024 general (XLSX 'Election Book', surname-block SOVC).

Single sheet, offices grouped by town; each office block's header carries
'Name (Party)' cells and the office is identified by candidate surnames.  Total
rows are summed across the per-town repeats.  No hardcoded anchors — the block
Total sum is the cross-check.
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "20"),
          ("U.S. House", "21"), ("State Senate", "44"),
          ("State Assembly", "108"), ("State Assembly", "112"),
          ("State Assembly", "113"), ("State Assembly", "114")]

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
    ("U.S. House", "20", "DEM"): "Paul D. Tonko",
    ("U.S. House", "20", "WOR"): "Paul D. Tonko",
    ("U.S. House", "20", "REP"): "Kevin M. Waltz",
    ("U.S. House", "20", "CON"): "Kevin M. Waltz",
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "WOR"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "44", "DEM"): "Minita J. Sanghvi",
    ("State Senate", "44", "WOR"): "Minita J. Sanghvi",
    ("State Senate", "44", "REP"): "James N. Tedisco",
    ("State Senate", "44", "CON"): "James N. Tedisco",
    ("State Assembly", "108", "DEM"): "John T. McDonald III",
    ("State Assembly", "112", "DEM"): "Joe Seeman",
    ("State Assembly", "112", "WOR"): "Joe Seeman",
    ("State Assembly", "112", "REP"): "Mary Beth Walsh",
    ("State Assembly", "112", "CON"): "Mary Beth Walsh",
    ("State Assembly", "113", "DEM"): "Carrie Woerner",
    ("State Assembly", "113", "WOR"): "Carrie Woerner",
    ("State Assembly", "113", "REP"): "Jeremy Messina",
    ("State Assembly", "113", "CON"): "Jeremy Messina",
    ("State Assembly", "114", "REP"): "Matthew J. Simpson",
    ("State Assembly", "114", "CON"): "Matthew J. Simpson",
}

_SURNAME = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "tonko": ("U.S. House", "20"), "waltz": ("U.S. House", "20"),
    "collins": ("U.S. House", "21"), "stefanik": ("U.S. House", "21"),
    "sanghvi": ("State Senate", "44"), "tedisco": ("State Senate", "44"),
    "mcdonald": ("State Assembly", "108"),
    "seeman": ("State Assembly", "112"), "walsh": ("State Assembly", "112"),
    "woerner": ("State Assembly", "113"), "messina": ("State Assembly", "113"),
    "simpson": ("State Assembly", "114"),
}

CONFIG = CountyConfig(
    county="Saratoga",
    slug="saratoga",
    engine="tabular",
    source_name="Saratoga.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    engine_opts={
        "mode": "blocks_by_surname",
        "surname_office": _SURNAME,
        "non_cand": ("write-ins", "write-in", "write in", "blanks", "voids"),
    },
)
