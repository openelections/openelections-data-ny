#!/usr/bin/env python3
"""Dedicated parser for Franklin County 2024 general precinct results (XLSX).

The Franklin County BOE publishes a multi-sheet XLSX (`Franklin.xlsx`) -- one
sheet per office. Each sheet is a clean SOVC: title rows, an "ED" header row
whose col1+ cells are "<Candidate> \\n<PARTY>" (DEM/REP/CON/WOR/LAR) plus
trailing "Write-ins" / "Voids" / "Blanks" / "Total Votes" columns, one row per
precinct, and a final "TOTAL" county-grand-total row.

Franklin is WHOLLY inside NY-21 / SD-45 / AD-115 -- same districts as Clinton,
no split. Canonical offices:
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 21                       Paula Collins (DEM/WOR) / Elise M. Stefanik (REP/CON)
  State Senate 45                     Daniel G. Stec (REP/CON)          (uncontested)
  State Assembly 115                  Billy Jones (DEM)                 (uncontested)
Non-canonical sheets (Family Court Judge, town Council Member, Town Justice,
Superintendent of Highways, Village Trustee, Proposals) are skipped.

Fusion is split at the source (separate DEM/WOR, REP/CON columns) -- exactly
the #148-branch convention; emit one row per party-line column. The "Write-ins"
column is emitted as ONE "Write-in" row (party empty) per (precinct, office)
when >0; "Voids" (overvotes) and "Blanks" (undervotes) are omitted. 0-vote rows
omitted. Total Votes = cand + writeins + voids + blanks (self-consistency).

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 NY corpus: Gillibrand/Sapraicone/Sare/Collins/Stefanik/Stec
match Clinton/Essex; source "D. Billy Jones" -> "Billy Jones" (matches Essex/
Clinton AD-115, cross-county consistency in the same race). The President
source cell is "Electors for Kamala D. Harris for President Tim Walz for Vice
President" -- the name is extracted from between "Electors for " and
" for President". WOR = Working Families (#148 convention); LAR = LaRouche.

Precinct names are preserved verbatim ("Bangor 1", "Bellmont 2") -- the
committed 2022 Franklin file uses these same names (29 precincts, exact match).

Verification (all HARD):
  1. per (precinct, office): cand + writeins + Voids + Blanks == Total Votes.
  2. per (office, district, party): precinct-sum == "TOTAL" row == ANCHOR
     (3-way); write-in precinct-sum == TOTAL-row write-in == ANCHOR _WI.
  3. candidate-name cross-check (with known source->canonical normalizations).
Run with uv (openpyxl):  uv run python franklin_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "FRANKLIN_XLSX",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Franklin.xlsx",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__franklin__precinct.csv"
)
COUNTY = "Franklin"

SHEETS = [
    ("Electors for President and Vice", "President", ""),
    ("US Senator ", "U.S. Senate", ""),
    ("Rep to Congress (21st)", "U.S. House", "21"),
    ("State Senator (45th)", "State Senate", "45"),
    ("Member of Assembly (115th)", "State Assembly", "115"),
]
OFFICE_RANK = {(o, d): i for i, (_, o, d) in enumerate(SHEETS)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}
PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
              "WFP": "WOR", "LAR": "LAR"}

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
    ("State Assembly", "115", "DEM"): "Billy Jones",
}

ANCHORS = {
    ("President", "", "DEM"): 8358, ("President", "", "WOR"): 463,
    ("President", "", "REP"): 9775, ("President", "", "CON"): 794,
    ("President", "", "_WI"): 68,
    ("U.S. Senate", "", "DEM"): 8519, ("U.S. Senate", "", "WOR"): 838,
    ("U.S. Senate", "", "REP"): 8713, ("U.S. Senate", "", "CON"): 768,
    ("U.S. Senate", "", "LAR"): 64, ("U.S. Senate", "", "_WI"): 6,
    ("U.S. House", "21", "DEM"): 7869, ("U.S. House", "21", "WOR"): 655,
    ("U.S. House", "21", "REP"): 9812, ("U.S. House", "21", "CON"): 868,
    ("U.S. House", "21", "_WI"): 10,
    ("State Senate", "45", "REP"): 12027, ("State Senate", "45", "CON"): 2140,
    ("State Senate", "45", "_WI"): 102,
    ("State Assembly", "115", "DEM"): 13278, ("State Assembly", "115", "_WI"): 85,
}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _src_name(cell, office):
    """Header candidate cell 'Name\\nPARTY' -> comparable name."""
    s = str(cell or "").split("\n", 1)[0].strip()
    if office == "President":
        m = re.search(r"Electors for (.*?) for President", s)
        if m:
            return m.group(1).strip()
        if " and " in s:
            return s.split(" and ", 1)[0].strip()
    return s


def classify_header(cell):
    if cell is None:
        return ("skip", None)
    s = str(cell)
    low = s.strip().lower()
    if low == "ed":
        return ("ed", None)
    if low == "total votes":
        return ("tv", None)
    if low.startswith("write-ins") or low.startswith("write-ins") or low == "write-in":
        return ("writein", None)
    if low == "voids" or low == "void":
        return ("over", None)
    if low == "blanks" or low == "blank":
        return ("under", None)
    if "\n" in s:
        code = s.split("\n")[-1].strip()
        if code in PARTY_NORM:
            return ("cand", PARTY_NORM[code])
    return ("skip", None)


def main():
    wb = openpyxl.load_workbook(SRC_PATH, data_only=True)
    all_rows = []
    prec_order = []
    seen_prec = set()
    od_seen = []
    psum = defaultdict(int)
    wisum = defaultdict(int)
    col_total = {}
    wi_total = {}
    layout_by_od = {}
    name_seen = defaultdict(set)
    ed_cand = defaultdict(int)
    ed_wi = defaultdict(int)
    ed_under = defaultdict(int)
    ed_over = defaultdict(int)
    ed_tv = defaultdict(int)

    for sheet_name, office, district in SHEETS:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        hdr_idx = None
        for i, r in enumerate(rows):
            if r and r[0] and str(r[0]).strip() == "ED":
                hdr_idx = i
                break
        if hdr_idx is None:
            continue
        hdr = rows[hdr_idx]
        layout = {"cand_cols": [], "writein_cols": [], "under_idx": None,
                  "over_idx": None, "tv_idx": None}
        for j, cell in enumerate(hdr):
            kind, party = classify_header(cell)
            if kind == "cand":
                layout["cand_cols"].append((j, party))
            elif kind == "writein":
                layout["writein_cols"].append(j)
            elif kind == "under":
                layout["under_idx"] = j
            elif kind == "over":
                layout["over_idx"] = j
            elif kind == "tv":
                layout["tv_idx"] = j
        layout_by_od[(office, district)] = layout
        if (office, district) not in od_seen:
            od_seen.append((office, district))

        for r in rows[hdr_idx + 1:]:
            c0 = r[0] if r else None
            if c0 is None:
                continue
            label = re.sub(r"\s+", " ", str(c0)).strip()
            if not label:
                continue
            if label.lower() == "total":
                for j, party in layout["cand_cols"]:
                    col_total[(office, district, j)] = _int(r[j])
                wi_total[(office, district)] = sum(
                    _int(r[j]) for j in layout["writein_cols"])
                break
            # precinct row (must have numeric data)
            if not any(isinstance(r[j], (int, float)) for j in range(1, len(r))
                       if j < len(r)):
                continue
            prec = label
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            key = (prec, office, district)
            for j, party in layout["cand_cols"]:
                v = _int(r[j] if j < len(r) else None)
                psum[(office, district, party)] += v
                name_seen[(office, district, party)].add(_src_name(hdr[j], office))
                ed_cand[key] += v
                if v > 0 and (office, district, party) in CAND:
                    all_rows.append((prec, office, district, party,
                                     CAND[(office, district, party)], v))
            wv = sum(_int(r[j] if j < len(r) else None)
                     for j in layout["writein_cols"])
            wisum[(office, district)] += wv
            ed_wi[key] += wv
            if wv > 0:
                all_rows.append((prec, office, district, "", "Write-in", wv))
            if layout["under_idx"] is not None:
                ed_under[key] += _int(r[layout["under_idx"]]
                                      if layout["under_idx"] < len(r) else None)
            if layout["over_idx"] is not None:
                ed_over[key] += _int(r[layout["over_idx"]]
                                     if layout["over_idx"] < len(r) else None)
            if layout["tv_idx"] is not None:
                ed_tv[key] += _int(r[layout["tv_idx"]]
                                   if layout["tv_idx"] < len(r) else None)

    # ---- HARD verification --------------------------------------------------
    hard = []
    for key in set(ed_cand) | set(ed_wi):
        c = ed_cand.get(key, 0)
        w = ed_wi.get(key, 0)
        u = ed_under.get(key, 0)
        o = ed_over.get(key, 0)
        tv = ed_tv.get(key, 0)
        if tv and tv != c + w + u + o:
            hard.append(f"{key}: TV={tv} != cand+wi+blanks+voids({c + w + u + o})")

    for sheet_name, office, district in SHEETS:
        layout = layout_by_od[(office, district)]
        for j, party in layout["cand_cols"]:
            s = psum.get((office, district, party), 0)
            tr = col_total.get((office, district, j))
            an = ANCHORS.get((office, district, party))
            if tr is None:
                hard.append(f"{office}/{district} {party}: no TOTAL row")
            elif s != tr:
                hard.append(f"{office}/{district} {party}: precinct-sum={s} "
                            f"!= TOTAL={tr}")
            if an is not None and tr is not None and tr != an:
                hard.append(f"{office}/{district} {party}: TOTAL={tr} "
                            f"!= ANCHOR={an}")
            if an is not None and s != an:
                hard.append(f"{office}/{district} {party}: precinct-sum={s} "
                            f"!= ANCHOR={an}")
        ws_ = wisum.get((office, district), 0)
        wt = wi_total.get((office, district))
        aw = ANCHORS.get((office, district, "_WI"))
        if wt is None:
            hard.append(f"{office}/{district} write-in: no TOTAL row")
        elif ws_ != wt:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws_} "
                        f"!= TOTAL={wt}")
        if aw is not None and wt is not None and wt != aw:
            hard.append(f"{office}/{district} write-in: TOTAL={wt} != ANCHOR={aw}")
        if aw is not None and ws_ != aw:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws_} "
                        f"!= ANCHOR={aw}")

    # candidate-name cross-check (with known normalizations)
    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp = _norm(expected)
        for nm in names:
            clean = nm.replace("D. Billy Jones", "Billy Jones")
            if clean and _norm(clean) != exp:
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
          f"{len(od_seen)} office-districts -> {OUT_PATH}")
    for sheet_name, office, district in SHEETS:
        parts = []
        for party in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, party) in CAND:
                parts.append(f"{party}={psum.get((office,district,party),0)}")
        parts.append(f"Write-in={wisum.get((office,district),0)}")
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