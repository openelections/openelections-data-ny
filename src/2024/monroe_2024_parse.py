#!/usr/bin/env python3
"""Dedicated parser for Monroe County 2024 general precinct results (XLSX).

The Monroe County BOE publishes a single-sheet "Election Book DETAIL" XLSX
(`Monroe.xlsx`). NOTE: this particular source file contains ONLY the
PRESIDENT contest (one office block, ~370 election districts). The sheet is a
merged-cell layout:

  row 0 : office title "PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES / DETAIL"
  row 4 : candidate names (multi-line cells, cols 5/7/9/11)
  row 9 : "LEGISLATIVE DISTRICT OR TOWN" precinct-label column header
  row 10: "TOTAL VOTES" (col 3) header
  row 11: party-code header -> col5 DEM, col7 REP, col9 CON, col11 WOR,
          col13 SCATTER (write-in/scattering)
  rows 12+: the data

The data is grouped by election district. The City of Rochester is divided
into numbered "Leg. Dist. NN" groups (04..29); each town is one named group
(Brighton, Chili, ..., Wheatland). Each group is:
  "<group>" header row (col3 blank) -> sets the current precinct prefix
  ED rows: col0 = ED number, col3 = Total Votes, col5/7/9/11 = DEM/REP/CON/WOR,
           col13 = SCATTER
  "<group>" subtotal row (col3 numeric) -> per-group total (skip, verify)
A group may span several header sections (a town split into wards). Citywide
subtotals "CITY" (Rochester), "TOWNS", and "GRAND TOTAL:" appear at the end.

Precinct names follow the committed 2022 Monroe convention EXACTLY:
  Rochester -> "Leg. Dist. NN E"   (e.g. "Leg. Dist. 21 1")
  towns     -> "Town E"            (e.g. "Brighton 1", "Webster 1")
i.e. precinct = "<group label> <ED>". (2022 was a midterm with no President,
so President precinct names cannot be cross-checked against 2022, but the
group-label+ED scheme matches the 2022 town/Leg.Dist names verbatim.)

Fusion is split at the source (separate DEM/WOR and REP/CON columns) -- exactly
the #148-branch convention; emit one row per party-line column. SCATTER
(unqualified write-ins) is emitted as ONE "Write-in" row (party empty) per
precinct when >0. "TOTAL VOTES" (col3) includes overvotes/undervotes/voids and
is NOT emitted. 0-vote rows omitted (an all-zero ED, e.g. Leg. Dist. 04 ED 1,
simply produces no rows). Party: WOR = Working Families (#148 convention).

Candidate names: President DEM/WOR = "Kamala D. Harris", REP/CON =
"Donald J. Trump" (source multi-line cells "KAMALA D. HARRIS AND TIM WALZ" /
"DONALD J. TRUMP AND JD VANCE" -> VP mate dropped), matching the committed 2024
NY corpus.

Verification (all HARD):
  1. per group (where a subtotal row is present): sum of ED rows per party col
     == subtotal row per party col (no double-count: subtotals skipped).
  2. county: sum of all ED rows per party col == "GRAND TOTAL:" row == ANCHOR
     (3-way); SCATTER sum == GRAND TOTAL SCATTER == ANCHOR _WI.
  3. candidate-name cross-check against the source name row (VP mate dropped).
Run with uv (openpyxl):  uv run python monroe_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "MONROE_XLSX",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Monroe.xlsx",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__monroe__precinct.csv"
)
COUNTY = "Monroe"
OFFICE = "President"
DISTRICT = ""
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}

CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "WOR"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("President", "", "CON"): "Donald J. Trump",
}

# county grand-total anchors (from the "GRAND TOTAL:" row)
ANCHORS = {
    ("President", "", "DEM"): 201677, ("President", "", "WOR"): 13080,
    ("President", "", "REP"): 126558, ("President", "", "CON"): 19382,
    ("President", "", "_WI"): 4084,
}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _is_ed(c0):
    if isinstance(c0, bool):
        return False
    if isinstance(c0, (int, float)):
        return True
    if isinstance(c0, str) and c0.strip().isdigit():
        return True
    return False


def main():
    wb = openpyxl.load_workbook(SRC_PATH, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # locate the party-code header row (col5 == 'DEM')
    party_row_idx = None
    for i, r in enumerate(rows):
        if r and len(r) > 5 and str(r[5]).strip().upper() == "DEM":
            party_row_idx = i
            break
    if party_row_idx is None:
        print("No party-code header row found", file=sys.stderr)
        return 1
    party_row = rows[party_row_idx]
    col_party = {}        # col_idx -> party code (DEM/REP/CON/WOR)
    writein_col = None
    for j in range(5, len(party_row)):
        v = str(party_row[j]).strip().upper()
        if v in ("DEM", "REP", "CON", "WOR", "LAR"):
            col_party[j] = v
        elif v == "SCATTER":
            writein_col = j
    # candidate-name row: the nearest non-empty row above the party row with
    # multi-line candidate cells in the candidate columns
    name_row = None
    for k in range(party_row_idx - 1, -1, -1):
        rk = rows[k]
        if rk and any(rk[j] is not None and "\n" in str(rk[j]) for j in col_party):
            name_row = rk
            break

    all_rows = []
    prec_order = []
    seen_prec = set()
    ed_sum = defaultdict(int)          # (col_idx) -> sum of ED votes (county)
    group_sub = {}                     # group_label -> {col_idx: subtotal}
    group_edsum = defaultdict(lambda: defaultdict(int))  # group -> col -> sum
    cur_group = None
    grand = {}                         # col_idx -> GRAND TOTAL value

    CITY_WIDE = {"CITY", "TOWNS", "GRAND TOTAL:", "GRAND TOTAL"}

    for r in rows[party_row_idx + 1:]:
        c0 = r[0] if r else None
        if c0 is None:
            continue
        s0 = str(c0).strip()
        if not s0:
            continue
        if _is_ed(c0):
            if cur_group is None:
                continue
            ed = int(float(c0)) if isinstance(c0, (int, float)) else int(s0)
            prec = f"{cur_group} {ed}"
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            for j, party in col_party.items():
                v = _int(r[j] if j < len(r) else None)
                ed_sum[j] += v
                group_edsum[cur_group][j] += v
                if v > 0 and (OFFICE, DISTRICT, party) in CAND:
                    all_rows.append((prec, OFFICE, DISTRICT, party,
                                     CAND[(OFFICE, DISTRICT, party)], v))
            if writein_col is not None:
                wv = _int(r[writein_col] if writein_col < len(r) else None)
                ed_sum[writein_col] += wv
                group_edsum[cur_group][writein_col] += wv
                if wv > 0:
                    all_rows.append((prec, OFFICE, DISTRICT, "", "Write-in", wv))
            continue
        # label row
        if s0.upper() in CITY_WIDE:
            if s0.upper().startswith("GRAND TOTAL"):
                for j in list(col_party.keys()) + ([writein_col] if writein_col is not None else []):
                    grand[j] = _int(r[j] if j < len(r) else None)
            continue
        c3 = r[3] if len(r) > 3 else None
        c3_blank = c3 is None or (isinstance(c3, str) and not c3.strip())
        if c3_blank:
            cur_group = s0  # header row -> set precinct prefix
        else:
            # per-group subtotal row -> record for verification, skip emission
            sub = {}
            for j in list(col_party.keys()) + ([writein_col] if writein_col is not None else []):
                sub[j] = _int(r[j] if j < len(r) else None)
            group_sub[s0] = sub

    # ---- HARD verification --------------------------------------------------
    hard = []
    # 1. per-group ED-sum == subtotal (where subtotal present)
    for grp, sub in group_sub.items():
        for j, val in sub.items():
            s = group_edsum.get(grp, {}).get(j, 0)
            if s != val:
                hard.append(f"group {grp} col{j}: ED-sum={s} != subtotal={val}")
    # 2. county: ED-sum == GRAND TOTAL == ANCHOR
    for j, party in col_party.items():
        s = ed_sum.get(j, 0)
        g = grand.get(j)
        an = ANCHORS.get((OFFICE, DISTRICT, party))
        if g is None:
            hard.append(f"{party}: no GRAND TOTAL")
        elif s != g:
            hard.append(f"{party}: county ED-sum={s} != GRAND TOTAL={g}")
        if an is not None and g is not None and g != an:
            hard.append(f"{party}: GRAND TOTAL={g} != ANCHOR={an}")
        if an is not None and s != an:
            hard.append(f"{party}: county ED-sum={s} != ANCHOR={an}")
    if writein_col is not None:
        s = ed_sum.get(writein_col, 0)
        g = grand.get(writein_col)
        an = ANCHORS.get((OFFICE, DISTRICT, "_WI"))
        if g is None:
            hard.append("write-in: no GRAND TOTAL")
        elif s != g:
            hard.append(f"write-in: county ED-sum={s} != GRAND TOTAL={g}")
        if an is not None and g is not None and g != an:
            hard.append(f"write-in: GRAND TOTAL={g} != ANCHOR={an}")
        if an is not None and s != an:
            hard.append(f"write-in: county ED-sum={s} != ANCHOR={an}")

    # 3. candidate-name cross-check (source name row, VP mate dropped)
    if name_row is not None:
        for j, party in col_party.items():
            expected = CAND.get((OFFICE, DISTRICT, party))
            if expected is None or name_row[j] is None:
                continue
            nm = str(name_row[j]).replace("\n", " ").strip()
            nm = re.sub(r"\s+", " ", nm)
            # drop VP running-mate (case-insensitive " AND ")
            m = re.search(r"\s+AND\s", nm, re.IGNORECASE)
            if m:
                nm = nm[:m.start()].strip()
            if _norm(nm) != _norm(expected):
                hard.append(f"{party}: source name {nm!r} != expected {expected!r}")

    # ---- Write CSV ----------------------------------------------------------
    all_rows.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order
                                 else 999,
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
          f"1 office (President only) -> {OUT_PATH}")
    parts = []
    for party in ("DEM", "REP", "CON", "WOR"):
        j = next((jj for jj, p in col_party.items() if p == party), None)
        if j is not None:
            parts.append(f"{party}={ed_sum.get(j,0)}")
    parts.append(f"Write-in={ed_sum.get(writein_col,0)}")
    print(f"  President: {', '.join(parts)}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())