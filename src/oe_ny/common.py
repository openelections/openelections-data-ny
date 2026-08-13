"""Shared helpers for the NY OpenElections generic parsers.

Every per-county parser under the old ``src/2024/*_2024_parse.py`` layout
re-implemented the same handful of primitives (integer coercion, name
normalization, surname extraction, party-code normalization, precinct-name
cleanup) and the same party tables.  They live here once so the engines and
county configs can share them.

The party table is seeded from ``ny2024_rpp_parser.PARTY_FULL`` (the most
complete normalizer in the repo) and extended with the handful of fusion/minor
lines the dedicated parsers introduced (PFP, POP, RSF, ECO, "Local 607").
"""
from __future__ import annotations

import re
from typing import Callable

# --- small primitives (verbatim from the old per-county scripts) -----------

NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def to_int(v) -> int:
    """Coerce a cell value to int; blanks / non-numeric -> 0."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


# back-compat alias matching the name used across the old scripts
_int = to_int


def norm(name: str | None) -> str:
    """Strip to comparable lowercase letters only (for name cross-checks)."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


_norm = norm


def surname(name: str | None) -> str:
    """Last real token of a name, skipping Jr/Sr/II/III/IV suffixes."""
    toks = re.sub(r"[.,]", " ", (name or "")).split()
    while toks and toks[-1].lower().strip(".") in NAME_SUFFIX:
        toks.pop()
    return toks[-1] if toks else ""


# --- President running-mate stripping --------------------------------------

_ELECTORS_RE = re.compile(r"Electors for (.*?) for President", re.IGNORECASE)


def strip_vp(name: str | None) -> str:
    """Reduce a President ballot label to just the presidential candidate.

    Handles the several encodings seen across NY county sources:
      * "Electors for Kamala D. Harris for President Tim Walz for Vice ..."
      * "Kamala D. Harris and Tim Walz"
      * "Kamala D. Harris / Tim Walz"
      * ALL-CAPS variants of the above
    Names without a running mate pass through unchanged.
    """
    if name is None:
        return ""
    s = str(name).strip()
    m = _ELECTORS_RE.search(s)
    if m:
        return m.group(1).strip()
    for sep in (" and ", " / ", "/"):
        if sep in s:
            return s.split(sep, 1)[0].strip()
    return s


# --- party normalization ----------------------------------------------------

# Canonical order used for the PARTY_RANK sort key.  Counties append their own
# minor/fusion lines via CountyConfig.extra_parties.
BASE_PARTY_ORDER = ("DEM", "REP", "CON", "WOR", "LAR")

# Full spelling / variant -> canonical code.  Seeded to cover everything the
# per-county scripts normalized; the engines look up case-insensitively too.
PARTY_NORM: dict[str, str] = {
    "DEM": "DEM", "DEMOCRATIC": "DEM", "DEMOCRAT": "DEM", "DEMOCRATS": "DEM",
    "REP": "REP", "REPUBLICAN": "REP", "REPUBLICANS": "REP",
    "CON": "CON", "CONSERVATIVE": "CON",
    "WOR": "WOR", "WFP": "WOR", "WF": "WOR",
    "WORKING FAMILIES": "WOR", "WORKING FAMILI": "WOR", "WORK FAMILIES": "WOR",
    "LAR": "LAR", "LRP": "LAR", "LRC": "LAR", "LR": "LAR",
    "LAROUCHE": "LAR", "LA ROUCHE": "LAR", "LAROUC": "LAR",
    # minor / fusion lines introduced by the dedicated parsers
    "PFP": "PFP",
    "POP": "POP", "PEOPLE OVER POLITICS": "POP",
    "RSF": "RSF",
    "ECO": "ECO",
    "IND": "IND", "INDEPENDENCE": "IND",
    "LOCAL 607": "Local 607",
}


def party_code(raw: str | None) -> str | None:
    """Normalize a party spelling/code to a canonical code, or None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return PARTY_NORM.get(s) or PARTY_NORM.get(s.upper())


def party_rank(extra_parties: tuple[str, ...] = ()) -> dict[str, int]:
    """Build a party -> sort-rank map: base order then any county extras."""
    order = list(BASE_PARTY_ORDER) + [p for p in extra_parties
                                      if p not in BASE_PARTY_ORDER]
    return {p: i for i, p in enumerate(order)}


# --- precinct-name strategies ----------------------------------------------

_LD_RE = re.compile(r"\s+LD\s+\d+\b", re.IGNORECASE)
_ORDINAL_WARD_RE = re.compile(r"^(\d+)(?:ST|ND|RD|TH)\s+WARD\s+0*(\d+)$",
                              re.IGNORECASE)


def _pn_verbatim(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip()


def _pn_strip_ld(label: str) -> str:
    """Drop a trailing/embedded ' LD N' county-legislative-district tag."""
    return _pn_verbatim(_LD_RE.sub("", label))


def _pn_ordinal_ward(label: str) -> str:
    """'1ST WARD 01' -> '1st Ward 1' (Onondaga-style)."""
    s = _pn_verbatim(label)
    m = _ORDINAL_WARD_RE.match(s)
    if not m:
        return s
    n = int(m.group(1))
    suf = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
    return f"{n}{suf} Ward {int(m.group(2))}"


# name -> function; CountyConfig.precinct_name may be one of these keys or a
# custom Callable[[str], str].
PRECINCT_NAME_STRATEGIES: dict[str, Callable[[str], str]] = {
    "verbatim": _pn_verbatim,
    "strip_ld": _pn_strip_ld,
    "ordinal_ward": _pn_ordinal_ward,
}


def resolve_precinct_name(strategy) -> Callable[[str], str]:
    """Turn a config precinct_name (str key or Callable) into a function."""
    if callable(strategy):
        return strategy
    try:
        return PRECINCT_NAME_STRATEGIES[strategy]
    except KeyError:
        raise ValueError(f"unknown precinct_name strategy: {strategy!r}")


# --- standard NY office-title matching -------------------------------------

_OFFICE_RES = [
    (re.compile(r"Electors for President", re.IGNORECASE), "President", None),
    (re.compile(r"United States Senator", re.IGNORECASE), "U.S. Senate", None),
    (re.compile(r"Representative in Congress\D*(\d+)", re.IGNORECASE),
     "U.S. House", 1),
    (re.compile(r"State Senator\D*(\d+)", re.IGNORECASE), "State Senate", 1),
    (re.compile(r"Member of Assembly\D*(\d+)", re.IGNORECASE),
     "State Assembly", 1),
]


def standard_ny_office(name: str | None) -> tuple[str, str] | None:
    """Map a NY office title to (office, district) for the 5 canonical offices.

    Covers the common BOE spellings: 'Electors for President and Vice
    President', 'United States Senator', 'Representative in Congress 24th
    District', 'State Senator 54th District', 'Member of Assembly 133rd
    District'.  Returns None for any non-canonical office.
    """
    if not name:
        return None
    n = str(name).strip()
    for rx, office, grp in _OFFICE_RES:
        m = rx.search(n)
        if m:
            return (office, m.group(grp) if grp else "")
    return None


def town_code_expand(town_map: dict[str, str]) -> Callable[[str], str]:
    """Factory: expand a leading town code via a per-county dict.

    e.g. town_map={'CA': 'Carmel'} turns 'CA 01' into 'Carmel 1'.  Labels with
    no recognized code pass through verbatim.
    """
    def _fn(label: str) -> str:
        s = _pn_verbatim(label)
        m = re.match(r"^([A-Za-z]+)[\s-]+0*(\d+)$", s)
        if m and m.group(1) in town_map:
            return f"{town_map[m.group(1)]} {int(m.group(2))}"
        return s
    return _fn
