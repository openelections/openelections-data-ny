#!/usr/bin/env python3
"""Dedicated parser for Allegany County 2024 general precinct PDF (NaturalPDF).

The Allegany SOVC PDF (7 pages) uses a wide tabular "Election Book" layout the
shared ny2024_rpp_parser.py cannot handle: each of pages 1/3/4 prints TWO
contests side-by-side as a single table, and extract_text interleaves the two
on every line ("Alfred 1 368 93 18 31 12 Alfred 1 351 83 17 46 1 0"). The
header text is rotated/garbled in extract_text, but NaturalPDF's
extract_tables() recovers the grid cleanly: the two contests are one table with
an empty separator column, the header row carries the office title in each
block's precinct column and the "<candidate>\\n<party>" label in each vote
column, and data rows carry the precinct name + integer votes.

Canonical office-districts present (pages 1, 3, 4):
  p1 left  President             p1 right U.S. Senate
  p3 left  U.S. House 23         p3 right State Senate 57
  p4 left  State Senate 58       p4 right State Assembly 148
Pages 2 (Supreme Court 8th Jud.) and 5-7 (town/village offices, propositions)
are non-canonical and skipped automatically (their office titles don't
classify and/or their tables don't have two precinct columns).

The PDF prints SHORT candidate names ("Harris/Walz", "T. Carle"); this parser
maps each (office, district, party) to the full canonical name used by the
committed NY 2024 counties (e.g. Cattaraugus/Chemung), maps Working Families ->
WOR and LaRouche -> LAR, and emits the aggregate "Write In" column as a single
"Write-in" row (party empty). Per the no-0-vote-row policy, all 0-vote rows
(party lines and write-ins) are omitted.

Verification: every party-line column's county sum (over precincts) must equal
the table's "Total" row for that column; every fusion candidate's party-line
sum must equal the candidate-total row printed under the table. Run with uv
(natural_pdf needs Python >=3.12):  uv run python allegany_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "ALLEGANY_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Allegany.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__allegany__precinct.csv"
)

# Party-code normalization for the header cell's last line.
PARTY_NORM = {
    "DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
    "LaRouche": "LAR", "LAR": "LAR", "WFP": "WOR", "WF": "WOR",
    "IND": "IND", "GRE": "GRE", "LIB": "LIB", "SAM": "SAM",
}

# (office, district, party) -> full canonical candidate name (matches the
# committed 2024 NY counties: Cattaraugus, Chemung, Seneca, ...). Each party
# line of a fusion candidate is a separate row.
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
    ("U.S. House", "23", "DEM"): "Thomas A. Carle",
    ("U.S. House", "23", "REP"): "Nicholas A. Langworthy",
    ("U.S. House", "23", "CON"): "Nicholas A. Langworthy",
    ("State Senate", "57", "REP"): "George M. Borrello",
    ("State Senate", "57", "CON"): "George M. Borrello",
    ("State Senate", "58", "REP"): "Thomas F. O'Mara",
    ("State Senate", "58", "CON"): "Thomas F. O'Mara",
    ("State Assembly", "148", "DEM"): "Daniel J. Brown",
    ("State Assembly", "148", "REP"): "Joseph Sempolinski",
    ("State Assembly", "148", "CON"): "Joseph Sempolinski",
}

# Short PDF name -> full candidate name, for verifying the candidate-total
# rows printed under each table ("Harris/Walz 5802" -> Kamala D. Harris, 5802).
SHORT2FULL = {
    "Harris/Walz": "Kamala D. Harris",
    "Trump/Vance": "Donald J. Trump",
    "K. Gillibrand": "Kirsten E. Gillibrand",
    "M. Sapraicone": "Michael D. Sapraicone",
    "D. Sare": "Diane Sare",
    "T. Carle": "Thomas A. Carle",
    "N. Langworthy": "Nicholas A. Langworthy",
    "N.Langworthy": "Nicholas A. Langworthy",
    "G. Borrello": "George M. Borrello",
    "T. O'Mara": "Thomas F. O'Mara",
    "D. Brown": "Daniel J. Brown",
    "J. Sempolinski": "Joseph Sempolinski",
}


def classify_office(title):
    """Map a header office-title cell to (office, district) or None."""
    if not title:
        return None
    t = title.replace("\n", " ")
    low = t.lower()
    if "president" in low:
        return ("President", "")
    if "senator" in low:                       # "United States Senator"
        return ("U.S. Senate", "")
    if "congress" in low:                      # "United States Congress Dist 23"
        m = re.search(r"Congress\D+(\d+)", t)
        return ("U.S. House", m.group(1) if m else "")
    if "senate" in low:                        # "57th Senate District"
        m = re.search(r"(\d+)", t)
        return ("State Senate", m.group(1) if m else "")
    if "assembly" in low:                      # "148th Assembly"
        m = re.search(r"(\d+)", t)
        return ("State Assembly", m.group(1) if m else "")
    return None


def parse_header_cell(cell):
    """Vote-column header cell -> (party, short_candidate) or ('WRITEIN','').

    Cell text is "<candidate>\\n<party>" (candidate may itself span lines, e.g.
    "M.\\nSapraicone\\nREP"); the last line is the party code. "Write\\nIn" is
    the aggregate write-in column."""
    if not cell:
        return None
    lines = [l.strip() for l in cell.split("\n") if l.strip()]
    if not lines:
        return None
    if " ".join(lines).lower().replace("-", " ") == "write in":
        return ("WRITEIN", "")
    party_raw = lines[-1]
    party = PARTY_NORM.get(party_raw, party_raw)
    return (party, " ".join(lines[:-1]))


def _is_text(cell):
    if not cell:
        return False
    s = cell.strip()
    return bool(s) and any(ch.isalpha() for ch in s)


def _is_num(cell):
    if not cell:
        return False
    return cell.strip().replace(",", "").isdigit()


def _i(s):
    return int(s.replace(",", ""))


def parse_table(rows):
    """Parse one extract_tables() table (two side-by-side contests).

    Returns (emitted_rows, col_totals, cand_totals) where
      emitted_rows = [(office, district, party, candidate, precinct, votes)]
      col_totals   = {(office,district,party,candidate): total}  (from Total row)
      cand_totals  = {(office,district,candidate): total}        (candidate-total rows)
    Only canonical office blocks are emitted.
    """
    if not rows or not rows[0]:
        return [], {}, {}
    ncols = len(rows[0])

    # Header row = the row carrying "Vote for" in some cell.
    header_idx = None
    for i, r in enumerate(rows):
        if any("vote for" in (c or "").lower() for c in r):
            header_idx = i
            break
    if header_idx is None:
        return [], {}, {}
    header = rows[header_idx]
    data = rows[header_idx + 1:]

    # Precinct columns = columns with many alphabetic (non-numeric) cells across
    # data rows. A two-contest table has exactly two; single-contest local tables
    # have one and are skipped.
    text_count = [sum(1 for r in data if _is_text(r[i] if i < len(r) else None))
                  for i in range(ncols)]
    precinct_cols = [i for i in range(ncols) if text_count[i] > 3]
    if len(precinct_cols) != 2:
        return [], {}, {}
    left_pc, right_pc = precinct_cols

    def block_vote_cols(pc_lo, pc_hi):
        """Numeric columns strictly between pc_lo and pc_hi (excludes the empty
        separator column, which has no numeric cells)."""
        return [i for i in range(pc_lo + 1, pc_hi)
                if any(_is_num(r[i] if i < len(r) else None) for r in data)]

    left_votes = block_vote_cols(left_pc, right_pc)
    right_votes = [i for i in range(right_pc + 1, ncols)
                   if any(_is_num(r[i] if i < len(r) else None) for r in data)]

    emitted = []
    col_totals = {}
    cand_totals = {}

    for pc, vote_cols in ((left_pc, left_votes), (right_pc, right_votes)):
        office_cell = header[pc] if pc < len(header) else None
        cls = classify_office(office_cell)
        if cls is None:
            continue  # non-canonical block (Supreme Court, town office, ...)
        office, district = cls

        # Per-column (party, short_cand) from the header; resolve the full
        # candidate via CAND[(office,district,party)].
        col_party = []
        for vi in vote_cols:
            ph = parse_header_cell(header[vi] if vi < len(header) else None)
            if ph is None:
                col_party.append(None)
                continue
            party, short = ph
            col_party.append((party, short))

        for r in data:
            if pc >= len(r):
                continue
            precinct = (r[pc] or "").strip()
            if not precinct:
                continue
            # Total row -> capture per-column county totals for verification.
            if precinct.lower() == "total":
                for vi, ph in zip(vote_cols, col_party):
                    if ph is None or ph[0] == "WRITEIN":
                        # write-in column total: still record for verification
                        key = (office, district, "", "Write-in")
                        val = r[vi] if vi < len(r) else None
                        if _is_num(val):
                            col_totals[key] = _i(val)
                        continue
                    party = ph[0]
                    cand = CAND.get((office, district, party))
                    if cand is None:
                        continue
                    val = r[vi] if vi < len(r) else None
                    if _is_num(val):
                        col_totals[(office, district, party, cand)] = _i(val)
                continue
            # Candidate-total rows have all-None vote cells -> skip emission,
            # but capture for verification ("<short> <total>").
            if not any((r[vi] if vi < len(r) else None) and
                       (r[vi] or "").strip() for vi in vote_cols):
                m = re.match(r"^(.+?)\s+(\d[\d,]*)$", precinct)
                if m and m.group(1) in SHORT2FULL:
                    cand = SHORT2FULL[m.group(1)]
                    cand_totals[(office, district, cand)] = _i(m.group(2))
                continue
            # Precinct data row.
            for vi, ph in zip(vote_cols, col_party):
                if ph is None:
                    continue
                party, short = ph
                val = r[vi] if vi < len(r) else None
                if not _is_num(val):
                    continue
                votes = _i(val)
                if votes == 0:
                    continue  # no-0-vote-row policy
                if party == "WRITEIN":
                    emitted.append((office, district, "", "Write-in", precinct, votes))
                else:
                    cand = CAND.get((office, district, party))
                    if cand is None:
                        # unexpected party for this office; record but skip
                        continue
                    emitted.append((office, district, party, cand, precinct, votes))
    return emitted, col_totals, cand_totals


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    col_totals = {}    # (office,district,party,candidate) -> county total
    cand_totals = {}   # (office,district,candidate) -> county total

    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception as e:
            print(f"  page {page.index + 1}: extract_tables failed: {e}",
                  file=sys.stderr)
            continue
        for table in tables:
            if not table:
                continue
            emitted, ct, cdt = parse_table(table)
            all_rows.extend(emitted)
            col_totals.update(ct)
            cand_totals.update(cdt)

    # ---- Verification -------------------------------------------------------
    problems = []

    # 1. Per party-line: sum of precinct votes == Total-row column total.
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        k = (office, district, party, cand)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in col_totals.items():
        sv = sums.get(k, 0)
        if sv != tv:
            problems.append(f"column total mismatch {k}: precinct-sum={sv} pdf-total={tv}")
    for k in sorted(set(sums) - set(col_totals)):
        problems.append(f"{k}: emitted votes but no Total row found")

    # 2. Per candidate: sum across party lines == candidate-total row.
    per_cand = {}
    for office, district, party, cand, precinct, votes in all_rows:
        if party == "":
            continue  # write-ins are not in candidate-total rows
        per_cand[(office, district, cand)] = \
            per_cand.get((office, district, cand), 0) + votes
    for k, tv in cand_totals.items():
        sv = per_cand.get(k, 0)
        if sv != tv:
            problems.append(f"candidate total mismatch {k}: party-sum={sv} pdf-total={tv}")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Allegany", precinct, office, district, party, cand, votes])

    precincts = {r[4] for r in all_rows}
    offices = []
    for r in all_rows:
        if r[0] not in offices:
            offices.append(r[0])
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"offices={offices} -> {OUT_PATH}")
    if problems:
        print(f"=== {len(problems)} VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in problems[:60]:
            print("  " + p, file=sys.stderr)
        if len(problems) > 60:
            print(f"  ... and {len(problems) - 60} more", file=sys.stderr)
        return 1
    print(f"Verification OK: {len(sums)} party-line sums == Total-row columns; "
          f"{len(per_cand)} candidate party-sums checked against candidate-total "
          f"rows (where printed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())