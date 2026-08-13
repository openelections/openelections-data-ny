"""Greene County 2024 general (XLSX, per-sheet SOVC, name-over-party header).

WFP -> WOR; President named write-in columns are bare-name headers; ' LD N'
stripped from precinct labels; Total Votes column is inconsistently defined so
the per-precinct total check is skipped (tv_mode 'either').
"""
from ..model import CountyConfig

_SHEETS = [
    ("Presidential", "President", ""),
    ("US Senator", "U.S. Senate", ""),
    ("Congress", "U.S. House", "19"),
    ("State Senator", "State Senate", "41"),
    ("Assembly", "State Assembly", "102"),
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
    ("State Senate", "41", "DEM"): "Michelle Hinchey",
    ("State Senate", "41", "WOR"): "Michelle Hinchey",
    ("State Senate", "41", "REP"): "Patrick Sheehan",
    ("State Senate", "41", "CON"): "Patrick Sheehan",
    ("State Assembly", "102", "DEM"): "Janet S. Tweed",
    ("State Assembly", "102", "WOR"): "Janet S. Tweed",
    ("State Assembly", "102", "REP"): "Christopher Tague",
    ("State Assembly", "102", "CON"): "Christopher Tague",
}

ANCHORS = {
    ("President", "", "DEM"): 9437, ("President", "", "WOR"): 999,
    ("President", "", "REP"): 13058, ("President", "", "CON"): 1644,
    ("President", "", "_WI"): 302,
    ("U.S. Senate", "", "DEM"): 9650, ("U.S. Senate", "", "WOR"): 1483,
    ("U.S. Senate", "", "REP"): 11751, ("U.S. Senate", "", "CON"): 1684,
    ("U.S. Senate", "", "LAR"): 123, ("U.S. Senate", "", "_WI"): 21,
    ("U.S. House", "19", "DEM"): 8898, ("U.S. House", "19", "WOR"): 1290,
    ("U.S. House", "19", "REP"): 12908, ("U.S. House", "19", "CON"): 1818,
    ("U.S. House", "19", "_WI"): 18,
    ("State Senate", "41", "DEM"): 9665, ("State Senate", "41", "WOR"): 1533,
    ("State Senate", "41", "REP"): 11779, ("State Senate", "41", "CON"): 1689,
    ("State Senate", "41", "_WI"): 12,
    ("State Assembly", "102", "DEM"): 8017, ("State Assembly", "102", "WOR"): 1193,
    ("State Assembly", "102", "REP"): 13433, ("State Assembly", "102", "CON"): 1982,
    ("State Assembly", "102", "_WI"): 12,
}

CONFIG = CountyConfig(
    county="Greene",
    slug="greene",
    engine="tabular",
    source_name="Greene.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    precinct_name="strip_ld",
    engine_opts={
        "header_style": "name_newline_party",
        "sheets": _SHEETS,
        "ed_label": "ED",
        "writein_prefixes": ("unqualified write-ins", "unqualified writeins"),
        "over_prefixes": ("overvotes",),
        "under_prefixes": ("undervotes",),
        "tv_labels": ("total votes",),
        "tv_mode": "either",
        "bare_name_role": "writein",
        "skip_prefixes": ("counting", "district", "vote", "area", "official",
                          "greene", "general", "nys", "(vote"),
    },
)
