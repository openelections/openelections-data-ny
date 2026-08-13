"""Onondaga County 2024 general (PDF 'Election Book', natural_pdf extract_text).

Letter-coded columns in canonical NY ballot order (party assigned positionally
from the CAND map filtered to DEM/REP/CON/WOR/LAR).  Data row:
  <ward/town label> <Dst> <WHOLE> <cand cols...> <WRITE-IN> <Voids>.
Ward/town names carry forward on continuation rows.  Precinct = Syracuse
'<ordinal> Ward <ED>' or town '<TOWN> <ED>'.  Config-level parse override.
"""
import re

from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "22"),
          ("State Senate", "48"), ("State Senate", "50"),
          ("State Assembly", "126"), ("State Assembly", "127"),
          ("State Assembly", "128"), ("State Assembly", "129")]
_CANON = ["DEM", "REP", "CON", "WOR", "LAR"]

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
    ("U.S. House", "22", "DEM"): "John W. Mannion",
    ("U.S. House", "22", "WOR"): "John W. Mannion",
    ("U.S. House", "22", "REP"): "Brandon M. Williams",
    ("U.S. House", "22", "CON"): "Brandon M. Williams",
    ("State Senate", "48", "DEM"): "Rachel May",
    ("State Senate", "48", "WOR"): "Rachel May",
    ("State Senate", "48", "REP"): "Caleb C. Slater",
    ("State Senate", "50", "DEM"): "Christopher J. Ryan",
    ("State Senate", "50", "WOR"): "Christopher J. Ryan",
    ("State Senate", "50", "REP"): "Nick Paro",
    ("State Senate", "50", "CON"): "Nick Paro",
    ("State Assembly", "126", "DEM"): "Ian Phillips",
    ("State Assembly", "126", "WOR"): "Ian Phillips",
    ("State Assembly", "126", "REP"): "John Lemondes Jr.",
    ("State Assembly", "126", "CON"): "John Lemondes Jr.",
    ("State Assembly", "127", "DEM"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "WOR"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "REP"): "Timothy R. Kelly",
    ("State Assembly", "127", "CON"): "Timothy R. Kelly",
    ("State Assembly", "128", "DEM"): "Pamela Jo Hunter",
    ("State Assembly", "128", "WOR"): "Pamela Jo Hunter",
    ("State Assembly", "128", "REP"): "Daniel A. Ciciarelli",
    ("State Assembly", "128", "CON"): "Daniel A. Ciciarelli",
    ("State Assembly", "129", "DEM"): "William B. Magnarelli",
}


def _office_of_title(t):
    t = (t or "").strip()
    if t.startswith("Summary --"):
        return None
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    m = re.search(r"REPRESENTATIVE IN CONGRESS\s*-\s*DISTRICT\s*(\d+)", t)
    if m:
        return ("U.S. House", m.group(1))
    if "STATE SENATOR" in t:
        m = re.search(r"(\d+)", t)
        if m:
            return ("State Senate", m.group(1))
    m = re.search(r"MEMBER OF ASSEMBLY\s*-\s*DISTRICT\s*(\d+)", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


def _ordinal(n):
    n = int(n)
    if 11 <= n % 100 <= 13:
        s = "th"
    else:
        s = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{s}"


def _precinct(label_tokens, dst):
    dst_int = int(dst)
    if "WARD" in label_tokens:
        m = re.match(r"(\d+)", label_tokens[0])
        return f"{_ordinal(m.group(1))} Ward {dst_int}"
    return " ".join(label_tokens) + f" {dst_int}"


def _is_num(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _parse(cfg: CountyConfig) -> ParseResult:
    from natural_pdf import PDF
    pdf = PDF(str(cfg.resolve_source()))
    acc = Accumulator(cfg)

    for page in pdf.pages:
        lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()]
        if not lines:
            continue
        od = _office_of_title(lines[0])
        if od is None or od not in _CAND_ODS:
            continue
        office, district = od
        acc.see_od(od)
        parties = [p for p in _CANON if (office, district, p) in CAND]
        num_cand = len(parties)
        num_cols = num_cand + 3
        cur_label = None
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
                if len(vals) == num_cols and lab == "GRAND TOTAL":
                    for j, p in enumerate(parties):
                        acc.set_col_total(office, district, p, vals[1 + j])
                    acc.set_wi_total(office, district, vals[1 + num_cand])
                continue
            if len(vals) != num_cols + 1:
                continue
            dst = vals[0]
            if dst > 999:
                continue
            cand_vals = vals[2:2 + num_cand]
            wi = vals[2 + num_cand]
            if label:
                cur_label = [t.upper() for t in label]
            if cur_label is None:
                continue
            prec = acc.precinct(_precinct(cur_label, str(dst)))
            for j, p in enumerate(parties):
                acc.candidate(prec, office, district, p, cand_vals[j])
            acc.writein(prec, office, district, wi)

    return acc.result()


_CAND_ODS = {od for od in _ORDER}


CONFIG = CountyConfig(
    county="Onondaga",
    slug="onondaga",
    engine="election_book",
    source_name="Onondaga.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    parse=_parse,
)
