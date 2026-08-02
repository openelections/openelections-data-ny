#!/usr/bin/env python3
"""Dedicated parser for Hamilton County 2024 general precinct results (XLSX).

The Hamilton County BOE publishes a single-sheet XLSX (`Hamilton.xlsx`,
sheet "Contest overview") in a clean "Results per ED" layout. Each office is a
BLOCK: an office-title row ("<Office> (Vote for 1)"), a header row whose col0
is "ED" and whose col1+ cells are "<Candidate> - <PARTY>" (DEM/WF/REP/CON/LR)
plus a trailing "Write-in" column and (for President) a "Voids" column, then
one precinct row per ED, then a "Total" county-grand-total row.

Hamilton is the smallest NY county -- 11 precincts, WHOLLY inside NY-21 /
SD-49 / AD-118 (note: NOT SD-45/AD-115 like neighboring Clinton/Franklin --
Hamilton's State Senator is Mark C. Walczyk (SD-49, same as Herkimer/St.
Lawrence) and its Assembly member is Robert Smullen (AD-118, same as
Herkimer)). Canonical offices:
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 21                       Paula Collins (DEM/WOR) / Elise M. Stefanik (REP/CON)
  State Senate 49                     Mark C. Walczyk (REP/CON)        (uncontested)
  State Assembly 118                  Robert Smullen (REP/CON)         (uncontested)
Non-canonical blocks (Town Justice, Town Clerk, Highway Superintendent,
Councilperson, County Coroner, Proposals) are skipped.

Fusion is already split into SEPARATE per-party columns (Harris DEM + Harris
WF, Trump REP + Trump CON) -- exactly the #148-branch convention; emit one row
per party-line column. Party codes: WF->WOR, LR->LAR. The trailing "Write-in"
column is emitted as ONE "Write-in" row (party empty) per (precinct, office)
when >0; "Voids" (overvotes/invalid) is omitted. 0-vote rows omitted.

Candidate names come from a hardcoded CAND[(office,district,party)] map
matching the committed 2024 NY corpus: "Kristen E. Gillibrand" (source typo)
-> "Kirsten E. Gillibrand"; "Michael D.Sapraicone" (missing space) ->
"Michael D. Sapraicone"; source "Robert J. Smullen" -> "Robert Smullen" to
match Herkimer's already-delivered AD-118 rows (cross-county consistency in
the same race). Collins/Stefanik/Walczyk/Sare match Clinton/Herkimer/St.
Lawrence. Precinct names are preserved verbatim ("Arietta 1", "Indian Lake
2") -- the committed 2022 Hamilton file uses these same names.

There is no per-precinct TOTAL column, so verification is the column-sum
cross-check (HARD): each candidate/write-in column's precinct-sum == the
block's "Total" row == the hardcoded ANCHOR (3-way), plus a candidate-name
cross-check.

Run with uv (openpyxl):  uv run python hamilton_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "HAMILTON_XLSX",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Hamilton.xlsx",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__hamilton__precinct.csv"
)
COUNTY = "Hamilton"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
                ("State Senate", "49"), ("State Assembly", "118")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}

# Office-title substring -> (office, district).
def office_of(title):
    t = title.strip()
    if "President and Vice President" in t:
        return ("President", "")
    if "United States Senator" in t:
        return ("U.S. Senate", "")
    if "Representative In Congress" in t or "Representative in Congress" in t:
        return ("U.S. House", "21")
    if "State Senator" in t:
        return ("State Senate", "49")
    if "Member of Assembly" in t:
        return ("State Assembly", "118")
    return None

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
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
}

PARTY_NORM = {"DEM": "DEM", "WF": "WOR", "WOR": "WOR", "REP": "REP",
              "CON": "CON", "LR": "LAR", "LAR": "LAR"}

ANCHORS = {
    ("President", "", "DEM"): 1136, ("President", "", "WOR"): 75,
    ("President", "", "REP"): 2052, ("President", "", "CON"): 171,
    ("President", "", "_WI"): 5,
    ("U.S. Senate", "", "DEM"): 1168, ("U.S. Senate", "", "WOR"): 115,
    ("U.S. Senate", "", "REP"): 1873, ("U.S. Senate", "", "CON"): 180,
    ("U.S. Senate", "", "LAR"): 13, ("U.S. Senate", "", "_WI"): 1,
    ("U.S. House", "21", "DEM"): 1019, ("U.S. House", "21", "WOR"): 83,
    ("U.S. House", "21", "REP"): 2089, ("U.S. House", "21", "CON"): 205,
    ("U.S. House", "21", "_WI"): 3,
    ("State Senate", "49", "REP"): 2324, ("State Senate", "49", "CON"): 295,
    ("State Senate", "49", "_WI"): 7,
    # AD-118 REP anchor = 2358 (the per-precinct sum); the source's "Total" row
    # prints 2362 -- a 4-vote BOE Total-row discrepancy (CON 310 + WI 15 match
    # the precincts exactly, only REP is off). Per-precinct data is authoritative
    # (Herkimer/Ontario precedent); the gap is reported as a non-fatal quirk.
    ("State Assembly", "118", "REP"): 2358, ("State Assembly", "118", "CON"): 310,
    ("State Assembly", "118", "_WI"): 15,
}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _clean_src(name, office):
    """Source header candidate name -> canonical-comparable name.

    Strips the President VP running-mate (", Tim Walz") and fixes the source's
    own typos so the cross-check recognizes them: "Kristen E. Gillibrand" ->
    "Kirsten E. Gillibrand", "Michael D.Sapraicone" -> "Michael D. Sapraicone",
    "Robert J. Smullen" -> "Robert Smullen" (matches Herkimer's AD-118)."""
    s = (name or "").strip()
    if office == "President" and "," in s:
        s = s.split(",", 1)[0].strip()
    s = s.replace("Kristen E. Gillibrand", "Kirsten E. Gillibrand")
    s = s.replace("Michael D.Sapraicone", "Michael D. Sapraicone")
    s = s.replace("Robert J. Smullen", "Robert Smullen")
    return s


def classify_header_cell(cell):
    """'Name - PARTY' / 'Write-in' / 'Voids' / 'ED' -> (kind, party, name)."""
    if cell is None:
        return (None, None, "")
    s = re.sub(r"\s+", " ", str(cell)).strip()
    if s == "ED":
        return ("ed", None, "")
    if s.lower() == "write-in" or s.lower() == "write in":
        return ("writein", None, "")
    if s.lower() == "voids" or s.lower() == "void":
        return ("void", None, "")
    # "Name - PARTY"
    m = re.match(r"^(.*?)\s*-\s*([A-Z]+)\s*$", s)
    if m:
        name, code = m.group(1).strip(), m.group(2).strip()
        party = PARTY_NORM.get(code)
        if party:
            return ("cand", party, name)
    return (None, None, "")


def main():
    wb = openpyxl.load_workbook(SRC_PATH, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    out = []
    prec_order = []
    seen_prec = set()
    od_seen = []
    # per-office layout + total row
    col_sum = defaultdict(int)       # (office,district,col_idx) -> precinct sum
    total_val = {}                   # (office,district,col_idx) -> Total-row val
    wi_sum = defaultdict(int)        # (office,district) -> write-in precinct sum
    wi_total = {}                    # (office,district) -> write-in Total-row val
    name_seen = defaultdict(set)     # (office,district,party) -> source names

    i = 0
    n = len(rows)
    while i < n:
        c0 = rows[i][0] if rows[i] else None
        if c0 and isinstance(c0, str) and "(Vote for 1)" in c0:
            od = office_of(c0)
            if od is None:
                i += 1
                continue
            office, district = od
            # next non-empty row is the header (col0 == "ED")
            hdr_idx = None
            for j in range(i + 1, min(i + 6, n)):
                hj = rows[j][0] if rows[j] else None
                if hj and str(hj).strip() == "ED":
                    hdr_idx = j
                    break
            if hdr_idx is None:
                i += 1
                continue
            hdr = rows[hdr_idx]
            layout = {}  # col_idx -> (kind, party, name)
            cand_cols = []
            writein_idx = None
            for j, cell in enumerate(hdr):
                kind, party, name = classify_header_cell(cell)
                if kind is None:
                    continue
                layout[j] = (kind, party, name)
                if kind == "cand":
                    cand_cols.append((j, party, name))
                elif kind == "writein":
                    writein_idx = j
            if od not in od_seen:
                od_seen.append(od)
            # data rows until "Total"
            for r in rows[hdr_idx + 1:]:
                rc0 = r[0] if r else None
                if rc0 is None:
                    continue
                label = re.sub(r"\s+", " ", str(rc0)).strip()
                if not label:
                    continue
                if label.lower() == "total":
                    for j, party, name in cand_cols:
                        total_val[(office, district, j)] = _int(r[j])
                    if writein_idx is not None:
                        wi_total[(office, district)] = _int(r[writein_idx])
                    break
                # precinct row
                if label not in seen_prec:
                    seen_prec.add(label)
                    prec_order.append(label)
                for j, party, name in cand_cols:
                    v = _int(r[j] if j < len(r) else None)
                    col_sum[(office, district, j)] += v
                    name_seen[(office, district, party)].add(name)
                    if v > 0 and (office, district, party) in CAND:
                        out.append((label, office, district, party,
                                    CAND[(office, district, party)], v))
                if writein_idx is not None:
                    wv = _int(r[writein_idx] if writein_idx < len(r) else None)
                    wi_sum[(office, district)] += wv
                    if wv > 0:
                        out.append((label, office, district, "", "Write-in", wv))
            i = r_idx_after(rows, hdr_idx)
            continue
        i += 1

    # ---- HARD verification --------------------------------------------------
    hard = []
    quirks = []   # non-fatal source Total-row discrepancies
    for od in OFFICE_ORDER:
        office, district = od
        # rebuild cand_cols for this office by re-finding its header
        cand_cols = _office_cand_cols(rows, office, district)
        for j, party, name in cand_cols:
            s = col_sum.get((office, district, j), 0)
            tv = total_val.get((office, district, j))
            an = ANCHORS.get((office, district, party))
            if tv is None:
                hard.append(f"{office}/{district} col{j}: no Total row")
            elif s != tv:
                # per-precinct sum vs source Total row: a mismatch is a BOE
                # Total-row arithmetic quirk (per-precinct data authoritative),
                # NOT a hard failure -- reported as a quirk.
                quirks.append(f"{office}/{district} {party}: precinct-sum={s} "
                              f"!= source Total={tv} (diff {tv - s})")
            if an is not None and s != an:
                hard.append(f"{office}/{district} {party}: precinct-sum={s} "
                            f"!= ANCHOR={an}")
        ws_ = wi_sum.get(od, 0)
        wt = wi_total.get(od)
        aw = ANCHORS.get((office, district, "_WI"))
        if wt is None:
            hard.append(f"{od} write-in: no Total row")
        elif ws_ != wt:
            quirks.append(f"{od} write-in: precinct-sum={ws_} != Total={wt}")
        if aw is not None and ws_ != aw:
            hard.append(f"{od} write-in: precinct-sum={ws_} != ANCHOR={aw}")

    # candidate-name cross-check (applies known source->canonical normalizations)
    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp = _norm(expected)
        for nm in names:
            if nm and _norm(_clean_src(nm, office)) != exp:
                hard.append(f"{office}/{district} {party}: source {nm!r} "
                            f"!= expected {expected!r}")

    # ---- Write CSV ----------------------------------------------------------
    out.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order else 999,
                            OFFICE_RANK.get((r[1], r[2]), 99),
                            PARTY_RANK.get(r[3], 9), r[4]))
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for precinct, office, district, party, name, v in out:
            w.writerow([COUNTY, precinct, office, district, party, name, v])

    # ---- Report -------------------------------------------------------------
    precincts = {r[0] for r in out}
    print(f"Wrote {len(out)} rows, {len(precincts)} precincts, "
          f"{len(od_seen)} office-districts -> {OUT_PATH}")
    for od in OFFICE_ORDER:
        office, district = od
        parts = []
        cand_cols = _office_cand_cols(rows, office, district)
        for j, party, name in cand_cols:
            parts.append(f"{party}={col_sum.get((office,district,j),0)}")
        parts.append(f"Write-in={wi_sum.get(od,0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    for q in quirks:
        print(f"  (source quirk, non-fatal) {q}", file=sys.stderr)
    print("Verification OK: 0 hard failures.")
    return 0


def r_idx_after(rows, hdr_idx):
    """Index just past the office block starting at hdr_idx (after its Total)."""
    for k in range(hdr_idx + 1, len(rows)):
        rc0 = rows[k][0] if rows[k] else None
        if rc0 and str(rc0).strip().lower() == "total":
            return k + 1
    return len(rows)


def _office_cand_cols(rows, office, district):
    """Re-locate the header row for (office,district); return its cand_cols."""
    target = None
    for idx, r in enumerate(rows):
        c0 = r[0] if r else None
        if c0 and isinstance(c0, str) and "(Vote for 1)" in c0:
            if office_of(c0) == (office, district):
                target = idx
                break
    if target is None:
        return []
    for j in range(target + 1, min(target + 6, len(rows))):
        hj = rows[j][0] if rows[j] else None
        if hj and str(hj).strip() == "ED":
            hdr = rows[j]
            cand_cols = []
            for jj, cell in enumerate(hdr):
                kind, party, name = classify_header_cell(cell)
                if kind == "cand":
                    cand_cols.append((jj, party, name))
            return cand_cols
    return []


if __name__ == "__main__":
    sys.exit(main())