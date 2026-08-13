"""Franklin County 2024 general (XLSX, per-sheet SOVC, name-over-party header)."""
from ..model import CountyConfig

_SHEETS = [
    ("Electors for President and Vice", "President", ""),
    ("US Senator ", "U.S. Senate", ""),
    ("Rep to Congress (21st)", "U.S. House", "21"),
    ("State Senator (45th)", "State Senate", "45"),
    ("Member of Assembly (115th)", "State Assembly", "115"),
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
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "WOR"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Senate", "45", "CON"): "Daniel G. Stec",
    ("State Assembly", "115", "DEM"): "Billy Jones",
}

ANCHORS = {
    ("President", "", "DEM"): 8358, ("President", "", "WOR"): 463,
    ("President", "", "REP"): 9775, ("President", "", "CON"): 794,
    ("President", "", "_WI"): 68,
    ("U.S. Senate", "", "DEM"): 8519, ("U.S. Senate", "", "WOR"): 838,
    ("U.S. Senate", "", "REP"): 8713, ("U.S. Senate", "", "CON"): 768,
    ("U.S. Senate", "", "LAR"): 64, ("U.S. Senate", "", "_WI"): 6,
    ("U.S. House", "21", "DEM"): 7869, ("U.S. House", "21", "WOR"): 655,
    ("U.S. House", "21", "REP"): 9812, ("U.S. House", "21", "CON"): 868,
    ("U.S. House", "21", "_WI"): 10,
    ("State Senate", "45", "REP"): 12027, ("State Senate", "45", "CON"): 2140,
    ("State Senate", "45", "_WI"): 102,
    ("State Assembly", "115", "DEM"): 13278, ("State Assembly", "115", "_WI"): 85,
}

CONFIG = CountyConfig(
    county="Franklin",
    slug="franklin",
    engine="tabular",
    source_name="Franklin.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    engine_opts={
        "header_style": "name_newline_party",
        "sheets": _SHEETS,
        "ed_label": "ED",
        "writein_prefixes": ("write-in",),
        "over_prefixes": ("void",),
        "under_prefixes": ("blank",),
        "tv_labels": ("total votes",),
        "tv_mode": "sum_all",
        "name_aliases": {"D. Billy Jones": "Billy Jones"},
    },
)
