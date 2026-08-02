#!/usr/bin/env python3
"""Dedicated parser for Orange County 2024 general precinct PDF (NaturalPDF).

The Orange County BOE "November 5, 2024 General Election Results" PDF (7 pages)
is a rotated-text SOVC: candidate names are printed rotated/vertical, so
extract_text() garbles them ("P V r ic e e s i P d r e e n s t i..."). The shared
ny2024_rpp_parser.py cannot open it. But NaturalPDF's extract_tables() recovers a
clean 9-column grid on every page, and -- crucially -- a SECOND header row
carries the upright party codes (REP/CON/DEM/WOR), which is all the candidate
mapping needs.

The source PDF contains ONLY the Presidential contest (the county BOE did not
publish Senate/House/Legislature precinct results in this file -- Orange is
source-limited, like Steuben). All 7 pages are President, paginated
alphabetically by town. Each page's table is:

    row0  rotated office + candidate-name fragments  (garbled)
    row1  ''  REP  CON  DEM  WOR  ''  ''  ''  ''      <- upright party codes
    row2+ precinct rows: <Town> [- W00N] - D00N, REP, CON, DEM, WOR,
                          Write-in, Total Votes Cast, Over, Under

So: col0 = precinct, cols1-4 = the four party lines (Trump REP/CON, Harris
DEM/WOR), col5 = aggregate Write-in, col6 = Total Votes Cast, col7 = Over Votes,
col8 = Under Votes. OpenElections votes for a party line = that column (single
number -- there is no absentee/affidavit sub-column split here, unlike Herkimer).

Candidate full names resolve from (office, party) via a hardcoded CAND map
matching the committed NY 2024 corpus; WOR = Working Families (the #148-branch
convention -- NOT WFP/WF). Fusion party lines are SEPARATE rows (same candidate,
different party).

Precinct names normalize "Town - W001 - D001" -> "Town Ward 1 ED 1",
"Town - D001" -> "Town ED 1", and "City of X - W001 - D001" ->
"City of X Ward 1 ED 1" (matching the committed Ward/ED convention used by
Albany/Oneida/Fulton). The "City of" prefix is preserved (as in Cattaraugus/
Fulton). 0-vote rows are omitted throughout (some EDs -- e.g. Monroe D020/D021 --
have all-zero rows in the source and naturally produce no rows).

Write-ins: the aggregate Write-in column (col5) is emitted as a single
"Write-in" row (party empty) when >0, matching the committed-corpus aggregate
convention (no per-precinct named write-ins are printed in this PDF).

Verification: the PRIMARY (hard) check is per-precinct self-consistency -- each
precinct's Total Votes Cast (col6) must equal the sum of its four candidate
columns + Write-in (over/under votes are not part of the total). This is
independent of any totals row. The SECONDARY (soft) check compares each party
line's county sum (and the write-in sum) to the "Grand Total" row printed on
the last page. Run with uv (natural_pdf needs Python >=3.12):
    uv run python orange_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "ORANGE_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Orange.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__orange__precinct.csv"
)

PARTY_NORM = {
    "DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
    "WFP": "WOR", "WF": "WOR", "LAR": "LAR", "IND": "IND",
    "GRE": "GRE", "LIB": "LIB", "SAM": "SAM", "CMN": "CMN",
}
PARTY_CODES = set(PARTY_NORM.keys())

# (office, district, party) -> full canonical candidate name (matches the
# committed 2024 NY counties). Orange's source PDF only carries President.
CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "WOR"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("President", "", "CON"): "Donald J. Trump",
}


def _ci(s):
    """Coerce a cell ('' or '1,364') to int, 0 on empty/non-numeric."""
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def is_totals_row(name):
    """True if the col0 cell is a totals/grand-total row, not a precinct."""
    if not name:
        return False
    low = name.lower().strip()
    return low in ("totals", "total", "grand total", "grand totals")


def is_data_row(name):
    """True if col0 looks like a precinct row (not blank, not a totals row,
    not a bare number). Real precinct names always carry a town name."""
    if not name:
        return False
    s = name.strip()
    if not s:
        return False
    if s.isdigit():
        return False
    if is_totals_row(s):
        return False
    # the rotated office-title fragments ("Presidential Electors ...") can
    # land in col0 of a header-ish row; skip rows with no precinct structure
    # (no '-' separator AND no alphabetic town token). Orange precincts always
    # contain " - D0NN".
    return " - " in s or re.search(r"D\d{3}", s) is not None


def normalize_precinct(s):
    """'Blooming Grove - W001 - D001' -> 'Blooming Grove Ward 1 ED 1';
    'Chester - D001' -> 'Chester ED 1';
    'City of Newburgh - W001 - D001' -> 'City of Newburgh Ward 1 ED 1'."""
    s = (s or "").strip()
    parts = [p.strip() for p in s.split(" - ")]
    if not parts:
        return s
    town = parts[0]
    ward = None
    ed = None
    for p in parts[1:]:
        m = re.match(r"^W0*(\d+)$", p)
        if m:
            ward = int(m.group(1))
            continue
        m = re.match(r"^D0*(\d+)$", p)
        if m:
            ed = int(m.group(1))
            continue
    # Title-case the town but keep an all-caps "City of" prefix readable.
    town = town.title() if not town.startswith("City of ") else town
    out = town
    if ward is not None:
        out += f" Ward {ward}"
    if ed is not None:
        out += f" ED {ed}"
    return out


def parse_page(page):
    """Parse one President page. Returns (rows, grand_totals, selfcheck) where
    rows = [(office,district,party,candidate,precinct,votes)],
    grand_totals = {(office,district,party,candidate): total} from a Grand
    Total row (only present on the last page; empty otherwise),
    selfcheck = [(precinct, sum_votecols, total_col)]."""
    try:
        tables = page.extract_tables()
    except Exception:
        return [], {}, []
    if not tables or not tables[0]:
        return [], {}, []
    table = tables[0]
    if len(table) < 3:
        return [], {}, []
    header0 = [(c or "") for c in table[0]]
    ncols = len(header0)

    # The party-code row: the first data-ish row whose cells include >=2 known
    # party codes. Its columns are the candidate (party-line) columns.
    party_row = None
    for r in table[1:4]:
        codes = [(j, (c or "").strip()) for j, c in enumerate(r)
                 if (c or "").strip() in PARTY_CODES]
        if len(codes) >= 2:
            party_row = codes
            break
    if not party_row:
        return [], {}, []

    cand_cols = [(j, PARTY_NORM[code]) for j, code in party_row]
    cand_idx = [j for j, _ in cand_cols]
    last_cand = max(cand_idx)

    # Write-in column = first col after the last candidate column whose header0
    # fragment contains "write". Total column = the next one whose header0
    # contains "total". (Over/Under follow but are not needed.)
    writein_idx = None
    total_idx = None
    for j in range(last_cand + 1, ncols):
        frag = header0[j].lower() if j < len(header0) else ""
        if writein_idx is None and "write" in frag:
            writein_idx = j
        elif "total" in frag and "vote" in frag:
            total_idx = j
    # Fallbacks if rotated fragments didn't parse cleanly.
    if writein_idx is None and last_cand + 1 < ncols:
        writein_idx = last_cand + 1
    if total_idx is None and last_cand + 2 < ncols:
        total_idx = last_cand + 2

    office, district = "President", ""
    rows = []
    grand = {}
    selfcheck = []
    for r in table:
        if not r:
            continue
        name = (r[0] or "").strip()
        if is_totals_row(name):
            for j, party in cand_cols:
                cand = CAND.get((office, district, party))
                if cand:
                    grand[(office, district, party, cand)] = _ci(
                        r[j] if j < len(r) else None)
            if writein_idx is not None:
                grand[(office, district, "", "Write-in")] = _ci(
                    r[writein_idx] if writein_idx < len(r) else None)
            continue
        if not is_data_row(name):
            continue
        precinct = normalize_precinct(name)
        for j, party in cand_cols:
            votes = _ci(r[j] if j < len(r) else None)
            if votes == 0:
                continue
            cand = CAND.get((office, district, party))
            if cand is None:
                continue
            rows.append((office, district, party, cand, precinct, votes))
        if writein_idx is not None:
            wv = _ci(r[writein_idx] if writein_idx < len(r) else None)
            if wv > 0:
                rows.append((office, district, "", "Write-in", precinct, wv))
        # Per-precinct self-consistency: Total == sum(candidates + write-in).
        if total_idx is not None and total_idx < len(r):
            sum_v = sum(_ci(r[j] if j < len(r) else 0) for j, _ in cand_cols)
            if writein_idx is not None:
                sum_v += _ci(r[writein_idx] if writein_idx < len(r) else 0)
            tot = _ci(r[total_idx])
            selfcheck.append((precinct, sum_v, tot))
    return rows, grand, selfcheck


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    grand_totals = {}
    pages_seen = []
    selfcheck = []
    for i, page in enumerate(pdf.pages):
        rows, grand, sc = parse_page(page)
        if not rows and not grand:
            continue
        all_rows.extend(rows)
        grand_totals.update(grand)
        pages_seen.append(i + 1)
        selfcheck.extend(sc)

    # ---- Verification -------------------------------------------------------
    # PRIMARY (hard): per-precinct Total == sum(candidate cols + write-in).
    hard = []
    for precinct, sv, tot in selfcheck:
        if sv != tot:
            hard.append(f"{precinct}: sum(candidates+write-in)={sv} Total={tot} "
                        f"diff={sv - tot}")

    # SECONDARY (soft): each party-line / write-in county sum == Grand Total row.
    soft = []
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        k = (office, district, party, cand)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in grand_totals.items():
        sv = sums.get(k, 0)
        if sv != tv:
            soft.append(f"Grand Total mismatch {k}: precinct-sum={sv} "
                        f"pdf-total={tv}")
    for k in sorted(set(sums) - set(grand_totals)):
        soft.append(f"{k}: emitted votes but no Grand Total row found")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Orange", precinct, office, district, party, cand, votes])

    precincts = {r[4] for r in all_rows}
    offices = []
    for r in all_rows:
        if r[0] not in offices:
            offices.append(r[0])
    print(f"Pages parsed: {pages_seen}")
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"offices={offices} -> {OUT_PATH}")
    n_sc = len(selfcheck)
    n_sc_ok = n_sc - len(hard)
    print(f"Self-consistency: {n_sc_ok}/{n_sc} precincts satisfy "
          f"Total == sum(candidates+write-in).")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
    if soft:
        print(f"--- {len(soft)} Grand Total mismatch(es) (non-fatal) ---",
              file=sys.stderr)
        for p in soft[:60]:
            print("  " + p, file=sys.stderr)
    if hard:
        return 1
    print(f"Verification OK: {n_sc_ok}/{n_sc} per-precinct Total==sum(cands+wi); "
          f"{len(sums) - len(soft)}/{len(sums)} party-line sums == Grand Total"
          f" ({len(soft)} mismatch).")
    return 0


if __name__ == "__main__":
    sys.exit(main())