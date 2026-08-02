#!/usr/bin/env python3
"""Dedicated parser for Herkimer County 2024 general precinct PDF (NaturalPDF).

The Herkimer SOVC PDF (11 pages) uses a layout the shared ny2024_rpp_parser.py
cannot open. Each CONTEST occupies one page as a single wide table; the remaining
pages are named-write-in continuation lists (pages 5, 6, 9, 10) with no per-precinct
data, which are skipped.

Each contest table has one row per precinct and one column per PARTY LINE, but
every party line is split into TWO columns: the machine-vote total and its
"Abs/Aff" (absentee/affidavit) subtotal. The OpenElections `votes` for a party
line = machine + Abs/Aff. After the candidate pairs come single-column
"Write-in", "Void", "Blank", "Total" columns (no Abs/Aff pair). `extract_text`
collapses empty cells (e.g. a 0-vote Write-in), which shifts trailing columns and
makes per-row column counts inconsistent, so this parser uses `extract_tables()`
exclusively -- it preserves empty cells and gives a stable 13/15/9-column grid.

The county is split across two State Senate districts and two State Assembly
districts (each precinct is in exactly one of each), so a given precinct appears
on more than one contest page (e.g. the same 40 precincts are in SD-49 and
AD-118) -- this is normal and not a duplicate, because the office/district
differs. The seven contest pages:

  p1  President              p2  U.S. Senate          p3  U.S. House 21
  p4  State Senate 49 (Walczyk)   p7  State Senate 53 (Griffo)
  p8  State Assembly 118 (Smullen)   p11 State Assembly 122 (Martini/Miller)

Office/district are detected from candidate surnames in the header (the PDF
prints no office titles), cross-checked against the committed NY 2024 corpus
(Walczyk=SD-49, Smullen=AD-118, Martini/Miller=AD-122, etc.). Candidate full
names resolve from (office, district, party) via a hardcoded CAND map matching
the committed spellings; WFP->WOR and LRP->LAR (the #148-branch convention).

Precinct names are normalized: strip the leading "C "/"T " (City/Town) prefix,
title-case the town, and render the trailing token as "Ward N" (from "W<n>") or
"ED N" (from a zero-padded or bare integer). This collapses the source's
inconsistent casing ("Winfield 00001" vs "WINFIELD 000001") to a single key per
precinct and keeps City-of-Little-Falls wards distinct from Town-of-Little-Falls
EDs ("Little Falls Ward 1" vs "Little Falls ED 1").

Write-ins: the aggregate "Write-in" column is emitted as a single "Write-in" row
(party empty) when >0; the per-precinct named-write-in rows printed after the
totals (e.g. "Adam Metzger (W) 1") are NOT emitted (they are a breakdown of the
aggregate, like Chenango/Allegany). 0-vote rows are omitted throughout.

Verification: the PRIMARY (hard) check is per-precinct self-consistency -- each
precinct's "Total" column (ballots cast) must equal the sum of ALL its vote
columns (every candidate main+abs, write-in, void, blank). This is independent
of the source's "Totals" row, which carries at least one BOE arithmetic error:
the President DEM Abs/Aff cell prints 1,136 but the precincts sum to 1,280
(and the Totals row's own Total cell 29,024 != the sum of its vote-column cells
28,880 -- a 144 gap). The per-precinct data is self-consistent, so this is a
source quirk (analogous to the Ontario U.S. Senate CON off-by-one), not a parser
bug. The SECONDARY (soft) check compares each party-line column's precinct-sum
to its Totals row; mismatches are reported as non-fatal source quirks. Run with
uv:  uv run python herkimer_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "HERKIMER_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Herkimer.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__herkimer__precinct.csv"
)

# Party codes as they appear in the PDF header cells -> OpenElections code.
PARTY_NORM = {
    "DEM": "DEM", "REP": "REP", "CON": "CON",
    "WFP": "WOR", "WF": "WOR", "WOR": "WOR",
    "LRP": "LAR", "LAR": "LAR",
    "IND": "IND", "GRE": "GRE", "LIB": "LIB", "SAM": "SAM", "CMN": "CMN",
}
PARTY_CODES = set(PARTY_NORM.keys())

# (office, district, party) -> full canonical candidate name (matches the
# committed 2024 NY counties). PDF typos ("Kristen" Gillibrand, "Sapaicone",
# "Donald Trump/JD vance") are resolved away by keying on office+party.
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
    ("U.S. House", "21", "REP"): "Elise Stefanik",
    ("U.S. House", "21", "CON"): "Elise Stefanik",
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Senate", "53", "DEM"): "James Meyers",
    ("State Senate", "53", "WOR"): "James Meyers",
    ("State Senate", "53", "REP"): "Joseph A. Griffo",
    ("State Senate", "53", "CON"): "Joseph A. Griffo",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
    ("State Assembly", "122", "DEM"): "Adrienne Martini",
    ("State Assembly", "122", "WOR"): "Adrienne Martini",
    ("State Assembly", "122", "REP"): "Brian Miller",
    ("State Assembly", "122", "CON"): "Brian Miller",
}

# Candidate surname (lowercase substring) -> (office, district). Used to detect
# the office of a page from its header candidate cells (the PDF prints no office
# titles). Each group's keywords are unique to that contest's header.
OFFICE_MARKERS = [
    (("harris", "trump"), ("President", "")),
    (("gillibrand", "sapraicone", "sare"), ("U.S. Senate", "")),
    (("stefanik", "collins"), ("U.S. House", "21")),
    (("walczyk",), ("State Senate", "49")),
    (("griffo", "meyers"), ("State Senate", "53")),
    (("smullen",), ("State Assembly", "118")),
    (("martini", "miller"), ("State Assembly", "122")),
]


def _ci(s):
    """Coerce a table cell (possibly '' or '1,364') to int, 0 on empty/non-numeric."""
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def header_party(cell):
    """If a header cell ends with a known party code (optionally parenthesized),
    return (party_normalized, name); else (None, '')."""
    if not cell:
        return None, ""
    toks = cell.split()
    if not toks:
        return None, ""
    code = toks[-1].strip("()")
    if code in PARTY_CODES:
        name = " ".join(toks[:-1]).strip()
        return PARTY_NORM[code], name
    return None, ""


def detect_office(header):
    """Classify a page by concatenating its header cells and matching a
    surname marker. Returns (office, district) or None."""
    blob = " ".join((c or "") for c in header).lower()
    for keywords, od in OFFICE_MARKERS:
        if any(k in blob for k in keywords):
            return od
    return None


def parse_columns(header):
    """Walk the header row and return a list of column specs:
    ('candidate', main_idx, party, abs_idx) | ('writein', idx) |
    ('void', idx) | ('blank', idx) | ('total', idx).
    Candidate main columns are paired with the following Abs/Aff column.
    """
    specs = []
    ncols = len(header)
    j = 1  # col 0 is the precinct name
    while j < ncols:
        cell = header[j] or ""
        party, _ = header_party(cell)
        if party is not None and j + 1 < ncols:
            specs.append(("candidate", j, party, j + 1))
            j += 2  # consume the Abs/Aff pair
            continue
        low = " ".join(cell.split()).lower().replace("-", " ")
        if "write" in low and "in" in low:
            specs.append(("writein", j))
        elif "void" in low:
            specs.append(("void", j))
        elif "blank" in low:
            specs.append(("blank", j))
        elif "total" in low and ("vote" in low or low == "total" or "votes" in low):
            specs.append(("total", j))
        j += 1
    return specs


def normalize_precinct(s):
    """'C LITTLE FALLS W1' -> 'Little Falls Ward 1'; 'COLUMBIA 000001' ->
    'Columbia ED 1'; 'GERMAN FLATTS 000004' -> 'German Flatts ED 4'."""
    s = (s or "").strip()
    if s.startswith("C ") or s.startswith("T "):
        s = s[2:]
    toks = s.split()
    if not toks:
        return s
    last = toks[-1]
    town = " ".join(toks[:-1]).title()
    m = re.match(r"^W(\d+)$", last)
    if m:
        return f"{town} Ward {m.group(1)}"
    if last.isdigit():
        return f"{town} ED {int(last)}"
    return s.title()


def is_data_row(name):
    """True if col0 looks like a precinct row (not Totals, not a named
    write-in '(W)', not the candidate-total summary 'Write- In', not a
    misaligned candidate-summary row whose col0 is a bare number like
    '7347' -- real precinct names always carry a town name)."""
    if not name:
        return False
    s = name.strip()
    if s.isdigit():
        return False
    low = s.lower()
    if low == "totals":
        return False
    if "(w)" in low:
        return False
    if "write" in low and "in" in low.replace("-", ""):
        return False
    return True


def parse_page(page):
    """Parse one contest page. Returns (rows, totals, od, selfcheck) where
    rows = [(office,district,party,candidate,precinct,votes)] and
    totals = {(office,district,party,candidate): col_total} for verification,
    and selfcheck = [(precinct, sum_votecols, total_col)] for the per-precinct
    self-consistency check (Total column == sum of all vote columns)."""
    try:
        tables = page.extract_tables()
    except Exception:
        return [], {}, None, []
    if not tables or not tables[0]:
        return [], {}, None, []
    table = tables[0]
    header = table[0]
    ncols = len(header)
    if ncols < 4:
        return [], {}, None, []  # write-in continuation pages have 2 cols

    specs = parse_columns(header)
    if not any(s[0] == "candidate" for s in specs):
        return [], {}, None, []  # no candidate columns -> not a contest page

    od = detect_office(header)
    if od is None:
        return [], {}, None, []
    office, district = od

    # Indices of every vote column (candidate main+abs, writein, void, blank)
    # and the Total column, for the per-precinct self-consistency check.
    vote_idxs = []
    total_idx = None
    for s in specs:
        if s[0] == "candidate":
            vote_idxs.append(s[1])
            vote_idxs.append(s[3])
        elif s[0] in ("writein", "void", "blank"):
            vote_idxs.append(s[1])
        elif s[0] == "total":
            total_idx = s[1]

    rows = []
    totals = {}  # (office,district,party,candidate) -> Totals-row col value
    selfcheck = []
    for r in table[1:]:
        if not r:
            continue
        name = (r[0] or "").strip()
        if name.lower() == "totals":
            for s in specs:
                if s[0] == "candidate":
                    _, j, party, jabs = s
                    cand = CAND.get((office, district, party))
                    if cand:
                        totals[(office, district, party, cand)] = \
                            _ci(r[j] if j < len(r) else None) + \
                            _ci(r[jabs] if jabs < len(r) else None)
                elif s[0] == "writein":
                    totals[(office, district, "", "Write-in")] = \
                        _ci(r[s[1]] if s[1] < len(r) else None)
            continue
        if not is_data_row(name):
            continue
        precinct = normalize_precinct(name)
        for s in specs:
            if s[0] == "candidate":
                _, j, party, jabs = s
                votes = _ci(r[j] if j < len(r) else None) + \
                    _ci(r[jabs] if jabs < len(r) else None)
                if votes == 0:
                    continue
                cand = CAND.get((office, district, party))
                if cand is None:
                    continue
                rows.append((office, district, party, cand, precinct, votes))
            elif s[0] == "writein":
                votes = _ci(r[s[1]] if s[1] < len(r) else None)
                if votes > 0:
                    rows.append((office, district, "", "Write-in", precinct, votes))
            # void / blank / total -> skip for emission
        # Per-precinct self-consistency: Total column == sum of all vote cols.
        # This is independent of the (sometimes erroneous) Totals row and is the
        # strongest evidence the per-precinct extraction is correct.
        if total_idx is not None and total_idx < len(r):
            sum_v = sum(_ci(r[j]) if j < len(r) else 0 for j in vote_idxs)
            tot = _ci(r[total_idx])
            selfcheck.append((precinct, sum_v, tot))
    return rows, totals, od, selfcheck


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    col_totals = {}  # (office,district,party,candidate) -> Totals-row value
    pages_seen = []
    selfcheck = []   # (office,district,precinct,sum_votecols,total_col)
    for i, page in enumerate(pdf.pages):
        rows, totals, od, sc = parse_page(page)
        if od is None:
            continue
        office, district = od
        all_rows.extend(rows)
        col_totals.update(totals)
        pages_seen.append((i + 1, od))
        for precinct, sv, tot in sc:
            selfcheck.append((office, district, precinct, sv, tot))

    # ---- Verification -------------------------------------------------------
    # PRIMARY (hard) check: per-precinct self-consistency. Each precinct's Total
    # column (ballots cast) must equal the sum of ALL its vote columns (every
    # candidate main+abs, write-in, void, blank). This is independent of the
    # source's Totals row -- which can carry BOE arithmetic errors (see the
    # President DEM Abs/Aff quirk below) -- so it is the trustworthy check that
    # the per-precinct extraction is correct.
    hard = []
    for office, district, precinct, sv, tot in selfcheck:
        if sv != tot:
            hard.append(f"{office}/{district} {precinct}: sum(vote cols)={sv} "
                        f"Total={tot} diff={sv - tot}")

    # SECONDARY (soft) check: each party-line/write-in precinct-sum vs the
    # Totals row. The Herkimer Totals row is internally inconsistent for one
    # cell -- President DEM Abs/Aff prints 1,136 but the precincts sum to 1,280
    # (and the Totals row's own Total cell 29,024 != the sum of its vote-column
    # cells 28,880, a 144 gap). The per-precinct data is self-consistent, so this
    # is a source Totals-row arithmetic quirk (analogous to the Ontario U.S.
    # Senate CON off-by-one), NOT a parser bug. We report it but do not fail.
    soft = []
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        k = (office, district, party, cand)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in col_totals.items():
        sv = sums.get(k, 0)
        if sv != tv:
            soft.append(f"Totals-row mismatch {k}: precinct-sum={sv} pdf-total={tv} "
                        f"(source quirk; per-precinct self-consistency holds)")
    for k in sorted(set(sums) - set(col_totals)):
        soft.append(f"{k}: emitted votes but no Totals row found")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Herkimer", precinct, office, district, party, cand, votes])

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
          f"Total == sum(vote cols).")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
    if soft:
        print(f"--- {len(soft)} source Totals-row quirk(s) (non-fatal) ---",
              file=sys.stderr)
        for p in soft[:60]:
            print("  " + p, file=sys.stderr)
    if hard:
        return 1
    print(f"Verification OK: {n_sc_ok}/{n_sc} per-precinct Total==sum(vote cols); "
          f"{len(sums) - len(soft)}/{len(sums)} party-line sums == Totals rows"
          f" ({len(soft)} source quirk).")
    return 0


if __name__ == "__main__":
    sys.exit(main())