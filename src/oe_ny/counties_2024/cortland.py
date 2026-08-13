"""Cortland County 2024 general (rotated-SOVC PDF, positional 4-block layout).

natural_pdf extract_tables; the header cells are scrambled by rotation, so the
approach is positional: each contest is 4 side-by-side counting-group blocks and
only block 4 ('Total Votes', the last contiguous run of non-empty cells) is the
grand total.  Candidate values are read positionally, party assigned by
canonical NY ballot order filtered to the lines present.  SD-52 carries a
Cortland-only 'Local 607' line.  Output is canonically sorted.  Parse override.
"""
import re

from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_CANON = ["DEM", "REP", "CON", "WOR", "LAR", "Local 607"]

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
    ("U.S. House", "22", "DEM"): "John W. Mannion",
    ("U.S. House", "22", "WOR"): "John W. Mannion",
    ("U.S. House", "22", "REP"): "Brandon M. Williams",
    ("U.S. House", "22", "CON"): "Brandon M. Williams",
    ("State Senate", "52", "DEM"): "Lea Webb",
    ("State Senate", "52", "WOR"): "Lea Webb",
    ("State Senate", "52", "REP"): "Michael Sigler",
    ("State Senate", "52", "Local 607"): "Michael Sigler",
    ("State Assembly", "125", "DEM"): "Anna Kelles",
    ("State Assembly", "125", "WOR"): "Anna Kelles",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}
_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
          ("U.S. House", "22"), ("State Senate", "52"),
          ("State Assembly", "125"), ("State Assembly", "131")]


def _office_of_title(t):
    t = (t or "").strip()
    if "President" in t:
        return ("President", "")
    if t.startswith("United States Senator"):
        return ("U.S. Senate", "")
    for rx, office in ((r"Rep\. in Congress\s*-\s*(\d+)\w* District", "U.S. House"),
                       (r"State Senator\s*-\s*(\d+)\w* District", "State Senate"),
                       (r"Member of Assembly\s*-\s*(\d+)\w* AD", "State Assembly")):
        m = re.search(rx, t)
        if m:
            return (office, m.group(1))
    return None


def _int(v):
    s = ("" if v is None else str(v)).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _block4(row):
    cells = ["" if c is None else str(c) for c in row]
    end = len(cells)
    while end > 0 and cells[end - 1].strip() == "":
        end -= 1
    start = end
    while start > 0 and cells[start - 1].strip() != "":
        start -= 1
    return cells[start:end]


def _parse(cfg: CountyConfig) -> ParseResult:
    from natural_pdf import PDF
    pdf = PDF(str(cfg.resolve_source()))
    acc = Accumulator(cfg)

    for page in pdf.pages:
        for rows in page.extract_tables():
            if not rows:
                continue
            title = None
            for c in rows[0]:
                t = "" if c is None else str(c).strip()
                if t and t not in ("Early Voting", "Election Day",
                                   "Absentees/Affidavits", "Total Votes"):
                    if "Early Voting" in t or "Election Day" in t or t[:1].isalpha():
                        title = t
                        break
            od = _office_of_title(title)
            if od is None or od not in dict.fromkeys(_ORDER):
                continue
            office, district = od
            acc.see_od(od)
            parties = [p for p in _CANON if (office, district, p) in CAND]
            num_cand = len(parties)
            has_void = office == "President"
            block_width = num_cand + (5 if has_void else 4)

            for r in rows[2:]:
                cells = ["" if c is None else str(c) for c in r]
                if not cells:
                    continue
                label = cells[0].strip()
                prec_cell = cells[1].strip() if len(cells) > 1 else ""
                b4 = _block4(cells)
                if len(b4) != block_width:
                    continue
                vals = [_int(x) for x in b4]
                cand_vals = vals[:num_cand]
                wi = vals[num_cand]
                if prec_cell == "":
                    low = label.lower()
                    if low in ("county totals", "cd19", "cd22", "totals"):
                        for i, p in enumerate(parties):
                            acc.set_col_total(office, district, p, cand_vals[i])
                        acc.set_wi_total(office, district, wi)
                    continue
                prec = re.sub(r"\s+", " ", prec_cell).strip()
                if prec.startswith("Ward "):
                    prec = "Cortland " + prec
                prec = acc.precinct(prec)
                if has_void:
                    void, blank, _sub, tot = vals[num_cand + 1:num_cand + 5]
                else:
                    void, blank, _sub, tot = 0, vals[num_cand + 1], \
                        vals[num_cand + 2], vals[num_cand + 3]
                for i, p in enumerate(parties):
                    acc.candidate(prec, office, district, p, cand_vals[i])
                acc.writein(prec, office, district, wi)
                acc.over(prec, office, district, void)
                acc.under(prec, office, district, blank)
                acc.total(prec, office, district, tot)

    return acc.result()


CONFIG = CountyConfig(
    county="Cortland",
    slug="cortland",
    engine="sovc_table",
    source_name="Cortland.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    extra_parties=("Local 607",),
    parse=_parse,
)
