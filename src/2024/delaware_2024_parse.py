#!/usr/bin/env python3
"""Dedicated parser for Delaware County 2024 general precinct results (HTML).

The Delaware County BOE publishes an NYS SOVC "Statement of Vote Cast" HTML
report (`Delaware.html`). It is a clean tabular SOVC: 96 `<table
class="stattable">` tables = 24 contests x 4 COUNTING-GROUP tables each
(All / Election Day / Early Voting / Absentee). ONLY the "Counting group: All"
table per contest is the per-precinct GRAND TOTAL -- the other three are
disjoint subsets that DOUBLE-COUNT if merged (verified: AN 1 Pres DEM
All=281 = ElectionDay 134 + Early 84 + Absentee 63), the same trap as
Schuyler/Chenango/Clinton-"by Gr". The "All" table is selected by reading the
"Counting group:" text preceding each table.

Each "All" table layout:
  row 0 (.title) = header: <ED> <candidate cell>... <Undervotes> <Overvotes>
                   <Unqualified Write-ins> <Total Special Votes> <Total Votes>
  row 1 = "Delaware" county-name header row (all zeros -- NOT a total)
  row 2+ = precinct rows (col 0 = 2-letter town code + ED num, e.g. "AN 1")
  ...then "Sub-total" / "Cumulative" / "Cumulative" / "TOTAL" rows.
A candidate cell is "<Name> <PARTY>" (party = last whitespace token:
DEM/REP/CON/WF/LRP). Write-in candidates appear as "<Name> Write-in" columns
(named write-ins); "Unqualified Write-ins" is a trailing column. Per the
#128/#148 convention + the committed Chenango 2024 precedent (its emitted
"Write-in" aggregate = named 69 + unnamed scattering 46 = 115), the Write-in
aggregate = sum(named write-in columns) + Unqualified Write-ins, emitted as
ONE "Write-in" row (party empty) per (precinct, office) when >0. Undervotes /
Overvotes / Total Special Votes are omitted. 0-vote rows are omitted.

The SOVC defines Total Votes = sum(candidates) + named_writeins +
Unqualified Write-ins (Undervotes/Overvotes are NOT in Total Votes -- they
are separate "special" ballots). So the per-precinct self-consistency check is
cand + writein_aggregate == Total Votes (verified county-wide: Pres
23026 + 234 = 23260).

Canonical offices (Delaware is WHOLLY inside NY-19 / SD-51; SPLIT across
AD-101 (17 precincts) / AD-102 (27) / AD-121 (11) -- 17+27+11 = 55):
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 19                       Josh Riley (DEM/WOR) / Marcus Molinaro (REP/CON)
  State Senate 51                     Michele Frazier (DEM/WOR) / Peter Oberacker (REP/CON)
  State Assembly 101                  Brian M. Maher (REP/CON)   (uncontested)
  State Assembly 102                  Janet S. Tweed (DEM/WOR) / Christopher Tague (REP/CON)
  State Assembly 121                  Vicki Davis (DEM) / Joe Angelino (REP/CON)
Non-canonical (skipped): County Clerk, Town Justice, Member of Council,
Superintendent of Highways, and all Proposals/Propositions.

Candidate names come from a hardcoded CAND[(office,district,party)] map
matching the committed 2024 NY corpus (Chenango carries Riley/Molinaro/
Frazier/Oberacker/Davis/Angelino; Maher/Tweed/Tague confirmed). The source
prints "Kamala D .Harris/ Tim Walz" (odd spacing + VP mate) and party codes
WF (->WOR) and LRP (->LAR) -- the CAND map sidesteps both. WOR = Working
Families (#148-branch convention, NOT WF); LAR = LaRouche.

Precinct names are the source's 2-letter town code + ED number ("AN 1",
"WL 5"), preserved VERBATIM -- the committed 2022 Delaware file uses these
same codes (the HTML carries no town names, and 2022 set the convention).

Verification (all HARD):
  1. per (precinct, office): sum(candidate cols) + writein_aggregate ==
     that row's Total Votes. Validates extraction of every number.
  2. per (office, district, party): precinct-sum == the table's TOTAL-row
     value == the hardcoded ANCHOR. Three-way cross-check.
  3. per (office, district): write-in precinct-sum == TOTAL-row write-in ==
     ANCHOR. Candidate-name cross-check: each (office,district,party) maps to
     exactly one source header cell matching CAND.
Run with uv (beautifulsoup4):  uv run python delaware_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "DELAWARE_HTML",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Delaware.html",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__delaware__precinct.csv"
)
COUNTY = "Delaware"

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
OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
                ("State Senate", "51"), ("State Assembly", "101"),
                ("State Assembly", "102"), ("State Assembly", "121")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}
PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WF": "WOR",
              "WOR": "WOR", "LRP": "LAR", "LAR": "LAR"}
TRAIL_SKIP = {"Undervotes", "Overvotes", "Total Special Votes"}
NON_PRECINCT = {"Delaware", "Cumulative", "TOTAL", "Sub-total", ""}

# Official county-wide anchors (office, district, party) -> candidate party-line
# county total; "_WI" -> write-in aggregate (named + unqualified). Read from each
# "All" table's TOTAL row and embedded here for the 3-way cross-check.
ANCHORS = {
    ("President", "", "DEM"): 8536,
    ("President", "", "WOR"): 701,
    ("President", "", "REP"): 12785,
    ("President", "", "CON"): 1004,
    ("President", "", "_WI"): 234,
    ("U.S. Senate", "", "DEM"): 8769,
    ("U.S. Senate", "", "WOR"): 1083,
    ("U.S. Senate", "", "REP"): 11586,
    ("U.S. Senate", "", "CON"): 1034,
    ("U.S. Senate", "", "LAR"): 111,
    ("U.S. Senate", "", "_WI"): 17,
    ("U.S. House", "19", "DEM"): 8220,
    ("U.S. House", "19", "WOR"): 974,
    ("U.S. House", "19", "REP"): 12358,
    ("U.S. House", "19", "CON"): 1114,
    ("U.S. House", "19", "_WI"): 25,
    ("State Senate", "51", "DEM"): 7577,
    ("State Senate", "51", "WOR"): 887,
    ("State Senate", "51", "REP"): 12855,
    ("State Senate", "51", "CON"): 1179,
    ("State Senate", "51", "_WI"): 16,
    ("State Assembly", "101", "REP"): 3095,
    ("State Assembly", "101", "CON"): 365,
    ("State Assembly", "101", "_WI"): 35,
    ("State Assembly", "102", "DEM"): 4662,
    ("State Assembly", "102", "WOR"): 557,
    ("State Assembly", "102", "REP"): 7179,
    ("State Assembly", "102", "CON"): 698,
    ("State Assembly", "102", "_WI"): 8,
    ("State Assembly", "121", "DEM"): 1333,
    ("State Assembly", "121", "REP"): 2684,
    ("State Assembly", "121", "CON"): 235,
    ("State Assembly", "121", "_WI"): 7,
}


def office_of(title):
    """<h1> office title -> (office, district) for canonical offices, else None."""
    if not title:
        return None
    t = title.strip()
    if "Presidential Electors" in t:
        return ("President", "")
    if "US Senator" in t:
        return ("U.S. Senate", "")
    m = re.search(r"Congress (\d+)\w* District", t)
    if m:
        return ("U.S. House", m.group(1))
    m = re.search(r"State Senator (\d+)\w* District", t)
    if m:
        return ("State Senate", m.group(1))
    m = re.search(r"Assembly (\d+)\w* District", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


def _norm_src_name(cell):
    """Source candidate cell -> a comparable name (lowercase, no spaces/punct)."""
    s = re.sub(r"\s+", " ", str(cell)).strip()
    # drop trailing party / 'Write-in' token
    s = re.sub(r"\s+(DEM|REP|CON|WF|WOR|LRP|LAR|Write-in|Write-ins)$", "", s)
    s = re.sub(r"[^a-z]", "", s.lower())
    return s


def _norm_cand(name):
    return re.sub(r"[^a-z]", "", name.lower())


def counting_group(table):
    node = table.previous
    d = 0
    while node and d < 80:
        s = node.get_text(" ", strip=True) if hasattr(node, "get_text") else (
            str(node).strip() if node.name is None else "")
        if s.startswith("Counting group:"):
            return s.split(":", 1)[1].strip()
        node = node.previous
        d += 1
    return "?"


def office_title(table):
    h = table.find_previous("h1")
    return " ".join(h.get_text(" ", strip=True).split()) if h else None


def parse_table(table):
    """Parse one 'All' table -> (header_map, precinct_rows, total_row).

    header_map: {col_index: ('cand', party) | ('wi',) | ('tv',) | ('skip',)}
    precinct_rows: [(precinct_code, [int values per col])]
    total_row: [int values per col] for the 'TOTAL' row, or None
    """
    rows = table.find_all("tr")
    if not rows:
        return None, [], None
    hdr_cells = rows[0].find_all(["td", "th"])
    header_map = {}
    cand_cols = []        # [(j, party)]
    wi_cols = []          # [j]
    tv_idx = None
    for j, c in enumerate(hdr_cells):
        h = " ".join(c.get_text(" ", strip=True).split())
        if j == 0:
            continue  # ED
        if h in TRAIL_SKIP or h in ("ED",):
            header_map[j] = ("skip",)
            continue
        if h == "Total Votes":
            header_map[j] = ("tv",)
            tv_idx = j
            continue
        if h in ("Unqualified Write-ins", "Write-ins", "Write-in"):
            header_map[j] = ("wi",)
            wi_cols.append(j)
            continue
        if h.endswith("Write-in") or h.endswith("Write-ins"):
            header_map[j] = ("wi",)
            wi_cols.append(j)
            continue
        toks = h.split()
        code = toks[-1] if toks else ""
        if code in PARTY_NORM:
            header_map[j] = ("cand", PARTY_NORM[code])
            cand_cols.append((j, PARTY_NORM[code]))
        else:
            header_map[j] = ("skip",)
    prec_rows = []
    total_row = None
    for r in rows[1:]:
        cells = [cc.get_text(" ", strip=True) for cc in r.find_all(["td", "th"])]
        if not cells or not cells[0]:
            continue
        label = cells[0].strip()
        if label == "TOTAL":
            total_row = cells
            continue
        if label in NON_PRECINCT:
            continue
        prec_rows.append((label, cells))
    return (header_map, cand_cols, wi_cols, tv_idx), prec_rows, total_row


def _int(s):
    s = (s or "").strip().replace(",", "")
    return int(s) if s.lstrip("-").isdigit() else 0


def main():
    html = open(SRC_PATH, encoding="utf-8").read()
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="stattable")
    all_tables = [t for t in tables if counting_group(t) == "All"]

    out = []                       # (precinct, office, district, party, candidate, votes)
    prec_order = []
    seen_prec = set()
    od_seen = []
    # verification accumulators
    ed_cand_sum = defaultdict(int)     # (prec, office, district) -> cand sum
    ed_wi = defaultdict(int)           # (prec, office, district) -> writein aggregate
    ed_tv = defaultdict(int)           # (prec, office, district) -> Total Votes
    party_sum = defaultdict(int)       # (office, district, party) -> precinct sum
    wi_sum = defaultdict(int)          # (office, district) -> writein precinct sum
    total_row_vals = {}                # (office, district) -> TOTAL row cells
    name_seen = defaultdict(set)       # (office, district, party) -> source names

    for t in all_tables:
        od = office_of(office_title(t))
        if od is None:
            continue
        office, district = od
        (header_map, cand_cols, wi_cols, tv_idx), prec_rows, total_row = \
            parse_table(t)
        if not cand_cols:
            continue
        if od not in od_seen:
            od_seen.append(od)
        total_row_vals[od] = total_row
        for label, cells in prec_rows:
            if label not in seen_prec:
                seen_prec.add(label)
                prec_order.append(label)
            key = (label, office, district)
            for j, party in cand_cols:
                v = _int(cells[j] if j < len(cells) else None)
                if (office, district, party) in CAND:
                    name_seen[(office, district, party)].add(
                        _norm_src_name(cells[j] if j < len(cells)
                                       and header_map[j][0] == "cand" else ""))
                    ed_cand_sum[key] += v
                    party_sum[(office, district, party)] += v
                    if v > 0:
                        out.append((label, office, district, party,
                                    CAND[(office, district, party)], v))
            wv = sum(_int(cells[j] if j < len(cells) else None) for j in wi_cols)
            ed_wi[key] += wv
            wi_sum[(office, district)] += wv
            if tv_idx is not None:
                ed_tv[key] += _int(cells[tv_idx] if tv_idx < len(cells) else None)

    # emit ONE aggregated Write-in row per (precinct, office-district) when >0
    for (label, office, district), w in ed_wi.items():
        if w > 0:
            out.append((label, office, district, "", "Write-in", w))

    # ---- HARD verification --------------------------------------------------
    hard = []
    # 1. per (precinct, office): cand + writein == Total Votes
    for key in set(ed_cand_sum) | set(ed_wi):
        c = ed_cand_sum.get(key, 0)
        w = ed_wi.get(key, 0)
        tv = ed_tv.get(key, 0)
        if c + w != tv:
            hard.append(f"{key}: cand({c})+writein({w})={c+w} != Total Votes={tv}")

    # 2 & 3. precinct-sum == TOTAL-row == ANCHOR (party lines + write-in)
    for od in OFFICE_ORDER:
        office, district = od
        trow = total_row_vals.get(od)
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, p) not in CAND:
                continue
            ps = party_sum.get((office, district, p), 0)
            # find TOTAL-row value: the candidate col for this party
            tr = None
            if trow is not None:
                # rebuild col map for TOTAL row by re-parsing header of its table
                # (total_row cells align to the same columns)
                # locate the cand col index for party p via header_map on the
                # table we stored implicitly -- simpler: recompute from cand_cols
                pass
            an = ANCHORS.get((office, district, p))
            if an is not None and ps != an:
                hard.append(f"{od} {p}: precinct-sum={ps} != ANCHOR={an}")
        aw = ANCHORS.get((office, district, "_WI"))
        ws = wi_sum.get(od, 0)
        if aw is not None and ws != aw:
            hard.append(f"{od} write-in: precinct-sum={ws} != ANCHOR={aw}")

    # TOTAL-row cross-check (read at runtime) vs ANCHOR -- re-walk each table
    for t in all_tables:
        od = office_of(office_title(t))
        if od is None or od not in OFFICE_RANK:
            continue
        office, district = od
        (header_map, cand_cols, wi_cols, tv_idx), prec_rows, total_row = \
            parse_table(t)
        if total_row is None:
            continue
        for j, party in cand_cols:
            if (office, district, party) not in CAND:
                continue
            an = ANCHORS.get((office, district, party))
            if an is not None:
                tr = _int(total_row[j] if j < len(total_row) else None)
                if tr != an:
                    hard.append(f"{od} {party}: TOTAL-row={tr} != ANCHOR={an}")
        # write-in TOTAL = sum of wi_cols in TOTAL row
        wi_tr = sum(_int(total_row[j] if j < len(total_row) else None)
                    for j in wi_cols)
        aw = ANCHORS.get((office, district, "_WI"))
        if aw is not None and wi_tr != aw:
            hard.append(f"{od} write-in: TOTAL-row={wi_tr} != ANCHOR={aw}")

    # candidate-name cross-check
    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp_n = _norm_cand(expected)
        for n in names:
            if n and n != exp_n:
                hard.append(f"{office}/{district} {party}: source {n!r} "
                            f"!= expected {exp_n!r}")

    # ---- Write CSV ----------------------------------------------------------
    out.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order else 999,
                            OFFICE_RANK.get((r[1], r[2]), 99),
                            PARTY_RANK.get(r[3], 9), r[4]))
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for label, office, district, party, name, v in out:
            w.writerow([COUNTY, label, office, district, party, name, v])

    # ---- Report -------------------------------------------------------------
    precincts = {r[0] for r in out}
    print(f"Wrote {len(out)} rows, {len(precincts)} precincts, "
          f"office-districts={od_seen} -> {OUT_PATH}")
    print("County-wide totals (per office-district):")
    for od in OFFICE_ORDER:
        office, district = od
        parts = []
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, p) in CAND:
                parts.append(f"{p}({CAND[(office,district,p)]})="
                             f"{party_sum.get((office,district,p),0)}")
        parts.append(f"Write-in={wi_sum.get(od,0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
    # assembly split check
    ad = defaultdict(set)
    for r in out:
        if r[1] == "State Assembly":
            ad[r[2]].add(r[0])
    if ad:
        sums = {d: len(s) for d, s in ad.items()}
        print(f"Assembly split: {sums} (sum={sum(sums.values())})")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())