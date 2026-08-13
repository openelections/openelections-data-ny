"""Monroe County 2024 general (XLSX 'Election Book DETAIL', President only).

Single merged-cell sheet with fixed candidate columns (5/7/9/11 = DEM/REP/CON/
WOR, 13 = SCATTER), grouped by 'Leg. Dist. NN' / town header rows.  Precinct =
'<group> <ED>'.  Config-level parse override.
"""
from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", "")]

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "WOR"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("President", "", "CON"): "Donald J. Trump",
}

_CITY_WIDE = {"CITY", "TOWNS", "GRAND TOTAL:", "GRAND TOTAL"}


def _is_ed(c0):
    if isinstance(c0, bool):
        return False
    if isinstance(c0, (int, float)):
        return True
    return isinstance(c0, str) and c0.strip().isdigit()


def _parse(cfg: CountyConfig) -> ParseResult:
    import openpyxl
    wb = openpyxl.load_workbook(cfg.resolve_source(), data_only=True)
    rows = [list(r) for r in wb.active.iter_rows(values_only=True)]

    party_idx = None
    for i, r in enumerate(rows):
        if r and len(r) > 5 and str(r[5]).strip().upper() == "DEM":
            party_idx = i
            break
    if party_idx is None:
        return Accumulator(cfg).result()
    pr = rows[party_idx]
    col_party, wi_col = {}, None
    for j in range(5, len(pr)):
        v = str(pr[j]).strip().upper()
        if v in ("DEM", "REP", "CON", "WOR", "LAR"):
            col_party[j] = v
        elif v == "SCATTER":
            wi_col = j

    acc = Accumulator(cfg)
    acc.see_od(("President", ""))
    cur_group = None
    for r in rows[party_idx + 1:]:
        c0 = r[0] if r else None
        if c0 is None:
            continue
        s0 = str(c0).strip()
        if not s0:
            continue
        if _is_ed(c0):
            if cur_group is None:
                continue
            ed = int(float(c0)) if isinstance(c0, (int, float)) else int(s0)
            prec = acc.precinct(f"{cur_group} {ed}")
            for j, party in col_party.items():
                acc.candidate(prec, "President", "", party,
                              to_int(r[j] if j < len(r) else None))
            if wi_col is not None:
                acc.writein(prec, "President", "",
                            to_int(r[wi_col] if wi_col < len(r) else None))
            continue
        if s0.upper() in _CITY_WIDE:
            if s0.upper().startswith("GRAND TOTAL"):
                for j, party in col_party.items():
                    acc.set_col_total("President", "", party,
                                      to_int(r[j] if j < len(r) else None))
                if wi_col is not None:
                    acc.set_wi_total("President", "",
                                     to_int(r[wi_col] if wi_col < len(r) else None))
            continue
        c3 = r[3] if len(r) > 3 else None
        c3_blank = c3 is None or (isinstance(c3, str) and not c3.strip())
        if c3_blank:
            cur_group = s0
    return acc.result()


CONFIG = CountyConfig(
    county="Monroe",
    slug="monroe",
    engine="election_book",
    source_name="Monroe.xlsx",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    parse=_parse,
)
