"""Broome County 2024 general (PDF, upright 'Statement of Votes Cast').

pdfplumber extract_text lines.  Each canonical contest has an upright party-code
row (ballot order, hardcoded per office below) and per-ED data rows:
  <section> <ED> <cand_0..n-1> <write-ins> <void> <blank> <ballots> <voters> <turnout%>
Town subtotals / county totals have no ED (one fewer field) and are skipped or
captured (the COUNTY TOTALS row is the anchor).  Config-level parse override.
"""
import re

from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
          ("State Senate", "51"), ("State Senate", "52"),
          ("State Assembly", "121"), ("State Assembly", "123"),
          ("State Assembly", "124"), ("State Assembly", "131")]

_PARTIES = {
    ("President", ""): ["DEM", "REP", "CON", "WOR"],
    ("U.S. Senate", ""): ["DEM", "REP", "CON", "WOR", "LAR"],
    ("U.S. House", "19"): ["DEM", "REP", "CON", "WOR"],
    ("State Senate", "51"): ["DEM", "REP", "CON", "WOR"],
    ("State Senate", "52"): ["DEM", "REP", "WOR", "Local 607"],
    ("State Assembly", "121"): ["DEM", "REP", "CON"],
    ("State Assembly", "123"): ["DEM", "REP", "CON", "WOR", "ECO"],
    ("State Assembly", "124"): ["REP", "CON"],
    ("State Assembly", "131"): ["REP", "CON"],
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
    ("U.S. House", "19", "DEM"): "Josh Riley",
    ("U.S. House", "19", "WOR"): "Josh Riley",
    ("U.S. House", "19", "REP"): "Marcus Molinaro",
    ("U.S. House", "19", "CON"): "Marcus Molinaro",
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Senate", "52", "DEM"): "Lea Webb",
    ("State Senate", "52", "WOR"): "Lea Webb",
    ("State Senate", "52", "REP"): "Michael Sigler",
    ("State Senate", "52", "Local 607"): "Michael Sigler",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
    ("State Assembly", "123", "DEM"): "Donna Lupardo",
    ("State Assembly", "123", "WOR"): "Donna Lupardo",
    ("State Assembly", "123", "REP"): "Lisa M. OKeefe",
    ("State Assembly", "123", "CON"): "Lisa M. OKeefe",
    ("State Assembly", "123", "ECO"): "Lisa M. OKeefe",
    ("State Assembly", "124", "REP"): "Christopher S. Friend",
    ("State Assembly", "124", "CON"): "Christopher S. Friend",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}


def _office_of_title(t):
    t = (t or "").strip()
    if "Vote for" not in t:
        return None
    if "PRESIDENTIAL ELECTORS" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    for rx, office in (
            (r"REPRESENTATIVE IN CONGRESS,\s*(\d+)[A-Za-z]*\s+CONGRESSIONAL", "U.S. House"),
            (r"STATE SENATOR,\s*(\d+)[A-Za-z]*\s+SENATE", "State Senate"),
            (r"MEMBER OF ASSEMBLY,\s*(\d+)[A-Za-z]*\s+ASSEMBLY", "State Assembly")):
        m = re.search(rx, t)
        if m:
            return (office, m.group(1))
    return None


def _is_int(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _is_turnout(tok):
    return bool(re.match(r"^\d+\.\d+%$", tok))


def _parse(cfg: CountyConfig) -> ParseResult:
    import pdfplumber
    acc = Accumulator(cfg)
    cur_od = None
    cur_section = None
    expect_county = False

    with pdfplumber.open(cfg.resolve_source()) as pdf:
        for page in pdf.pages:
            lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()]
            for raw in lines:
                s = raw.strip()
                if "Vote for" in s:
                    od = _office_of_title(s)
                    cur_od = od if od in _PARTIES else None
                    if cur_od:
                        acc.see_od(cur_od)
                    expect_county = False
                    continue
                if re.match(r"^(City|Town|Village) of [A-Za-z.'\- ]+$", s) \
                        and not any(c.isdigit() for c in s):
                    cur_section = s
                    continue
                if cur_od is None:
                    continue
                office, district = cur_od
                parties = _PARTIES[cur_od]
                n_cand = len(parties)
                n_data = n_cand + 7
                n_total = n_cand + 6

                if s == "COUNTY":
                    expect_county = True
                    continue
                if expect_county and s.startswith("TOTALS"):
                    s2 = re.sub(r"\d+\.\d+%?\s*$", "", s)
                    vals = [to_int(t) for t in re.findall(r"[\d,]+", s2)]
                    if len(vals) == n_total - 1:
                        for j, p in enumerate(parties):
                            acc.set_col_total(office, district, p, vals[j])
                        acc.set_wi_total(office, district, vals[n_cand])
                    expect_county = False
                    continue

                toks = s.split()
                i = 0
                while i < len(toks) and not _is_int(toks[i]):
                    i += 1
                if i == 0 or i == len(toks):
                    continue
                nums = toks[i:]
                if not all(_is_int(t) or _is_turnout(t) for t in nums):
                    continue
                if not _is_turnout(nums[-1]):
                    continue
                vals = [to_int(t) for t in nums]
                if len(vals) != n_data:
                    continue  # subtotal (n_total) or noise
                ed = vals[0]
                if ed > 999 or ed < 1 or cur_section is None:
                    continue
                cand_vals = vals[1:1 + n_cand]
                wi = vals[1 + n_cand]
                void = vals[2 + n_cand]
                blank = vals[3 + n_cand]
                ballots = vals[4 + n_cand]
                prec = acc.precinct(f"{cur_section} {ed}")
                for j, p in enumerate(parties):
                    acc.candidate(prec, office, district, p, cand_vals[j])
                acc.writein(prec, office, district, wi)
                acc.over(prec, office, district, void)
                acc.under(prec, office, district, blank)
                acc.total(prec, office, district, ballots)
    return acc.result()


CONFIG = CountyConfig(
    county="Broome",
    slug="broome",
    engine="election_book",
    source_name="Broome.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    extra_parties=("ECO", "Local 607"),
    parse=_parse,
)
