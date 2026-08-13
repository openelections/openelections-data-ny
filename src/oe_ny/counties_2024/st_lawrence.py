"""St. Lawrence County 2024 general (rotated-SOVC PDF, natural_pdf extract_text).

Rotated candidate names are ignored; the upright party-code row + a hardcoded
per-office party list fix the columns.  Each precinct row (parsed from text):
  <precinct...> <turnout> <reg> <%> <cand*N> <cand-totals*> <Write-in> <TVC>.
Candidate columns = first N tokens after '%'; Write-in/TVC = last two.  Rows are
emitted in source order (committed CSV is not canonically sorted).
"""
import re

from ..model import CountyConfig, ParseResult

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
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Senate", "45", "CON"): "Daniel G. Stec",
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Assembly", "116", "REP"): "Scott A. Gray",
    ("State Assembly", "116", "CON"): "Scott A. Gray",
    ("State Assembly", "117", "REP"): "Kenneth Blankenbush",
    ("State Assembly", "117", "CON"): "Kenneth Blankenbush",
}

# (office, district, start_page, end_page[1-indexed], [party codes in col order])
_OFFICES = [
    ("President", "", 1, 5, ["DEM", "REP", "CON", "WOR"]),
    ("U.S. Senate", "", 6, 10, ["DEM", "REP", "CON", "WOR", "LAR"]),
    ("U.S. House", "21", 11, 15, ["DEM", "REP", "CON", "WOR"]),
    ("State Senate", "45", 16, 19, ["REP", "CON"]),
    ("State Senate", "49", 20, 21, ["REP", "CON"]),
    ("State Assembly", "116", 22, 24, ["REP", "CON"]),
    ("State Assembly", "117", 25, 26, ["REP", "CON"]),
]
_ORDER = [(o, d) for o, d, *_ in _OFFICES]


def _ci(tok):
    s = (tok or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _is_num(tok):
    return (tok or "").replace(",", "").strip().isdigit()


def _parse_row(line, n):
    toks = line.split()
    pct_idx = next((i for i, t in enumerate(toks) if re.match(r"^\d+%$", t)), None)
    if pct_idx is None or pct_idx < 3:
        return None
    if not (_is_num(toks[pct_idx - 2]) and _is_num(toks[pct_idx - 1])):
        return None
    precinct_toks = toks[:pct_idx - 2]
    if not precinct_toks or not precinct_toks[0][:1].isalpha():
        return None
    after = toks[pct_idx + 1:]
    if len(after) < n + 2:
        return None
    cand = after[:n]
    if not all(_is_num(c) for c in cand):
        return None
    if not (_is_num(after[-2]) and _is_num(after[-1])):
        return None
    return (" ".join(precinct_toks), [_ci(c) for c in cand],
            _ci(after[-2]), _ci(after[-1]))


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    rows, prec_order, seen, psum, col_total = [], [], set(), {}, {}

    for office, district, p0, p1, parties in _OFFICES:
        n = len(parties)
        for p in range(p0, p1 + 1):
            text = pdf.pages[p - 1].extract_text() or ""
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                is_total = line.split()[0].upper() == "TOTAL"
                parsed = _parse_row(line, n)
                if parsed is None:
                    continue
                precinct, cand, writein, _tvc = parsed
                if is_total:
                    for i, party in enumerate(parties):
                        col_total[(office, district, party)] = cand[i]
                    continue
                if precinct not in seen:
                    seen.add(precinct)
                    prec_order.append(precinct)
                for i, party in enumerate(parties):
                    v = cand[i]
                    if v <= 0:
                        continue
                    name = CAND.get((office, district, party))
                    if name is None:
                        continue
                    psum[(office, district, party)] = \
                        psum.get((office, district, party), 0) + v
                    rows.append((precinct, office, district, party, name, v))
                if writein > 0:
                    rows.append((precinct, office, district, "", "Write-in", writein))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum, col_total=col_total)


CONFIG = CountyConfig(
    county="St. Lawrence",
    slug="st_lawrence",
    engine="sovc_table",
    source_name="St Lawrence.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
