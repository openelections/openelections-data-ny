"""Herkimer County 2024 general (rotated-SOVC PDF, natural_pdf extract_tables).

One contest per page; office detected from candidate surnames (no titles).  Each
party line is split into a machine column + an 'Abs/Aff' column — votes = their
sum.  Trailing Write-in / Void / Blank / Total are single columns.  Rows emitted
in source order.  Config-level parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR", "LAR": "LAR",
          "WFP": "WOR", "WF": "WOR", "LRP": "LAR"}
_CODES = set(_PARTY)

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
    ("U.S. House", "21", "REP"): "Elise Stefanik",
    ("U.S. House", "21", "CON"): "Elise Stefanik",
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Senate", "53", "DEM"): "James Meyers",
    ("State Senate", "53", "WOR"): "James Meyers",
    ("State Senate", "53", "REP"): "Joseph A. Griffo",
    ("State Senate", "53", "CON"): "Joseph A. Griffo",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
    ("State Assembly", "122", "DEM"): "Adrienne Martini",
    ("State Assembly", "122", "WOR"): "Adrienne Martini",
    ("State Assembly", "122", "REP"): "Brian Miller",
    ("State Assembly", "122", "CON"): "Brian Miller",
}

_MARKERS = [
    (("harris", "trump"), ("President", "")),
    (("gillibrand", "sapraicone", "sare"), ("U.S. Senate", "")),
    (("stefanik", "collins"), ("U.S. House", "21")),
    (("walczyk",), ("State Senate", "49")),
    (("griffo", "meyers"), ("State Senate", "53")),
    (("smullen",), ("State Assembly", "118")),
    (("martini", "miller"), ("State Assembly", "122")),
]
_ORDER = [od for _, od in _MARKERS]


def _ci(s):
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _header_party(cell):
    toks = (cell or "").split()
    if toks and toks[-1].strip("()") in _CODES:
        return _PARTY[toks[-1].strip("()")]
    return None


def _detect_office(header):
    blob = " ".join((c or "") for c in header).lower()
    for keys, od in _MARKERS:
        if any(k in blob for k in keys):
            return od
    return None


def _columns(header):
    specs = []
    j = 1
    while j < len(header):
        if _header_party(header[j]) is not None and j + 1 < len(header):
            specs.append(("candidate", j, _header_party(header[j]), j + 1))
            j += 2
            continue
        low = " ".join((header[j] or "").split()).lower().replace("-", " ")
        if "write" in low and "in" in low:
            specs.append(("writein", j))
        j += 1
    return specs


def _precinct(s):
    s = (s or "").strip()
    if s.startswith("C ") or s.startswith("T "):
        s = s[2:]
    toks = s.split()
    if not toks:
        return s
    last = toks[-1]
    town = " ".join(toks[:-1]).title()
    m = re.match(r"^W(\d+)$", last)
    if m:
        return f"{town} Ward {m.group(1)}"
    if last.isdigit():
        return f"{town} ED {int(last)}"
    return s.title()


def _is_data(name):
    s = (name or "").strip()
    if not s or s.isdigit() or s.lower() == "totals":
        return False
    low = s.lower()
    if "(w)" in low:
        return False
    if "write" in low and "in" in low.replace("-", ""):
        return False
    return True


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    rows, prec_order, seen, psum = [], [], set(), {}

    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        if not tables or not tables[0] or len(tables[0][0]) < 4:
            continue
        table = tables[0]
        specs = _columns(table[0])
        if not any(s[0] == "candidate" for s in specs):
            continue
        od = _detect_office(table[0])
        if od is None:
            continue
        office, district = od
        for r in table[1:]:
            if not r or not _is_data((r[0] or "").strip()):
                continue
            prec = _precinct((r[0] or "").strip())
            if prec not in seen:
                seen.add(prec)
                prec_order.append(prec)
            for s in specs:
                if s[0] == "candidate":
                    _, j, party, jabs = s
                    v = _ci(r[j] if j < len(r) else None) + \
                        _ci(r[jabs] if jabs < len(r) else None)
                    if v == 0:
                        continue
                    cand = CAND.get((office, district, party))
                    if cand is None:
                        continue
                    psum[(office, district, party)] = \
                        psum.get((office, district, party), 0) + v
                    rows.append((prec, office, district, party, cand, v))
                elif s[0] == "writein":
                    wv = _ci(r[s[1]] if s[1] < len(r) else None)
                    if wv > 0:
                        rows.append((prec, office, district, "", "Write-in", wv))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum)


CONFIG = CountyConfig(
    county="Herkimer",
    slug="herkimer",
    engine="sovc_table",
    source_name="Herkimer.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
