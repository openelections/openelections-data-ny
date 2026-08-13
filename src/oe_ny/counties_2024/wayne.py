"""Wayne County 2024 general (HTML 'Results per Precinct', one table per contest).

Header cells 'Name - PARTY' (column order non-standard, so party is read per
column); office identified by candidate surnames; single aggregate Write-in
column; verified against each table's Total row.
"""
import re

from ..model import CountyConfig

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "24"),
          ("State Senate", "54"), ("State Assembly", "130")]


def _precinct(label: str) -> str:
    s = re.sub(r"\s+", " ", str(label)).strip()
    s = re.sub(r"^Town of\s+", "", s)
    s = re.sub(r"\s+LD\s+\d+$", "", s)
    s = re.sub(r"^City of\s+", "", s)
    return s.strip()


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
    ("State Assembly", "130", "DEM"): "James Schuler",
    ("State Assembly", "130", "REP"): "Brian D. Manktelow",
    ("State Assembly", "130", "CON"): "Brian D. Manktelow",
}

_SURNAME = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "wagenhauser": ("U.S. House", "24"), "tenney": ("U.S. House", "24"),
    "comegys": ("State Senate", "54"), "helming": ("State Senate", "54"),
    "schuler": ("State Assembly", "130"), "manktelow": ("State Assembly", "130"),
}

CONFIG = CountyConfig(
    county="Wayne",
    slug="wayne",
    engine="tabular",
    source_name="Wayne.html",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    precinct_name=_precinct,
    engine_opts={
        "mode": "html_tables",
        "header_style": "name_dash_party",
        "precinct_label": "precinct",
        "surname_office": _SURNAME,
        "bare_name_role": "writein",
    },
)
