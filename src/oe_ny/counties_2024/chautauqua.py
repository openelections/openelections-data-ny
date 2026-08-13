"""Chautauqua County 2024 general (XLSX, per-sheet SOVC, two-row header).

Row 0 = candidate names (repeated across a fusion candidate's columns), row 1 =
a party CODE per column (TOTAL / DEM / WOR / REP / CON / LAR / RSF / W-IN).
Each candidate = a TOTAL column + one column per party line; write-ins are a
'W-IN' column or individual named columns (code blank).  Candidate names are
taken verbatim from row 0.  Config-level parse override.
"""
from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_SHEETS = [
    ("President and Vice President", "President", ""),
    ("United States Senator", "U.S. Senate", ""),
    ("Rep in Congress (23 CD)", "U.S. House", "23"),
    ("State Senator (57 SD)", "State Senate", "57"),
    ("Member of Assembly (150 AD)", "State Assembly", "150"),
]
_ORDER = [(o, d) for _, o, d in _SHEETS]

_REAL_PARTIES = {"DEM", "REP", "CON", "WOR", "LAR", "RSF", "IND", "GRE", "LIB",
                 "SAM", "WEP"}


def _clean_name(cell):
    if cell is None:
        return ""
    return str(cell).split("\n", 1)[0].replace("*", "").strip()


def _parse(cfg: CountyConfig) -> ParseResult:
    import openpyxl
    wb = openpyxl.load_workbook(cfg.resolve_source(), data_only=True)
    acc = Accumulator(cfg)

    for sheet_name, office, district in _SHEETS:
        rows = [list(r) for r in wb[sheet_name].iter_rows(values_only=True)]
        if len(rows) < 3:
            continue
        row0, row1 = rows[0], rows[1]
        party_cols, wi_cols = [], []
        ncol = max(len(row0), len(row1))
        for j in range(2, ncol):
            name = _clean_name(row0[j] if j < len(row0) else None)
            code = row1[j] if j < len(row1) else None
            code = str(code).strip() if code is not None else ""
            low = name.lower()
            if low in ("over votes", "overvotes", "over vote",
                       "under votes", "undervotes", "under vote"):
                continue
            if code in _REAL_PARTIES:
                party_cols.append((j, code, name))
            elif code == "TOTAL":
                continue
            elif code == "W-IN" or (name and not code):
                wi_cols.append(j)
        acc.see_od((office, district))
        for r in rows[2:]:
            c0 = (str(r[0]).strip() if r and r[0] is not None else "")
            if not c0 or c0.upper() == "TOTALS":
                continue
            prec = acc.precinct(c0)
            for j, party, name in party_cols:
                v = to_int(r[j] if j < len(r) else None)
                acc.candidate(prec, office, district, party, v, name=name)
            acc.writein(prec, office, district,
                        sum(to_int(r[j] if j < len(r) else None) for j in wi_cols))
    return acc.result()


CONFIG = CountyConfig(
    county="Chautauqua",
    slug="chautauqua",
    engine="tabular",
    source_name="Chautauqua.xlsx",
    office_order=_ORDER,
    cand={},
    anchors={},
    extra_parties=("RSF",),
    parse=_parse,
)
