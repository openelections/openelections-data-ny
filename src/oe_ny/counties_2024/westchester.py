"""Westchester County 2024 general (PDF 'Election Book', 688 pp).

pdfplumber extract_text.  Candidate names are printed rotated (garbled) and
ignored; the UPRIGHT party-code row 'DEM REP CON WOR [LAR] W/I ...' gives the
columns in canonical order (party read positionally).  Data row:
  <Town/City of ...> <EDCODE(>=4 digits)> <v1..vN> <CANVASS> <VOID> <BALLOT>.
County anchor = the 'TOTAL OF COUNTY WIDE' rollup (fallback: last TOTAL row).
Config-level parse override.
"""
import re

from ..common import to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""),
          ("U.S. House", "16"), ("U.S. House", "17"),
          ("State Senate", "34"), ("State Senate", "35"),
          ("State Senate", "36"), ("State Senate", "37"), ("State Senate", "40"),
          ("State Assembly", "88"), ("State Assembly", "89"),
          ("State Assembly", "90"), ("State Assembly", "91"),
          ("State Assembly", "92"), ("State Assembly", "93"),
          ("State Assembly", "94"), ("State Assembly", "95")]

_PARTY_TOKENS = {"DEM", "REP", "CON", "WOR", "LAR", "W/I"}

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
    ("U.S. House", "16", "DEM"): "George S. Latimer",
    ("U.S. House", "16", "REP"): "Miriam Levitt Flisser",
    ("U.S. House", "17", "DEM"): "Mondaire L. Jones",
    ("U.S. House", "17", "WOR"): "Anthony Frascone",
    ("U.S. House", "17", "REP"): "Mike Lawler",
    ("U.S. House", "17", "CON"): "Mike Lawler",
    ("State Senate", "34", "DEM"): "Nathalia Fernandez",
    ("State Senate", "34", "REP"): "Edwinna Herrera",
    ("State Senate", "34", "CON"): "Edwinna Herrera",
    ("State Senate", "35", "DEM"): "Andrea Stewart-Cousins",
    ("State Senate", "35", "WOR"): "Andrea Stewart-Cousins",
    ("State Senate", "35", "REP"): "Khristen M. Kerr",
    ("State Senate", "36", "DEM"): "Jamaal T. Bailey",
    ("State Senate", "36", "CON"): "Irene Estrada",
    ("State Senate", "37", "DEM"): "Shelley B. Mayer",
    ("State Senate", "37", "WOR"): "Shelley B. Mayer",
    ("State Senate", "37", "REP"): "Tricia S. Lindsay",
    ("State Senate", "37", "CON"): "Tricia S. Lindsay",
    ("State Senate", "40", "DEM"): "Peter B. Harckham",
    ("State Senate", "40", "WOR"): "Peter B. Harckham",
    ("State Senate", "40", "REP"): "Gina M. Arena",
    ("State Senate", "40", "CON"): "Gina M. Arena",
    ("State Assembly", "88", "DEM"): "Amy Paulin",
    ("State Assembly", "88", "WOR"): "Amy Paulin",
    ("State Assembly", "88", "REP"): "Thomas H. Fix Jr.",
    ("State Assembly", "88", "CON"): "Thomas H. Fix Jr.",
    ("State Assembly", "89", "DEM"): "Gary J. Pretlow",
    ("State Assembly", "90", "DEM"): "Nader J. Sayegh",
    ("State Assembly", "90", "REP"): "John Isaac",
    ("State Assembly", "90", "CON"): "John Isaac",
    ("State Assembly", "91", "DEM"): "Steven Otis",
    ("State Assembly", "91", "WOR"): "Steven Otis",
    ("State Assembly", "91", "REP"): "Katie Manger",
    ("State Assembly", "92", "DEM"): "MaryJane C. Shimsky",
    ("State Assembly", "92", "WOR"): "MaryJane C. Shimsky",
    ("State Assembly", "92", "REP"): "Alessandro Crocco",
    ("State Assembly", "92", "CON"): "Alessandro Crocco",
    ("State Assembly", "93", "DEM"): "Chris Burdick",
    ("State Assembly", "93", "WOR"): "Chris Burdick",
    ("State Assembly", "94", "DEM"): "Zachary C. Couzens",
    ("State Assembly", "94", "REP"): "Matthew J. Slater",
    ("State Assembly", "94", "CON"): "Matthew J. Slater",
    ("State Assembly", "95", "DEM"): "Dana Levenberg",
    ("State Assembly", "95", "WOR"): "Dana Levenberg",
    ("State Assembly", "95", "REP"): "Michael L. Capalbo",
    ("State Assembly", "95", "CON"): "Michael L. Capalbo",
}


def _office_of_title(t):
    t = (t or "").strip()
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    for rx, office in ((r"CONGRESSIONAL DISTRICT - (\d+)(?:ST|ND|RD|TH)", "U.S. House"),
                       (r"SENATORIAL DISTRICT - (\d+)(?:ST|ND|RD|TH)", "State Senate"),
                       (r"ASSEMBLY DISTRICT - (\d+)(?:ST|ND|RD|TH)", "State Assembly")):
        m = re.search(rx, t)
        if m:
            return (office, m.group(1))
    return None


def _precinct_name(label):
    m = re.match(r"^(.+?) -(\d+)$", label)
    return f"{m.group(1)} - {m.group(2)}" if m else label


def _party_row(toks):
    if 2 <= len(toks) <= 20 and all(t in _PARTY_TOKENS for t in toks):
        return toks
    return None


def _is_num(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _parse(cfg: CountyConfig) -> ParseResult:
    import pdfplumber
    acc = Accumulator(cfg)
    anchor = {}      # (office,district,party) -> total
    wi_anchor = {}   # (office,district) -> total

    with pdfplumber.open(cfg.resolve_source()) as pdf:
        for page in pdf.pages:
            raw = page.extract_text()
            if not raw:
                continue
            lines = [l for l in raw.split("\n") if l.strip()]
            od = None
            for l in lines:
                m = re.search(r"2024 GENERAL (.+?) \d+ OF 688", l)
                if m:
                    od = _office_of_title(m.group(1))
                    break
            if od is None or od not in dict.fromkeys(_ORDER):
                continue
            office, district = od
            parties = None
            for l in lines:
                pr = _party_row(l.split())
                if pr:
                    parties = pr
                    break
            if parties is None:
                continue
            acc.see_od(od)
            n_vote = len(parties)

            # county anchor (COUNTY WIDE rollup, else last TOTAL row)
            expect_county = False
            last_total = None
            for l in lines:
                s = l.strip()
                if "COUNTY WIDE" in s:
                    expect_county = True
                    continue
                if s.startswith("TOTALS:") or s.startswith("TOTAL:"):
                    vals = [to_int(t) for t in re.findall(r"[\d,]+", s)]
                    if len(vals) == n_vote + 3:
                        if expect_county:
                            for j, p in enumerate(parties):
                                if p != "W/I":
                                    anchor[(office, district, p)] = vals[j]
                            wi_anchor[od] = sum(vals[j] for j, p in enumerate(parties)
                                                if p == "W/I")
                        last_total = vals
                    expect_county = False
            if last_total is not None:
                for j, p in enumerate(parties):
                    if p != "W/I" and (office, district, p) not in anchor:
                        anchor[(office, district, p)] = last_total[j]
                if od not in wi_anchor:
                    wi_anchor[od] = sum(last_total[j] for j, p in enumerate(parties)
                                        if p == "W/I")

            # data rows
            for l in lines:
                s = l.strip()
                if not (s.startswith("Town of ") or s.startswith("City of ")
                        or s.startswith("Village of ")):
                    continue
                toks = s.split()
                k = next((j for j, t in enumerate(toks)
                          if re.match(r"^\d{4,}$", t)), None)
                if not k:
                    continue
                nums = toks[k:]
                if not all(_is_num(t) for t in nums):
                    continue
                vals = [to_int(t) for t in nums]
                if len(vals) != n_vote + 4:
                    continue
                prec = acc.precinct(_precinct_name(" ".join(toks[:k])))
                vote = vals[1:1 + n_vote]
                wi = 0
                for j, p in enumerate(parties):
                    if p == "W/I":
                        wi += vote[j]
                    else:
                        acc.candidate(prec, office, district, p, vote[j])
                acc.writein(prec, office, district, wi)

    for (office, district, p), v in anchor.items():
        acc.set_col_total(office, district, p, v)
    for (office, district), v in wi_anchor.items():
        acc.set_wi_total(office, district, v)
    return acc.result()


CONFIG = CountyConfig(
    county="Westchester",
    slug="westchester",
    engine="election_book",
    source_name="Westchester.pdf",
    office_order=_ORDER,
    cand=CAND,
    anchors={},
    parse=_parse,
)
