"""Montgomery County 2024 general (HTML 'Results per Precinct').

Like Wayne/Schoharie but col0 label is 'ED' and party is a TRAILING token on
each candidate cell ('Paul D. Tonko DEM', 'Diane Sare LaRouche', 'Angelo L.
Santabarbara People First' -> PFP).  Source has candidate-name typos, so the
name cross-check is by surname.
"""
from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""),
          ("U.S. House", "20"), ("U.S. House", "21"),
          ("State Senate", "46"),
          ("State Assembly", "111"), ("State Assembly", "118")]

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
    ("State Senate", "46", "DEM"): "Patricia A. Fahy",
    ("State Senate", "46", "WOR"): "Patricia A. Fahy",
    ("State Senate", "46", "REP"): "Ted Danz Jr.",
    ("State Senate", "46", "CON"): "Ted Danz Jr.",
    ("State Assembly", "111", "DEM"): "Angelo L. Santabarbara",
    ("State Assembly", "111", "PFP"): "Angelo L. Santabarbara",
    ("State Assembly", "111", "REP"): "Joseph C. Mastroianni",
    ("State Assembly", "111", "CON"): "Joseph C. Mastroianni",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
}

_SURNAME = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "tonko": ("U.S. House", "20"), "waltz": ("U.S. House", "20"),
    "collins": ("U.S. House", "21"), "stefanik": ("U.S. House", "21"),
    "fahy": ("State Senate", "46"), "danz": ("State Senate", "46"),
    "santabarbara": ("State Assembly", "111"),
    "mastroianni": ("State Assembly", "111"),
    "smullen": ("State Assembly", "118"),
}

CONFIG = CountyConfig(
    county="Montgomery",
    slug="montgomery",
    engine="tabular",
    source_name="Montgomery.html",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    extra_parties=("PFP",),
    engine_opts={
        "mode": "html_tables",
        "header_style": "trailing_party_token",
        "precinct_label": "ed",
        "surname_office": _SURNAME,
        "name_check": "surname",
        "writein_prefixes": ("write-ins", "write-in", "write in"),
        # split-office Total rows cover the whole county (not just the split's
        # precincts) and one source Total is internally inconsistent; the
        # per-precinct data is authoritative, so skip the Total cross-check.
        "capture_total": False,
    },
)
