"""Chenango County 2024 general (rotated-SOVC PDF, counting-group SOVC).

Only 'Counting Group - All' sections are the grand total (others double-count).
Vote-column headers come from extract_tables (clean), but precinct names come
from extract_text (extract_tables drops the spaces), split as
name = tokens[:-N], votes = tokens[-N:] where N = table columns - 1.  Aggregate
Write-in column is the true write-in total (named write-in columns skipped).
Rows emitted in source order.  Config-level parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
          "LaRouche": "LAR", "LAR": "LAR", "WFP": "WOR", "WF": "WOR"}

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
    ("U.S. House", "19", "DEM"): "Josh Riley",
    ("U.S. House", "19", "WOR"): "Josh Riley",
    ("U.S. House", "19", "REP"): "Marcus Molinaro",
    ("U.S. House", "19", "CON"): "Marcus Molinaro",
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Senate", "53", "DEM"): "James Meyers",
    ("State Senate", "53", "WOR"): "James Meyers",
    ("State Senate", "53", "REP"): "Joseph A. Griffo",
    ("State Senate", "53", "CON"): "Joseph A. Griffo",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}
_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
          ("State Senate", "51"), ("State Senate", "53"),
          ("State Assembly", "121"), ("State Assembly", "131")]


def _is_int(s):
    return bool(s) and s.replace(",", "").isdigit()


def _i(s):
    return int(s.replace(",", ""))


def _office_of(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    office_line = next((l for l in lines if l.startswith("Office:")), "")
    district_line = next((l for l in lines if l.startswith("District:") and
                          ("Senatorial" in l or "Assembly District" in l)), "")
    o = office_line.lower()
    if "president" in o:
        return ("President", "")
    if "united states senator" in o:
        return ("U.S. Senate", "")
    if "congress" in o:
        m = re.search(r"(\d+)\w*\s*District", office_line)
        return ("U.S. House", m.group(1) if m else "")
    if "state senator" in o:
        m = re.search(r"(\d+)", district_line)
        return ("State Senate", m.group(1) if m else "")
    if "member of assembly" in o:
        m = re.search(r"(\d+)", district_line)
        return ("State Assembly", m.group(1) if m else "")
    return None


def _col_header(cell):
    if not cell:
        return ("unknown", "")
    m = re.search(r"\(([^)]+)\)", cell)
    if m:
        code = m.group(1).strip()
        if "write" in code.lower():
            return ("writein_individual", "")
        return ("candidate", _PARTY.get(code, code))
    cleaned = " ".join(cell.split()).lower().replace("-", " ")
    if "write" in cleaned and "in" in cleaned:
        return ("writein_aggregate", "")
    return ("other", "")


def _all_section(text):
    lines = text.splitlines()
    group_idx = [i for i, l in enumerate(lines) if "Group" in l]
    all_idx = next((i for i in group_idx if "All" in lines[i]), None)
    if all_idx is None:
        return []
    end_idx = next((i for i in group_idx if i > all_idx), len(lines))
    return lines[all_idx:end_idx]


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    rows, prec_order, seen, psum = [], [], set(), {}

    for page in pdf.pages:
        text = page.extract_text() or ""
        section = _all_section(text)
        if not section:
            continue
        cls = _office_of(text)
        if cls is None:
            continue
        office, district = cls
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        if not tables or not tables[0] or not tables[0][0]:
            continue
        hdr = tables[0][0]
        n_votes = len(hdr) - 1
        cols = [_col_header(hdr[i]) for i in range(1, len(hdr))]

        for raw in section:
            tokens = raw.split()
            if len(tokens) < n_votes + 1:
                continue
            votes = tokens[-n_votes:]
            if not all(_is_int(v) for v in votes):
                continue
            name_tokens = tokens[:-n_votes]
            if not name_tokens or not name_tokens[0][:1].isalpha():
                continue
            precinct = " ".join(name_tokens)
            if precinct.lower() == "total":
                continue
            emitted = False
            for i, v in enumerate(votes):
                vi = _i(v)
                if vi == 0:
                    continue
                kind, party = cols[i]
                if kind == "candidate":
                    cand = CAND.get((office, district, party))
                    if cand is None:
                        continue
                    if not emitted and precinct not in seen:
                        seen.add(precinct)
                        prec_order.append(precinct)
                    emitted = True
                    psum[(office, district, party)] = \
                        psum.get((office, district, party), 0) + vi
                    rows.append((precinct, office, district, party, cand, vi))
                elif kind == "writein_aggregate":
                    if not emitted and precinct not in seen:
                        seen.add(precinct)
                        prec_order.append(precinct)
                    emitted = True
                    rows.append((precinct, office, district, "", "Write-in", vi))

    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER),
                       psum=psum)


CONFIG = CountyConfig(
    county="Chenango",
    slug="chenango",
    engine="sovc_table",
    source_name="Chenango.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    sort_output=False,
    parse=_parse,
)
