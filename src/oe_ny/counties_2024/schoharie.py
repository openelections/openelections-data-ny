"""Schoharie County 2024 general (HTML 'Results per Precinct', same as Wayne).

Precinct names verbatim ('Town of Blenheim 1 LD 1').
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
          ("State Senate", "51"), ("State Assembly", "102")]

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
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Assembly", "102", "DEM"): "Janet S. Tweed",
    ("State Assembly", "102", "WOR"): "Janet S. Tweed",
    ("State Assembly", "102", "REP"): "Christopher Tague",
    ("State Assembly", "102", "CON"): "Christopher Tague",
}

_SURNAME = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "collins": ("U.S. House", "21"), "stefanik": ("U.S. House", "21"),
    "frazier": ("State Senate", "51"), "oberacker": ("State Senate", "51"),
    "tweed": ("State Assembly", "102"), "tague": ("State Assembly", "102"),
}

CONFIG = CountyConfig(
    county="Schoharie",
    slug="schoharie",
    engine="tabular",
    source_name="Schoharie.HTML",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    engine_opts={
        "mode": "html_tables",
        "header_style": "name_dash_party",
        "precinct_label": "precinct",
        "surname_office": _SURNAME,
        "bare_name_role": "writein",
    },
)
