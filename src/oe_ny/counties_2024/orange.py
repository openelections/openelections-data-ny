"""Orange County 2024 general (rotated-SOVC PDF, President only, natural_pdf).

extract_text garbles the rotated candidate names, but natural_pdf's
extract_tables recovers a clean grid whose second header row carries upright
party codes (REP/CON/DEM/WOR).  Rows are emitted in source column order (the
committed CSV is not canonically sorted), so sort_output=False.  Config-level
parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_ORDER = [("President", "")]
_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
          "WFP": "WOR", "WF": "WOR", "LAR": "LAR", "IND": "IND",
          "GRE": "GRE", "LIB": "LIB", "SAM": "SAM", "CMN": "CMN"}
_CODES = set(_PARTY)

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "WOR"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("President", "", "CON"): "Donald J. Trump",
}


def _ci(s):
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _is_totals(name):
    return (name or "").lower().strip() in ("totals", "total", "grand total",
                                            "grand totals")


def _is_data(name):
    s = (name or "").strip()
    if not s or s.isdigit() or _is_totals(s):
        return False
    return " - " in s or re.search(r"D\d{3}", s) is not None


def _precinct(s):
    parts = [p.strip() for p in (s or "").strip().split(" - ")]
    if not parts:
        return s
    town = parts[0]
    ward = ed = None
    for p in parts[1:]:
        m = re.match(r"^W0*(\d+)$", p)
        if m:
            ward = int(m.group(1))
            continue
        m = re.match(r"^D0*(\d+)$", p)
        if m:
            ed = int(m.group(1))
    town = town if town.startswith("City of ") else town.title()
    out = town
    if ward is not None:
        out += f" Ward {ward}"
    if ed is not None:
        out += f" ED {ed}"
    return out


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    rows = []
    prec_order = []
    seen = set()
    psum = {}

    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        if not tables or not tables[0] or len(tables[0]) < 3:
            continue
        table = tables[0]
        header0 = [(c or "") for c in table[0]]
        ncols = len(header0)
        party_row = None
        for r in table[1:4]:
            codes = [(j, (c or "").strip()) for j, c in enumerate(r)
                     if (c or "").strip() in _CODES]
            if len(codes) >= 2:
                party_row = codes
                break
        if not party_row:
            continue
        cand_cols = [(j, _PARTY[code]) for j, code in party_row]
        last_cand = max(j for j, _ in cand_cols)
        writein_idx = None
        for j in range(last_cand + 1, ncols):
            if "write" in (header0[j].lower() if j < len(header0) else ""):
                writein_idx = j
                break
        if writein_idx is None and last_cand + 1 < ncols:
            writein_idx = last_cand + 1

        for r in table:
            if not r or not _is_data((r[0] or "").strip()):
                continue
            prec = _precinct((r[0] or "").strip())
            if prec not in seen:
                seen.add(prec)
                prec_order.append(prec)
            for j, party in cand_cols:
                v = _ci(r[j] if j < len(r) else None)
                if v == 0:
                    continue
                cand = CAND.get(("President", "", party))
                if cand is None:
                    continue
                psum[("President", "", party)] = psum.get(("President", "", party), 0) + v
                rows.append((prec, "President", "", party, cand, v))
            if writein_idx is not None:
                wv = _ci(r[writein_idx] if writein_idx < len(r) else None)
                if wv > 0:
                    rows.append((prec, "President", "", "", "Write-in", wv))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=[("President", "")],
                       psum=psum)


CONFIG = CountyConfig(
    county="Orange",
    slug="orange",
    engine="sovc_table",
    source_name="Orange.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
