"""Cayuga County 2024 general (CSV, multiple office blocks).

Each block = office-title row (col0 only) + an 'Election District' header row
whose cells are 'Name (Party)' + a 'Write-in' column + Over/Under columns +
precinct rows + a 'Total' row.  Candidate names are taken verbatim from the
header (no CAND map); party labels are truncated variants normalized below.
Config-level parse override.
"""
import csv
import re

from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "22"),
          ("U.S. House", "24"), ("State Senate", "48"),
          ("State Assembly", "120"), ("State Assembly", "126"),
          ("State Assembly", "131")]

_PARTY = {
    "DEM": "DEM", "DEMOCRATIC": "DEM", "DEMOCRAT": "DEM",
    "REP": "REP", "REPUBLICAN": "REP", "REPUBLICANS": "REP",
    "CON": "CON", "CONSERVATIVE": "CON", "CONSER": "CON", "CONSV": "CON",
    "WOR": "WOR", "WORKING FAMILIES": "WOR", "WORKINGFAMILIES": "WOR",
    "FAMILIES": "WOR", "FAMILI": "WOR", "WFP": "WOR", "WF": "WOR",
    "LAR": "LAR", "LAROUCHE": "LAR", "LAROUC": "LAR", "LAROUCH": "LAR",
    "IND": "IND", "INDEPENDENCE": "IND",
}
_NAME_PARTY_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")
_WI = ("write-in", "write in", "writeins", "write-ins")
_CTRL = ("over votes", "undervotes", "under votes", "overvotes", "over vote",
         "under vote", "yes", "no")


def _office_of(title):
    t = title.strip()
    if t == "Presidential Electors for President and Vice President":
        return ("President", "")
    if t == "United States Senator":
        return ("U.S. Senate", "")
    for rx, office in ((r"Representative in Congress D(\d+)$", "U.S. House"),
                       (r"State Senate D(\d+)$", "State Senate"),
                       (r"Member of Assembly (\d+)$", "State Assembly")):
        m = re.match(rx, t)
        if m:
            return (office, m.group(1))
    return None


def _party_of(raw):
    return _PARTY.get(re.sub(r"\s+", " ", raw.strip().upper()))


def _parse_header(row):
    cand, wi = [], None
    for j, cell in enumerate(row):
        if j == 0:
            continue
        c = (cell or "").strip()
        if not c:
            continue
        if c.lower() in _WI:
            wi = j
            continue
        if c.lower() in _CTRL:
            continue
        m = _NAME_PARTY_RE.match(c)
        if not m:
            continue
        name, party = m.group(1).strip(), _party_of(m.group(2))
        if party and name:
            cand.append((j, party, name))
    return cand, wi


def _parse(cfg: CountyConfig) -> ParseResult:
    with open(cfg.resolve_source(), newline="") as f:
        rows = list(csv.reader(f))
    acc = Accumulator(cfg)
    cur_od = None
    cur_cand, cur_wi = [], None
    for row in rows:
        if not row or not any((c or "").strip() for c in row):
            continue
        c0 = (row[0] or "").strip()
        c1 = (row[1] or "").strip() if len(row) > 1 else ""
        if c0 and not c1 and c0 != "Election District":
            cur_od = _office_of(c0)
            cur_cand, cur_wi = [], None
            if cur_od:
                acc.see_od(cur_od)
            continue
        if c0 == "Election District":
            if cur_od is not None:
                cur_cand, cur_wi = _parse_header(row)
            continue
        if cur_od is None or not cur_cand:
            continue
        office, district = cur_od
        if c0 == "Total":
            for j, party, name in cur_cand:
                acc.set_col_total(office, district, party,
                                  to_int(row[j] if j < len(row) else None))
            if cur_wi is not None:
                acc.set_wi_total(office, district,
                                 to_int(row[cur_wi] if cur_wi < len(row) else None))
            continue
        prec = acc.precinct(c0)
        for j, party, name in cur_cand:
            v = to_int(row[j] if j < len(row) else None)
            acc.candidate(prec, office, district, party, v, name=name)
        if cur_wi is not None:
            acc.writein(prec, office, district,
                        to_int(row[cur_wi] if cur_wi < len(row) else None))
    return acc.result()


CONFIG = CountyConfig(
    county="Cayuga",
    slug="cayuga",
    engine="tabular",
    source_name="Cayuga.csv",
    office_order=_ORDER,
    cand={},
    anchors={},
    parse=_parse,
)
