#!/usr/bin/env python3
"""Dedicated parser for Niagara County 2024 general precinct results (CSV).

The Niagara County BOE publishes a tidy long CSV (`Niagara.csv`) -- one row per
(precinct, contest, ballot-choice) with columns
  Contest | Candidate Issue | Party | District Name | Total Votes | % of Total Votes
The source file has NO county-total rows and NO per-precinct total/ballots-cast
row (the "% of Total Votes" column is computed against inconsistent bases and is
unusable), so county anchors come from the OFFICIAL NYS Election Night Reporting
countywide totals (ny.votereporting.com/NIA/184/Summary) -- see ANCHORS below.

Fusion is COMBINED at the source: a single row per candidate with a composite
Party like "DEM; WOR" or "REP; CON" and ONE combined vote total. Per the
Washington-county precedent, emit ONE row on the PRIMARY party line (DEM for
Dem candidates, REP for Rep candidates, LAR for Sare) carrying the combined
votes -- the source gives no per-line breakdown to split. Write-in rows
(aggregate "Write-in" + the President sheet's 12 named write-in candidates) all
have Party == "" and are folded into ONE "Write-in" row (party empty) per
(precinct, office) when >0. Non-President contests have no named write-ins.

Niagara is split across NY-23/24/26 (House), and at the Assembly level across
AD-140/144/145; SD-62 covers the whole county. Some precincts are SPLIT across
House districts (e.g. a precinct appears in both NY-23 and NY-24 with disjoint
vote subsets) -- the (office, district) key keeps these distinct. Canonical:
  President             (statewide)   Harris (DEM) / Trump (REP)       [combined DEM;WOR / REP;CON]
  U.S. Senate           (statewide)   Gillibrand (DEM) / Sapraicone (REP) / Sare (LAR)
  U.S. House 23                       Thomas A. Carle (DEM) / Nicholas A. Langworthy (REP)
  U.S. House 24                       David Wagenhauser (DEM) / Claudia Tenney (REP)
  U.S. House 26                       Timothy M. Kennedy (DEM) / Anthony G. Marecki (REP)
  State Senate 62                     Robert G. Ortt (REP)             (uncontested)
  State Assembly 140                  William C. Conrad III (DEM)      (uncontested)
  State Assembly 144                  Michelle M. Roman (DEM) / Paul A. Bologna (REP)
  State Assembly 145                  Jeffrey Elder (DEM) / Angelo J. Morinello (REP)
Non-canonical contests (Supreme Court, Family Court Judge, DA, Sheriff, town
offices, Proposals) are skipped.

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 NY corpus: Carle/Langworthy/Kennedy/Marecki/Roman/Bologna/
Elder/Morinello/Tenney/Wagenhauser match committed counties verbatim; source
"William C. Conrad, III" -> "William C. Conrad III" (matches committed AD-140).
SD-62 (Ortt) is Niagara-unique (no committed 2024 county yet) -- verbatim.
President "Kamala D. Harris and Tim Walz" -> VP mate dropped. Precinct names are
the source "District Name" verbatim, whitespace-stripped ("City of Lockport
001001") -- matches the committed 2022 Niagara file exactly.

Verification (all HARD):
  1. per (office, district, party): precinct-sum == OFFICIAL ANCHOR (3-way with
     the source having no totals, the official anchor is the sole cross-check);
     write-in precinct-sum == ANCHOR _WI (aggregate + named for President).
  2. candidate-name cross-check (VP mate dropped; Conrad comma fix).
  3. all 4 OE data tests.
Run with uv (stdlib csv):  uv run python niagara_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "NIAGARA_CSV",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Niagara.csv",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__niagara__precinct.csv"
)
COUNTY = "Niagara"

CONTEST_MAP = {
    "Electors for President and Vice President": ("President", ""),
    "United States Senator": ("U.S. Senate", ""),
    "Representative in Congress 23rd District": ("U.S. House", "23"),
    "Representative in Congress 24th District": ("U.S. House", "24"),
    "Representative in Congress 26th District": ("U.S. House", "26"),
    "State Senator 62nd District": ("State Senate", "62"),
    "Member of Assembly 140th District": ("State Assembly", "140"),
    "Member of Assembly 144th District": ("State Assembly", "144"),
    "Member of Assembly 145th District": ("State Assembly", "145"),
}
OFFICE_ORDER = list(CONTEST_MAP.values())
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("U.S. Senate", "", "DEM"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "REP"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "LAR"): "Diane Sare",
    ("U.S. House", "23", "DEM"): "Thomas A. Carle",
    ("U.S. House", "23", "REP"): "Nicholas A. Langworthy",
    ("U.S. House", "24", "DEM"): "David Wagenhauser",
    ("U.S. House", "24", "REP"): "Claudia Tenney",
    ("U.S. House", "26", "DEM"): "Timothy M. Kennedy",
    ("U.S. House", "26", "REP"): "Anthony G. Marecki",
    ("State Senate", "62", "REP"): "Robert G. Ortt",
    ("State Assembly", "140", "DEM"): "William C. Conrad III",
    ("State Assembly", "144", "DEM"): "Michelle M. Roman",
    ("State Assembly", "144", "REP"): "Paul A. Bologna",
    ("State Assembly", "145", "DEM"): "Jeffrey Elder",
    ("State Assembly", "145", "REP"): "Angelo J. Morinello",
}

# Official NYS Election Night Reporting countywide totals (combined fusion).
ANCHORS = {
    ("President", "", "DEM"): 43438, ("President", "", "REP"): 58678,
    ("President", "", "_WI"): 802,
    ("U.S. Senate", "", "DEM"): 44641, ("U.S. Senate", "", "REP"): 53851,
    ("U.S. Senate", "", "LAR"): 409, ("U.S. Senate", "", "_WI"): 53,
    ("U.S. House", "23", "DEM"): 3857, ("U.S. House", "23", "REP"): 7179,
    ("U.S. House", "23", "_WI"): 9,
    ("U.S. House", "24", "DEM"): 14795, ("U.S. House", "24", "REP"): 27174,
    ("U.S. House", "24", "_WI"): 15,
    ("U.S. House", "26", "DEM"): 22520, ("U.S. House", "26", "REP"): 20462,
    ("U.S. House", "26", "_WI"): 18,
    ("State Senate", "62", "REP"): 73640, ("State Senate", "62", "_WI"): 511,
    ("State Assembly", "140", "DEM"): 6403, ("State Assembly", "140", "_WI"): 28,
    ("State Assembly", "144", "DEM"): 14275, ("State Assembly", "144", "REP"): 23333,
    ("State Assembly", "144", "_WI"): 17,
    ("State Assembly", "145", "DEM"): 19087, ("State Assembly", "145", "REP"): 30110,
    ("State Assembly", "145", "_WI"): 18,
}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _clean_name(ballot, office):
    s = (ballot or "").strip()
    if office == "President" and " and " in s:
        s = s.split(" and ", 1)[0].strip()
    # committed corpus uses "William C. Conrad III" (no comma before III)
    s = s.replace("William C. Conrad, III", "William C. Conrad III")
    return s


def _primary_party(party_raw):
    """'DEM; WOR' -> 'DEM', 'REP; CON' -> 'REP', 'LAR' -> 'LAR'."""
    return party_raw.split(";")[0].strip()


def main():
    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)          # (office,district,party) -> precinct sum
    wisum = defaultdict(int)         # (office,district) -> write-in precinct sum
    name_seen = defaultdict(set)     # (office,district,party) -> source names

    with open(SRC_PATH, newline="") as f:
        for r in csv.DictReader(f):
            contest = r["Contest"].strip()
            if contest not in CONTEST_MAP:
                continue
            office, district = CONTEST_MAP[contest]
            prec = re.sub(r"\s+", " ", r["District Name"]).strip()
            if not prec:
                continue
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            ballot = r["Candidate Issue"].strip()
            party_raw = r["Party"].strip()
            votes = _int(r["Total Votes"])
            if party_raw == "":
                # write-in (aggregate "Write-in" + any named write-ins, e.g. President)
                wisum[(office, district)] += votes
                continue
            party = _primary_party(party_raw)
            nm = _clean_name(ballot, office)
            psum[(office, district, party)] += votes
            name_seen[(office, district, party)].add(nm)
            if votes > 0 and (office, district, party) in CAND:
                all_rows.append((prec, office, district, party,
                                 CAND[(office, district, party)], votes))

    # emit one aggregated Write-in row per (precinct, office, district) when >0
    # (re-scan to attribute write-ins to precincts; collect per precinct)
    wi_by_prec = defaultdict(int)
    with open(SRC_PATH, newline="") as f:
        for r in csv.DictReader(f):
            contest = r["Contest"].strip()
            if contest not in CONTEST_MAP:
                continue
            office, district = CONTEST_MAP[contest]
            if r["Party"].strip() == "":
                prec = re.sub(r"\s+", " ", r["District Name"]).strip()
                wi_by_prec[(prec, office, district)] += _int(r["Total Votes"])
    for (prec, office, district), wv in wi_by_prec.items():
        if wv > 0:
            all_rows.append((prec, office, district, "", "Write-in", wv))

    # ---- HARD verification --------------------------------------------------
    hard = []
    for od in OFFICE_ORDER:
        office, district = od
        for party in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, party) not in CAND:
                continue
            s = psum.get((office, district, party), 0)
            an = ANCHORS.get((office, district, party))
            if an is not None and s != an:
                hard.append(f"{od} {party}: precinct-sum={s} != ANCHOR={an}")
        ws_ = wisum.get(od, 0)
        aw = ANCHORS.get((office, district, "_WI"))
        if aw is not None and ws_ != aw:
            hard.append(f"{od} write-in: precinct-sum={ws_} != ANCHOR={aw}")

    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp = _norm(expected)
        for nm in names:
            if nm and _norm(nm) != exp:
                hard.append(f"{office}/{district} {party}: source {nm!r} "
                            f"!= expected {expected!r}")

    # ---- Write CSV ----------------------------------------------------------
    all_rows.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order
                                 else 999,
                                 OFFICE_RANK.get((r[1], r[2]), 99),
                                 PARTY_RANK.get(r[3], 9), r[4]))
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for prec, office, district, party, name, v in all_rows:
            w.writerow([COUNTY, prec, office, district, party, name, v])

    # ---- Report -------------------------------------------------------------
    precincts = {r[0] for r in all_rows}
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"{len(OFFICE_ORDER)} office-districts -> {OUT_PATH}")
    for od in OFFICE_ORDER:
        office, district = od
        parts = []
        for party in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, party) in CAND:
                parts.append(f"{party}={psum.get((office,district,party),0)}")
        parts.append(f"Write-in={wisum.get(od,0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())