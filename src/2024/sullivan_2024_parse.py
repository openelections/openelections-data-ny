#!/usr/bin/env python3
"""Dedicated parser for Sullivan County 2024 general precinct results (XLSX).

The Sullivan County BOE publishes a tidy "long" XLSX (`Sullivan.xlsx`, sheet
"Results") -- one row per (precinct, contest, ballot-choice) with columns
  Contest | Votes Allowed | Precinct | Candidate | Party | Votes Cast | ...
Fusion is already split into SEPARATE per-party rows (Harris Democratic + Harris
Working Families, etc.) -- exactly the #148-branch convention; emit one row per
(precinct, office, party). Party codes: Democratic->DEM, Republican->REP,
Conservative->CON, Working Families->WOR, LaRouche->LAR, People Over Politics
->POP (an independent fusion line for the AD-100 Democrat, new in 2024).

Sullivan is WHOLLY inside NY-19 / SD-51 but SPLIT across TWO Assembly districts
(AD-100 / AD-101). Canonical offices:
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 19                       Josh Riley (DEM/WOR) / Marcus Molinaro (REP/CON)
  State Senate 51                     Michele Frazier (DEM/WOR) / Peter Oberacker (REP/CON)
  State Assembly 100                  Paula Elaine Kay (DEM/POP) / Louis J. Ingrassia, Jr. (REP/CON)
  State Assembly 101                  Brian M. Maher (REP/CON)         (uncontested)
Non-canonical contests (County Coroner, town/village offices, Proposals) skipped.

WRITE-IN semantics: the source has an aggregate "Write-in" row, a "Scattering"
row, AND named-write-in candidate rows (Chase Oliver, Claudia De la Cruz, Cornel
West, Jill Stein, Peter Sonski), all with Party == "". These do NOT overlap
(verified: Write-in + Scattering + named == TVC - candidates), so true write-in
= Write-in + Scattering + named, emitted as ONE "Write-in" row (party empty) per
(precinct, office) when >0. The control rows "Under Votes"/"Over Votes"/"Total
Registered Voters"/"Total Votes Cast" (also Party == "") are NOT write-ins.
NOTE: Sullivan's "Total Votes Cast" = candidates + write-ins ONLY (Under/Over
votes are reported separately, NOT inside TVC) -- verified per precinct, so the
HARD self-consistency check is cand + writein == TVC (NOT +over+under).

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 NY corpus: Riley/Molinaro/Frazier/Oberacker match Delaware/Otsego;
Maher (AD-101) matches Delaware; Paula Elaine Kay / Louis J. Ingrassia, Jr.
(AD-100) are new to the corpus here -- taken verbatim from the source. President
"Kamala D. Harris and Tim Walz" -> VP mate dropped -> "Kamala D. Harris". Precinct
names are the source "Precinct" column verbatim, whitespace-stripped ("Town of
Bethel 1") -- matches the committed 2022 Sullivan file.

Verification (all HARD):
  1. per (precinct, office): cand + writein == Total Votes Cast.
  2. candidate-name cross-check (President VP-mate drop).
  3. AD-100/101 split disjoint + complete == President precinct set.
Run with uv (openpyxl):  uv run python sullivan_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "SULLIVAN_XLSX",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Sullivan.xlsx",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__sullivan__precinct.csv"
)
COUNTY = "Sullivan"

CONTEST_MAP = {
    "Electors for President and Vice President": ("President", ""),
    "United States Senator": ("U.S. Senate", ""),
    "Representative in Congress 19th District": ("U.S. House", "19"),
    "State Senator 51st District": ("State Senate", "51"),
    "Member of Assembly 100th District": ("State Assembly", "100"),
    "Member of Assembly 101st District": ("State Assembly", "101"),
}
OFFICE_ORDER = list(CONTEST_MAP.values())
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "POP": 5, "IND": 6}
PARTY_NORM = {"Democratic": "DEM", "Republican": "REP", "Conservative": "CON",
              "Working Families": "WOR", "LaRouche": "LAR",
              "People Over Politics": "POP"}

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
    ("State Assembly", "100", "DEM"): "Paula Elaine Kay",
    ("State Assembly", "100", "POP"): "Paula Elaine Kay",
    ("State Assembly", "100", "REP"): "Louis J. Ingrassia, Jr.",
    ("State Assembly", "100", "CON"): "Louis J. Ingrassia, Jr.",
    ("State Assembly", "101", "REP"): "Brian M. Maher",
    ("State Assembly", "101", "CON"): "Brian M. Maher",
}

# rows with Party == "" that are NOT write-ins (control / summary rows)
CONTROL = {"Under Votes", "Over Votes", "Total Registered Voters", "Total Votes Cast",
           "Total Ballots Cast"}


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
    return s


def main():
    wb = openpyxl.load_workbook(SRC_PATH, data_only=True, read_only=True)
    ws = wb["Results"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)          # (office,district,party) -> precinct sum
    name_seen = defaultdict(set)     # (office,district,party) -> source names
    ed_cand = defaultdict(int)       # (prec,office,district) -> candidate votes
    ed_wi = defaultdict(int)         # (prec,office,district) -> write-in votes
    ed_tvc = defaultdict(int)        # (prec,office,district) -> Total Votes Cast
    ad_precincts = defaultdict(set)  # AD district -> set of precincts

    for r in rows[1:]:
        contest = (r[0] or "").strip()
        if contest not in CONTEST_MAP:
            continue
        office, district = CONTEST_MAP[contest]
        prec = re.sub(r"\s+", " ", str(r[2] or "")).strip()
        if not prec:
            continue
        cand = (r[3] or "").strip()
        party_raw = (r[4] or "").strip()
        votes = _int(r[5])
        if prec not in seen_prec:
            seen_prec.add(prec)
            prec_order.append(prec)
        key = (prec, office, district)
        if cand == "Total Votes Cast":
            ed_tvc[key] = votes
            continue
        if cand in CONTROL:
            continue  # Under/Over/Registered -- not emitted, not write-in
        if party_raw == "":
            # write-in aggregate ("Write-in"), "Scattering", or named write-in
            ed_wi[key] += votes
            continue
        party = PARTY_NORM.get(party_raw)
        if party is None:
            continue
        nm = _clean_name(cand, office)
        psum[(office, district, party)] += votes
        ed_cand[key] += votes
        name_seen[(office, district, party)].add(nm)
        if office == "State Assembly":
            ad_precincts[district].add(prec)
        if votes > 0 and (office, district, party) in CAND:
            all_rows.append((prec, office, district, party,
                             CAND[(office, district, party)], votes))

    # emit one aggregated Write-in row per (precinct, office) when >0
    for (prec, office, district), wv in ed_wi.items():
        if wv > 0:
            all_rows.append((prec, office, district, "", "Write-in", wv))

    # ---- HARD verification --------------------------------------------------
    hard = []
    # 1. per-precinct cand + writein == Total Votes Cast
    for key in set(ed_cand) | set(ed_wi):
        c = ed_cand.get(key, 0)
        w = ed_wi.get(key, 0)
        tvc = ed_tvc.get(key, 0)
        if tvc and tvc != c + w:
            hard.append(f"{key}: TVC={tvc} != cand+writein({c + w})")

    # 2. candidate-name cross-check
    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp = _norm(expected)
        for nm in names:
            if nm and _norm(nm) != exp:
                hard.append(f"{office}/{district} {party}: source {nm!r} "
                            f"!= expected {expected!r}")

    # 3. AD-100/101 split disjoint + complete == President precincts
    pres_precs = {p for (p, o, d) in ed_tvc if o == "President"}
    ad_union = set()
    for d, ps in ad_precincts.items():
        ad_union |= ps
    if ad_union != pres_precs:
        hard.append(f"AD split not complete: union={len(ad_union)} "
                    f"president={len(pres_precs)}")
    overlap = set()
    ds = list(ad_precincts)
    for a in range(len(ds)):
        for b in range(a + 1, len(ds)):
            overlap |= ad_precincts[ds[a]] & ad_precincts[ds[b]]
    if overlap:
        hard.append(f"AD split overlap: {sorted(overlap)[:5]}")

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
        for party in ("DEM", "REP", "CON", "WOR", "LAR", "POP"):
            if (office, district, party) in CAND:
                parts.append(f"{party}={psum.get((office,district,party),0)}")
        wi = sum(v for (p, o, d), v in ed_wi.items() if (o, d) == od)
        parts.append(f"Write-in={wi}")
        print(f"  {office} {district}: {', '.join(parts)}")
    print(f"  AD split: {dict((d, len(ps)) for d, ps in ad_precincts.items())}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())