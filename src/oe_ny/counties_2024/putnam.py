"""Putnam County 2024 general (rotated-SOVC PDF, natural_pdf extract_tables).

Upright party-code row fixes the candidate columns; office from the upright page
title (President detected structurally).  President has 6 named write-in columns
(hardcoded cols 10-15) summed into the aggregate; other offices have a single
aggregate write-in column located structurally.  Precinct 'CA 01' -> 'Carmel ED
1'.  Rows emitted in source order.  Config-level parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_TOWN = {"CA": "Carmel", "KE": "Kent", "PA": "Patterson", "PH": "Philipstown",
         "PV": "Putnam Valley", "SE": "Southeast"}
_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR", "LAR": "LAR"}
_KNOWN = set(_PARTY) | {"IND", "GRE", "LIB", "SAM", "CMN"}

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
    ("U.S. House", "17", "DEM"): "Mondaire L. Jones",
    ("U.S. House", "17", "WOR"): "Mondaire L. Jones",
    ("U.S. House", "17", "REP"): "Mike Lawler",
    ("U.S. House", "17", "CON"): "Mike Lawler",
    ("State Senate", "39", "DEM"): "Yvette Valdes Smith",
    ("State Senate", "39", "WOR"): "Yvette Valdes Smith",
    ("State Senate", "39", "REP"): "Rob Rolison",
    ("State Senate", "39", "CON"): "Rob Rolison",
    ("State Senate", "40", "DEM"): "Peter B. Harckham",
    ("State Senate", "40", "WOR"): "Peter B. Harckham",
    ("State Senate", "40", "REP"): "Gina M. Arena",
    ("State Senate", "40", "CON"): "Gina M. Arena",
    ("State Assembly", "94", "DEM"): "Zachary C. Couzens",
    ("State Assembly", "94", "REP"): "Matthew J. Slater",
    ("State Assembly", "94", "CON"): "Matthew J. Slater",
    ("State Assembly", "95", "DEM"): "Dana Levenberg",
    ("State Assembly", "95", "WOR"): "Dana Levenberg",
    ("State Assembly", "95", "REP"): "Michael L. Capalbo",
    ("State Assembly", "95", "CON"): "Michael L. Capalbo",
}
_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "17"),
          ("State Senate", "39"), ("State Senate", "40"),
          ("State Assembly", "94"), ("State Assembly", "95")]


def _ci(c):
    s = (c or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _letters(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _kw(cell):
    f = re.sub(r"[^a-z]", "", (cell or "").lower())
    r = f[::-1]
    return {k for k in ("total", "vote", "void", "blank", "write", "over", "under")
            if k in f or k in r}


def _detect_office(up, table):
    if "UNITEDSTATESSENATOR" in up:
        return ("U.S. Senate", "")
    if "REPRESENTATIVEINCONGRESS" in up:
        m = re.search(r"(\d+)THCONGRESSIONALDISTRICT", up)
        return ("U.S. House", m.group(1) if m else "")
    if "MEMBEROFTHEASSEMBLY" in up:
        m = re.search(r"(\d+)THASSEMBLYDISTRICT", up)
        return ("State Assembly", m.group(1) if m else "")
    if "STATESENATOR" in up and "UNITEDSTATES" not in up:
        m = re.search(r"(\d+)THSENATORIALDISTRICT", up)
        return ("State Senate", m.group(1) if m else "")
    pset = {(c or "").strip().rstrip("*") for c in table[1]
            if (c or "").strip().rstrip("*") in _KNOWN}
    if pset == {"DEM", "REP", "CON", "WOR"} and len(table[0]) >= 20:
        return ("President", "")
    return None


def _cand_cols(table):
    out = []
    for j, c in enumerate(table[1]):
        code = (c or "").strip().rstrip("*")
        if code in _KNOWN:
            out.append((j, _PARTY.get(code, code)))
    return out


def _precinct(s):
    m = re.match(r"^([A-Z]{2})\s*0*(\d+)$", (s or "").strip())
    if not m:
        return (s or "").strip()
    return f"{_TOWN.get(m.group(1), m.group(1))} ED {m.group(2)}"


def _is_precinct(name):
    return bool(re.match(r"^[A-Z]{2}\s*\d+$", (name or "").strip()))


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    rows, prec_order, seen, psum = [], [], set(), {}

    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        if not tables or not tables[0] or len(tables[0]) < 3:
            continue
        table = tables[0]
        od = _detect_office(_letters(page.extract_text() or ""), table)
        if od is None:
            continue
        office, district = od
        cc = _cand_cols(table)
        if not cc:
            continue
        last_cand = max(j for j, _ in cc)
        if office == "President":
            wicols, wi_single = list(range(10, 16)), None
        else:
            tb = None
            for j in range(last_cand + 1, len(table[0])):
                if _kw(table[0][j]) >= {"total", "vote"}:
                    tb = j
                    break
            if tb is None or tb - 4 < 0:
                continue
            wicols, wi_single = None, tb - 1

        for r in table[2:]:
            name = (r[0] or "").strip()
            if not _is_precinct(name):
                continue
            prec = _precinct(name)
            if prec not in seen:
                seen.add(prec)
                prec_order.append(prec)
            for j, party in cc:
                v = _ci(r[j] if j < len(r) else None)
                if v == 0:
                    continue
                cand = CAND.get((office, district, party))
                if cand is None:
                    continue
                psum[(office, district, party)] = \
                    psum.get((office, district, party), 0) + v
                rows.append((prec, office, district, party, cand, v))
            if wicols is not None:
                wv = sum(_ci(r[j] if j < len(r) else 0) for j in wicols)
            else:
                wv = _ci(r[wi_single] if wi_single < len(r) else 0)
            if wv > 0:
                rows.append((prec, office, district, "", "Write-in", wv))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum)


CONFIG = CountyConfig(
    county="Putnam",
    slug="putnam",
    engine="sovc_table",
    source_name="Putnam.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
