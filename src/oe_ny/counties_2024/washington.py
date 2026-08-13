"""Washington County 2024 general (per-candidate PDF report, natural_pdf text).

Per-candidate (not per-party-line): each candidate row has ONE combined fusion
total and a party cell like 'DEM, WOR', so fusion is emitted on the PRIMARY line
(first party-code token).  Each precinct prints in three sections (regular / ABS
/ Fed ABS) summed.  Output is canonically sorted.  Config-level parse override.
"""
import re

from ..model import CountyConfig, ParseResult

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("U.S. Senate", "", "DEM"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "REP"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "LAR"): "Diane Sare",
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("State Senate", "43", "DEM"): "Alvin Gamble",
    ("State Senate", "43", "REP"): "Jake Ashby",
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Assembly", "107", "DEM"): "Chloe E. Pierce",
    ("State Assembly", "107", "REP"): "Scott H. Bendett",
    ("State Assembly", "113", "DEM"): "Carrie Woerner",
    ("State Assembly", "113", "REP"): "Jeremy Messina",
    ("State Assembly", "114", "REP"): "Matthew J. Simpson",
}

_CANON = [
    ("electors for president", "President", ""),
    ("united states senator", "U.S. Senate", ""),
    ("representative in congress 21st", "U.S. House", "21"),
    ("state senator 43rd", "State Senate", "43"),
    ("state senator 45th", "State Senate", "45"),
    ("member of assembly 107th", "State Assembly", "107"),
    ("member of assembly 113th", "State Assembly", "113"),
    ("member of assembly 114th", "State Assembly", "114"),
]
_ORDER = [(o, d) for _, o, d in _CANON]
_PARTY_CODES = {"DEM", "REP", "CON", "WOR", "LAR", "IND"}

_HEADER_RE = re.compile(r"^(.+?) (\d[\d,]+) of (\d[\d,]+) registered voters =")
_PAIR_RE = re.compile(r"(\d[\d,]*)\s+\d+\.\d+%")


def _ci(tok):
    s = (tok or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _office_of(title):
    low = title.lower()
    if "vote for one" not in low:
        return None
    for sub, o, d in _CANON:
        if sub in low:
            return (o, d)
    return None


def _precinct(raw):
    s = re.sub(r"\s*-\s*(Fed ABS|ABS)\s*$", "", raw.strip())
    m = re.match(r"^(.+?) District (\d+)$", s)
    return f"{m.group(1)} {m.group(2)}" if m else f"{s} 1"


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    cand, wi = {}, {}
    prec_order, seen = [], set()
    cur_prec_raw = cur_od = None

    for page in pdf.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            hm = _HEADER_RE.match(line)
            if hm:
                cur_prec_raw = hm.group(1).strip()
                norm = _precinct(cur_prec_raw)
                if norm not in seen:
                    seen.add(norm)
                    prec_order.append(norm)
                continue
            if "vote for one" in line.lower():
                cur_od = _office_of(line)
                continue
            if cur_prec_raw is None or cur_od is None:
                continue
            office, district = cur_od
            low = line.lower()
            if low.startswith(("cast votes:", "undervotes", "overvotes")):
                continue
            pairs = _PAIR_RE.findall(line)
            if len(pairs) != 5:
                continue
            total = _ci(pairs[-1])
            norm = _precinct(cur_prec_raw)
            nkey = (norm, office, district)
            party = None
            for t in line.split():
                u = re.sub(r"[^A-Za-z]", "", t)
                if u in _PARTY_CODES:
                    party = u
                    break
            if party is not None and (office, district, party) in CAND:
                k = (norm, office, district, party)
                cand[k] = cand.get(k, 0) + total
            elif "(W)" in line or "( W )" in line:
                if "void" not in low:
                    wi[nkey] = wi.get(nkey, 0) + total
            elif party is None and total > 0:
                wi[nkey] = wi.get(nkey, 0) + total

    rows, psum = [], {}
    for (norm, office, district, party), v in cand.items():
        psum[(office, district, party)] = psum.get((office, district, party), 0) + v
        if v > 0:
            rows.append((norm, office, district, party, CAND[(office, district, party)], v))
    for (norm, office, district), v in wi.items():
        if v > 0:
            rows.append((norm, office, district, "", "Write-in", v))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum)


CONFIG = CountyConfig(
    county="Washington",
    slug="washington",
    engine="text_report",
    source_name="Washington.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    parse=_parse,
)
