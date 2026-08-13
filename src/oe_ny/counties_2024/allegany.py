"""Allegany County 2024 general (rotated-SOVC PDF, two contests side-by-side).

natural_pdf extract_tables recovers a grid where pages 1/3/4 each hold TWO
contests separated by an empty column.  Each block's office comes from its
precinct-column header; vote-column headers are '<candidate>\\n<party>'.  Rows
emitted in source order (left block then right block per page).  Parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
          "LaRouche": "LAR", "LAR": "LAR", "WFP": "WOR", "WF": "WOR",
          "IND": "IND", "GRE": "GRE", "LIB": "LIB", "SAM": "SAM"}

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
    ("U.S. House", "23", "DEM"): "Thomas A. Carle",
    ("U.S. House", "23", "REP"): "Nicholas A. Langworthy",
    ("U.S. House", "23", "CON"): "Nicholas A. Langworthy",
    ("State Senate", "57", "REP"): "George M. Borrello",
    ("State Senate", "57", "CON"): "George M. Borrello",
    ("State Senate", "58", "REP"): "Thomas F. O'Mara",
    ("State Senate", "58", "CON"): "Thomas F. O'Mara",
    ("State Assembly", "148", "DEM"): "Daniel J. Brown",
    ("State Assembly", "148", "REP"): "Joseph Sempolinski",
    ("State Assembly", "148", "CON"): "Joseph Sempolinski",
}
_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "23"),
          ("State Senate", "57"), ("State Senate", "58"),
          ("State Assembly", "148")]


def _classify(title):
    if not title:
        return None
    t = title.replace("\n", " ")
    low = t.lower()
    if "president" in low:
        return ("President", "")
    if "senator" in low:
        return ("U.S. Senate", "")
    if "congress" in low:
        m = re.search(r"Congress\D+(\d+)", t)
        return ("U.S. House", m.group(1) if m else "")
    if "senate" in low:
        m = re.search(r"(\d+)", t)
        return ("State Senate", m.group(1) if m else "")
    if "assembly" in low:
        m = re.search(r"(\d+)", t)
        return ("State Assembly", m.group(1) if m else "")
    return None


def _header_cell(cell):
    lines = [l.strip() for l in (cell or "").split("\n") if l.strip()]
    if not lines:
        return None
    if " ".join(lines).lower().replace("-", " ") == "write in":
        return ("WRITEIN", "")
    return (_PARTY.get(lines[-1], lines[-1]), " ".join(lines[:-1]))


def _is_text(cell):
    return bool(cell and cell.strip() and any(ch.isalpha() for ch in cell))


def _is_num(cell):
    return bool(cell and cell.strip().replace(",", "").isdigit())


def _i(s):
    return int(s.replace(",", ""))


def _parse_table(table, out, seen, prec_order, psum):
    if not table or not table[0]:
        return
    ncols = len(table[0])
    header_idx = next((i for i, r in enumerate(table)
                       if any("vote for" in (c or "").lower() for c in r)), None)
    if header_idx is None:
        return
    header = table[header_idx]
    data = table[header_idx + 1:]
    text_count = [sum(1 for r in data if _is_text(r[i] if i < len(r) else None))
                  for i in range(ncols)]
    precinct_cols = [i for i in range(ncols) if text_count[i] > 3]
    if len(precinct_cols) != 2:
        return
    left_pc, right_pc = precinct_cols
    left_votes = [i for i in range(left_pc + 1, right_pc)
                  if any(_is_num(r[i] if i < len(r) else None) for r in data)]
    right_votes = [i for i in range(right_pc + 1, ncols)
                   if any(_is_num(r[i] if i < len(r) else None) for r in data)]

    for pc, vote_cols in ((left_pc, left_votes), (right_pc, right_votes)):
        cls = _classify(header[pc] if pc < len(header) else None)
        if cls is None:
            continue
        office, district = cls
        col_party = [_header_cell(header[vi] if vi < len(header) else None)
                     for vi in vote_cols]
        for r in data:
            if pc >= len(r):
                continue
            precinct = (r[pc] or "").strip()
            if not precinct or precinct.lower() == "total":
                continue
            # candidate-total rows have empty vote cells -> skip
            if not any((r[vi] if vi < len(r) else None) and (r[vi] or "").strip()
                       for vi in vote_cols):
                continue
            seen_prec = False
            for vi, ph in zip(vote_cols, col_party):
                if ph is None:
                    continue
                val = r[vi] if vi < len(r) else None
                if not _is_num(val):
                    continue
                votes = _i(val)
                if votes == 0:
                    continue
                if not seen_prec:
                    if precinct not in seen:
                        seen.add(precinct)
                        prec_order.append(precinct)
                    seen_prec = True
                if ph[0] == "WRITEIN":
                    out.append((precinct, office, district, "", "Write-in", votes))
                else:
                    cand = CAND.get((office, district, ph[0]))
                    if cand is None:
                        continue
                    psum[(office, district, ph[0])] = \
                        psum.get((office, district, ph[0]), 0) + votes
                    out.append((precinct, office, district, ph[0], cand, votes))


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    out, prec_order, seen, psum = [], [], set(), {}
    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables or []:
            _parse_table(table, out, seen, prec_order, psum)
    return ParseResult(rows=out, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum)


CONFIG = CountyConfig(
    county="Allegany",
    slug="allegany",
    engine="sovc_table",
    source_name="Allegany.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
