"""Rensselaer County 2024 general (XLSX, per-sheet SOVC, name-paren header).

One sheet per contest; header row has col0 'Election District' and candidate
cells 'Name/\\nRunning Mate (Party)' (Con->CON, LaRouc->LAR).  Single aggregate
Write-in column; Over/Under/TOTAL VOTES columns skipped; per-sheet Total row is
the anchor.
"""
from ..model import CountyConfig

_SHEETS = [
    ("PRESIDENT", "President", ""),
    ("US SENATOR", "U.S. Senate", ""),
    ("19TH CONGRESSIONAL", "U.S. House", "19"),
    ("20TH CONGRESSIONAL", "U.S. House", "20"),
    ("43RD STATE SENATE", "State Senate", "43"),
    ("107TH ASSEMBLY", "State Assembly", "107"),
    ("108TH ASSEMBLY", "State Assembly", "108"),
]
_ORDER = [(o, d) for _, o, d in _SHEETS]

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
    ("U.S. House", "20", "DEM"): "Paul D. Tonko",
    ("U.S. House", "20", "WOR"): "Paul D. Tonko",
    ("U.S. House", "20", "REP"): "Kevin M. Waltz",
    ("U.S. House", "20", "CON"): "Kevin M. Waltz",
    ("State Senate", "43", "DEM"): "Alvin Gamble",
    ("State Senate", "43", "REP"): "Jake Ashby",
    ("State Senate", "43", "CON"): "Jake Ashby",
    ("State Assembly", "107", "DEM"): "Chloe E. Pierce",
    ("State Assembly", "107", "REP"): "Scott H. Bendett",
    ("State Assembly", "107", "CON"): "Scott H. Bendett",
    ("State Assembly", "108", "DEM"): "John T. McDonald III",
}

CONFIG = CountyConfig(
    county="Rensselaer",
    slug="rensselaer",
    engine="tabular",
    source_name="Rensselaer.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    engine_opts={
        "header_style": "name_paren_party",
        "sheets": _SHEETS,
        "ed_label": "Election District",
        "writein_prefixes": ("write-in",),
        "tv_mode": "either",
    },
)
