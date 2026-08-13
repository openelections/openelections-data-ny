"""Warren County 2024 general (PDF 'Election Book', per-ED detail pages).

pdfplumber extract_text.  Each contest = one detail page (per-ED rows with a Dst
column) + a 'Summary --' rollup page (skipped).  Column order is fixed per
office (hardcoded below, matching the source's non-standard order); a data row
is  <label> <Dst> <WHOLE> <cand cols...> <WRITE-IN> <Voids>.  A new ward starts
whenever Dst resets to 1; precinct = 'Town [- Ward W] ED'.  Parse override.
"""
import re

from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
          ("State Senate", "45"), ("State Assembly", "113"),
          ("State Assembly", "114")]

# candidate columns in physical (source) order per office-district
_PARTIES = {
    ("President", ""): ["DEM", "WOR", "REP", "CON"],
    ("U.S. Senate", ""): ["DEM", "WOR", "REP", "CON", "LAR"],
    ("U.S. House", "21"): ["DEM", "WOR", "REP", "CON"],
    ("State Senate", "45"): ["REP", "CON"],
    ("State Assembly", "113"): ["DEM", "REP", "CON"],
    ("State Assembly", "114"): ["REP", "CON"],
}

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
    ("State Assembly", "113", "DEM"): "Carrie Woerner",
    ("State Assembly", "113", "REP"): "Jeremy Messina",
    ("State Assembly", "113", "CON"): "Jeremy Messina",
    ("State Assembly", "114", "REP"): "Matthew J. Simpson",
    ("State Assembly", "114", "CON"): "Matthew J. Simpson",
}


def _office_of_title(t):
    t = (t or "").strip()
    if t.startswith("Summary --"):
        return None
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    if "REPRESENTATIVE IN CONGRESS" in t:
        return ("U.S. House", "21")
    if "STATE SENATOR" in t:
        return ("State Senate", "45")
    m = re.search(r"MEMBER OF ASSEMBLY\s*\((\d+)\w*\)", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


def _town_name(label_upper):
    m = re.match(r"CITY OF\s+(.+)", label_upper)
    return (m.group(1) if m else label_upper).title()


def _is_num(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _parse(cfg: CountyConfig) -> ParseResult:
    import pdfplumber
    # pass 1: collect rows + per-group max ward; pass 2: name + emit
    data = []          # (od, group, ward, dst, cand_vals, wi)
    group_town, group_max_ward = {}, {}
    grand = {}         # od -> [whole, cand..., wi, voids]

    with pdfplumber.open(cfg.resolve_source()) as pdf:
        for page in pdf.pages:
            lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()]
            if not lines:
                continue
            od = _office_of_title(lines[0])
            if od is None or od not in _PARTIES:
                continue
            office, district = od
            n = len(_PARTIES[od])
            cur_group = None
            ward = 0
            for l in lines[1:]:
                toks = l.split()
                i = 0
                while i < len(toks) and not _is_num(toks[i]):
                    i += 1
                if i == len(toks):
                    continue
                label, nums = toks[:i], toks[i:]
                if not all(_is_num(t) for t in nums):
                    continue
                vals = [to_int(t) for t in nums]
                lab = " ".join(label).upper()
                if "TOTAL" in lab:
                    if len(vals) == n + 3 and od not in grand:
                        grand[od] = vals
                    continue
                if len(vals) != n + 4:
                    continue
                dst = vals[0]
                if dst > 999:
                    continue
                cand_vals = vals[2:2 + n]
                wi = vals[2 + n]
                if label:
                    cur_group = (od, tuple(label))
                    ward = 0
                    group_town[cur_group] = _town_name(lab)
                if cur_group is None:
                    continue
                if dst == 1:
                    ward += 1
                group_max_ward[cur_group] = max(group_max_ward.get(cur_group, 0), ward)
                data.append((od, cur_group, ward, dst, cand_vals, wi))

    acc = Accumulator(cfg)
    for od in _ORDER:
        if od in grand:
            acc.see_od(od)
    for od, group, ward, dst, cand_vals, wi in data:
        office, district = od
        town = group_town[group]
        prec = acc.precinct(f"{town} - Ward {ward} {dst}"
                            if group_max_ward[group] > 1 else f"{town} {dst}")
        for j, p in enumerate(_PARTIES[od]):
            acc.candidate(prec, office, district, p, cand_vals[j])
        acc.writein(prec, office, district, wi)

    for od, vals in grand.items():
        office, district = od
        n = len(_PARTIES[od])
        for j, p in enumerate(_PARTIES[od]):
            acc.set_col_total(office, district, p, vals[1 + j])
        acc.set_wi_total(office, district, vals[1 + n])
    return acc.result()


CONFIG = CountyConfig(
    county="Warren",
    slug="warren",
    engine="election_book",
    source_name="Warren.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    parse=_parse,
)
