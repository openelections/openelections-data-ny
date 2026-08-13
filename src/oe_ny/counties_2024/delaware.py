"""Delaware County 2024 general (HTML SOVC, counting-group tables).

96 stattable tables = 24 contests x 4 counting groups; only 'Counting group:
All' is the per-precinct grand total (the others double-count).  Office comes
from each table's preceding <h1>; party is the trailing token on each candidate
cell (WF->WOR, LRP->LAR); named 'X Write-in' columns plus 'Unqualified
Write-ins' fold into the aggregate write-in.  Config-level parse override.
"""
import re

from ..common import strip_vp, to_int
from ..engines.base import Accumulator
from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
          ("State Senate", "51"), ("State Assembly", "101"),
          ("State Assembly", "102"), ("State Assembly", "121")]

_PARTY = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WF": "WOR", "WOR": "WOR",
          "LRP": "LAR", "LAR": "LAR"}
_TRAIL_SKIP = {"Undervotes", "Overvotes", "Total Special Votes"}
_NON_PRECINCT = {"Delaware", "Cumulative", "TOTAL", "Sub-total", ""}

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
    ("State Assembly", "101", "REP"): "Brian M. Maher",
    ("State Assembly", "101", "CON"): "Brian M. Maher",
    ("State Assembly", "102", "DEM"): "Janet S. Tweed",
    ("State Assembly", "102", "WOR"): "Janet S. Tweed",
    ("State Assembly", "102", "REP"): "Christopher Tague",
    ("State Assembly", "102", "CON"): "Christopher Tague",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
}

ANCHORS = {
    ("President", "", "DEM"): 8536, ("President", "", "WOR"): 701,
    ("President", "", "REP"): 12785, ("President", "", "CON"): 1004,
    ("President", "", "_WI"): 234,
    ("U.S. Senate", "", "DEM"): 8769, ("U.S. Senate", "", "WOR"): 1083,
    ("U.S. Senate", "", "REP"): 11586, ("U.S. Senate", "", "CON"): 1034,
    ("U.S. Senate", "", "LAR"): 111, ("U.S. Senate", "", "_WI"): 17,
    ("U.S. House", "19", "DEM"): 8220, ("U.S. House", "19", "WOR"): 974,
    ("U.S. House", "19", "REP"): 12358, ("U.S. House", "19", "CON"): 1114,
    ("U.S. House", "19", "_WI"): 25,
    ("State Senate", "51", "DEM"): 7577, ("State Senate", "51", "WOR"): 887,
    ("State Senate", "51", "REP"): 12855, ("State Senate", "51", "CON"): 1179,
    ("State Senate", "51", "_WI"): 16,
    ("State Assembly", "101", "REP"): 3095, ("State Assembly", "101", "CON"): 365,
    ("State Assembly", "101", "_WI"): 35,
    ("State Assembly", "102", "DEM"): 4662, ("State Assembly", "102", "WOR"): 557,
    ("State Assembly", "102", "REP"): 7179, ("State Assembly", "102", "CON"): 698,
    ("State Assembly", "102", "_WI"): 8,
    ("State Assembly", "121", "DEM"): 1333, ("State Assembly", "121", "REP"): 2684,
    ("State Assembly", "121", "CON"): 235, ("State Assembly", "121", "_WI"): 7,
}


def _office_of(title):
    if not title:
        return None
    t = title.strip()
    if "Presidential Electors" in t:
        return ("President", "")
    if "US Senator" in t:
        return ("U.S. Senate", "")
    for rx, office in ((r"Congress (\d+)\w* District", "U.S. House"),
                       (r"State Senator (\d+)\w* District", "State Senate"),
                       (r"Assembly (\d+)\w* District", "State Assembly")):
        m = re.search(rx, t)
        if m:
            return (office, m.group(1))
    return None


def _counting_group(table):
    node = table.previous
    for _ in range(80):
        if node is None:
            break
        s = node.get_text(" ", strip=True) if hasattr(node, "get_text") else (
            str(node).strip() if getattr(node, "name", None) is None else "")
        if s.startswith("Counting group:"):
            return s.split(":", 1)[1].strip()
        node = node.previous
    return "?"


def _office_title(table):
    h = table.find_previous("h1")
    return " ".join(h.get_text(" ", strip=True).split()) if h else None


def _src_name(cell, office):
    s = re.sub(r"\s+(DEM|REP|CON|WF|WOR|LRP|LAR)$", "", str(cell).strip())
    return strip_vp(s) if office == "President" else s


def _parse(cfg: CountyConfig) -> ParseResult:
    from bs4 import BeautifulSoup
    html = open(cfg.resolve_source(), encoding="utf-8", errors="replace").read()
    soup = BeautifulSoup(html, "html.parser")
    acc = Accumulator(cfg)

    for t in soup.find_all("table", class_="stattable"):
        if _counting_group(t) != "All":
            continue
        od = _office_of(_office_title(t))
        if od is None:
            continue
        office, district = od
        trs = t.find_all("tr")
        if not trs:
            continue
        hdr = [" ".join(c.get_text(" ", strip=True).split())
               for c in trs[0].find_all(["td", "th"])]
        cand_cols, wi_cols, tv_idx = [], [], None
        names = {}
        for j, h in enumerate(hdr):
            if j == 0 or h in _TRAIL_SKIP or h == "ED":
                continue
            if h == "Total Votes":
                tv_idx = j
                continue
            if h in ("Unqualified Write-ins", "Write-ins", "Write-in") \
                    or h.endswith("Write-in") or h.endswith("Write-ins"):
                wi_cols.append(j)
                continue
            toks = h.split()
            code = _PARTY.get(toks[-1]) if toks else None
            if code:
                cand_cols.append((j, code))
                names[j] = _src_name(h, office)
        if not cand_cols:
            continue
        acc.see_od(od)
        total_row = None
        for r in trs[1:]:
            cells = [cc.get_text(" ", strip=True) for cc in r.find_all(["td", "th"])]
            if not cells or not cells[0]:
                continue
            label = cells[0].strip()
            if label == "TOTAL":
                total_row = cells
                continue
            if label in _NON_PRECINCT:
                continue
            prec = acc.precinct(label)
            for j, party in cand_cols:
                if (office, district, party) not in cfg.cand:
                    continue
                v = to_int(cells[j] if j < len(cells) else None)
                acc.candidate(prec, office, district, party, v, src_name=names[j])
            acc.writein(prec, office, district,
                        sum(to_int(cells[j] if j < len(cells) else None)
                            for j in wi_cols))
            if tv_idx is not None:
                acc.total(prec, office, district,
                          to_int(cells[tv_idx] if tv_idx < len(cells) else None))
        if total_row is not None:
            for j, party in cand_cols:
                if (office, district, party) in cfg.cand:
                    acc.set_col_total(office, district, party,
                                      to_int(total_row[j] if j < len(total_row) else None))
            acc.set_wi_total(office, district,
                             sum(to_int(total_row[j] if j < len(total_row) else None)
                                 for j in wi_cols))

    return acc.result()


CONFIG = CountyConfig(
    county="Delaware",
    slug="delaware",
    engine="tabular",
    source_name="Delaware.html",
    office_order=_ORDER,
    cand=CAND,
    anchors=ANCHORS,
    parse=_parse,
)
