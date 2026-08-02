#!/usr/bin/env python3
"""Dedicated parser for Greene County 2024 general precinct results (XLSX).

The Greene County BOE publishes an NYS SOVC "Subtotals by City/Town/Ward"
XLSX (`Greene.xlsx`) -- one sheet per office. Each sheet has a single
"Counting group: All" block (the per-precinct GRAND TOTAL; no Election
Day/Early/Absentee sub-blocks, so no double-count trap), an "ED" header row,
one row per precinct, and a final "Totals" county-grand-total row.

Header cells are "<Candidate> \\n<PARTY>" (DEM/REP/CON/WFP/LAR; WFP->WOR),
followed by trailing control columns "Undervotes (Blank)" / "Overvotes
(Void)" / "Unqualified Write-ins (Scatter)" / [named write-in columns,
President only] / "Total Votes".

Greene is WHOLLY inside NY-19 / SD-41 / AD-102 -- no split. Canonical offices:
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 19                       Josh Riley (DEM/WOR) / Marcus Molinaro (REP/CON)
  State Senate 41                     Michelle Hinchey (DEM/WOR) / Patrick Sheehan (REP/CON)
  State Assembly 102                  Janet S. Tweed (DEM/WOR) / Christopher Tague (REP/CON)
Non-canonical sheets (County Treasurer, Coroner, Leg 1-9, Justice *,
Council, Prop) are skipped.

Fusion is split at the source (separate DEM/WFP, REP/CON columns) -- exactly
the #148-branch convention; emit one row per party-line column. Write-ins =
"Unqualified Write-ins (Scatter)" + the President sheet's 6 named write-in
columns (Jill Stein / Chase Oliver / Claudia De la Cruz / Cornel West / Shiva
Ayyadurai / Peter Sonski), aggregated into ONE "Write-in" row (party empty)
per (precinct, office) when >0 (per the Chenango/Delaware precedent).
Undervotes/Overvotes omitted. 0-vote rows omitted.

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 NY corpus: Riley/Molinaro/Tweed/Tague match Delaware/Chenango;
Hinchey/Sheehan (SD-41) are Greene-unique (no committed 2024 county carries
them yet) -- taken verbatim from the source, matching the committed 2022
Greene file. President source "Kamala D. Harris and Tim Walz" -> VP mate
dropped. WOR = Working Families (#148 convention, NOT WFP); LAR = LaRouche.

Precinct names: the source prints "Town of Ashland 1 LD 6" (LD = County
Legislative district). The "LD N" suffix is STRIPPED to match the committed
2022 Greene file ("Town of Ashland 1") -- verified: dropping LD yields exactly
the 2022 52-precinct set with zero collisions (no town/ED splits across LDs).
Whitespace collapsed (avoids double-space file_format failures).

SOURCE QUIRK: the "Total Votes" column is defined INCONSISTENTLY across
contests -- for President, Total Votes = cand + writein + Undervotes +
Overvotes; for every other office, Total Votes = cand + writein (under/over
EXCLUDED). The per-precinct self-check therefore accepts EITHER formula.

Verification (all HARD):
  1. per (precinct, office): Total Votes == cand+writein OR cand+writein+
     under+over (tolerates the source's inconsistent TV definition).
  2. per (office, district, party): precinct-sum == "Totals" row == ANCHOR
     (3-way); write-in precinct-sum == Totals-row (Unqualified + named) ==
     ANCHOR _WI.
  3. candidate-name cross-check: each (office,district,party) maps to one
     source header name matching CAND.
Run with uv (openpyxl):  uv run python greene_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "GREENE_XLSX",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Greene.xlsx",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__greene__precinct.csv"
)
COUNTY = "Greene"

SHEETS = [
    ("Presidential", "President", ""),
    ("US Senator", "U.S. Senate", ""),
    ("Congress", "U.S. House", "19"),
    ("State Senator", "State Senate", "41"),
    ("Assembly", "State Assembly", "102"),
]
OFFICE_RANK = {(o, d): i for i, (_, o, d) in enumerate(SHEETS)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}
PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WFP": "WOR",
              "WOR": "WOR", "LAR": "LAR"}

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
    ("State Senate", "41", "DEM"): "Michelle Hinchey",
    ("State Senate", "41", "WOR"): "Michelle Hinchey",
    ("State Senate", "41", "REP"): "Patrick Sheehan",
    ("State Senate", "41", "CON"): "Patrick Sheehan",
    ("State Assembly", "102", "DEM"): "Janet S. Tweed",
    ("State Assembly", "102", "WOR"): "Janet S. Tweed",
    ("State Assembly", "102", "REP"): "Christopher Tague",
    ("State Assembly", "102", "CON"): "Christopher Tague",
}

ANCHORS = {
    ("President", "", "DEM"): 9437, ("President", "", "WOR"): 999,
    ("President", "", "REP"): 13058, ("President", "", "CON"): 1644,
    ("President", "", "_WI"): 302,
    ("U.S. Senate", "", "DEM"): 9650, ("U.S. Senate", "", "WOR"): 1483,
    ("U.S. Senate", "", "REP"): 11751, ("U.S. Senate", "", "CON"): 1684,
    ("U.S. Senate", "", "LAR"): 123, ("U.S. Senate", "", "_WI"): 21,
    ("U.S. House", "19", "DEM"): 8898, ("U.S. House", "19", "WOR"): 1290,
    ("U.S. House", "19", "REP"): 12908, ("U.S. House", "19", "CON"): 1818,
    ("U.S. House", "19", "_WI"): 18,
    ("State Senate", "41", "DEM"): 9665, ("State Senate", "41", "WOR"): 1533,
    ("State Senate", "41", "REP"): 11779, ("State Senate", "41", "CON"): 1689,
    ("State Senate", "41", "_WI"): 12,
    ("State Assembly", "102", "DEM"): 8017, ("State Assembly", "102", "WOR"): 1193,
    ("State Assembly", "102", "REP"): 13433, ("State Assembly", "102", "CON"): 1982,
    ("State Assembly", "102", "_WI"): 12,
}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _src_name(cell, office):
    """Header candidate cell 'Name\\nPARTY' -> name (drop VP mate for President)."""
    s = str(cell or "").split("\n", 1)[0].strip()
    if office == "President" and " and " in s:
        s = s.split(" and ", 1)[0].strip()
    return s


def classify_header(cell):
    """Header cell -> (kind, party_or_None). kind: cand/writein/under/over/tv/ed/skip."""
    if cell is None:
        return ("skip", None)
    s = str(cell)
    low = s.strip().lower()
    if low == "ed":
        return ("ed", None)
    if low == "total votes":
        return ("tv", None)
    if low.startswith("undervotes"):
        return ("under", None)
    if low.startswith("overvotes"):
        return ("over", None)
    if low.startswith("unqualified write-ins") or low.startswith("unqualified writeins"):
        return ("writein", None)
    # "Name \nPARTY"
    if "\n" in s:
        toks = s.split("\n")
        code = toks[-1].strip()
        if code in PARTY_NORM:
            return ("cand", PARTY_NORM[code])
    # bare name -> named write-in column (President: Jill Stein, etc.)
    if s.strip() and "\n" not in s and not low.startswith(("counting", "district",
            "vote", "area", "official", "greene", "general", "nys", "(vote")):
        return ("writein", None)
    return ("skip", None)


def _strip_precinct(label):
    s = re.sub(r"\s+", " ", str(label)).strip()
    s = re.sub(r" LD \d+$", "", s)
    return s


def main():
    wb = openpyxl.load_workbook(SRC_PATH, data_only=True)
    all_rows = []
    prec_order = []
    seen_prec = set()
    od_seen = []
    # verification accumulators
    psum = defaultdict(int)       # (office,district,party) -> precinct sum
    wisum = defaultdict(int)      # (office,district) -> write-in precinct sum
    col_total = {}                # (office,district,col_idx) -> Totals-row val
    wi_total = {}                 # (office,district) -> Totals-row write-in val
    tv_total = {}                 # (office,district) -> Totals-row Total Votes
    layout_by_od = {}             # (office,district) -> layout dict
    name_seen = defaultdict(set)  # (office,district,party) -> source names
    # per-precinct TV self-consistency
    ed_cand = defaultdict(int)
    ed_wi = defaultdict(int)
    ed_under = defaultdict(int)
    ed_over = defaultdict(int)
    ed_tv = defaultdict(int)

    for sheet_name, office, district in SHEETS:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        # find ED header row
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
            label = str(c0).strip()
            if not label:
                continue
            if label.lower() == "totals":
                for j, party in layout["cand_cols"]:
                    col_total[(office, district, j)] = _int(r[j])
                wi_total[(office, district)] = sum(
                    _int(r[j]) for j in layout["writein_cols"])
                if layout["tv_idx"] is not None:
                    tv_total[(office, district)] = _int(r[layout["tv_idx"]])
                break
            # precinct row (skip stray control rows with no numeric data)
            if not any(_int(r[j]) if j < len(r) else False
                       for j, _ in layout["cand_cols"]):
                # row with all-zero cand cols could still be a precinct; check
                # it has numeric content in any data col
                if not any(isinstance(r[j], (int, float))
                           for j in range(1, len(r)) if j < len(r)):
                    continue
            prec = _strip_precinct(label)
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
    # 1. per-precinct TV self-consistency (accept either TV formula)
    for key in set(ed_cand) | set(ed_wi):
        c = ed_cand.get(key, 0)
        w = ed_wi.get(key, 0)
        u = ed_under.get(key, 0)
        o = ed_over.get(key, 0)
        tv = ed_tv.get(key, 0)
        if tv and tv != c + w and tv != c + w + u + o:
            hard.append(f"{key}: TV={tv} != cand+wi({c + w}) and != "
                        f"cand+wi+under+over({c + w + u + o})")

    # 2. per (office,district,party): precinct-sum == Totals row == ANCHOR
    for sheet_name, office, district in SHEETS:
        layout = layout_by_od[(office, district)]
        for j, party in layout["cand_cols"]:
            s = psum.get((office, district, party), 0)
            tr = col_total.get((office, district, j))
            an = ANCHORS.get((office, district, party))
            if tr is None:
                hard.append(f"{office}/{district} {party}: no Totals row")
            elif s != tr:
                hard.append(f"{office}/{district} {party}: precinct-sum={s} "
                            f"!= Totals={tr}")
            if an is not None and tr is not None and tr != an:
                hard.append(f"{office}/{district} {party}: Totals={tr} "
                            f"!= ANCHOR={an}")
            if an is not None and s != an:
                hard.append(f"{office}/{district} {party}: precinct-sum={s} "
                            f"!= ANCHOR={an}")
        ws_ = wisum.get((office, district), 0)
        wt = wi_total.get((office, district))
        aw = ANCHORS.get((office, district, "_WI"))
        if wt is None:
            hard.append(f"{office}/{district} write-in: no Totals row")
        elif ws_ != wt:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws_} "
                        f"!= Totals={wt}")
        if aw is not None and wt is not None and wt != aw:
            hard.append(f"{office}/{district} write-in: Totals={wt} "
                        f"!= ANCHOR={aw}")
        if aw is not None and ws_ != aw:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws_} "
                        f"!= ANCHOR={aw}")

    # 3. candidate-name cross-check
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