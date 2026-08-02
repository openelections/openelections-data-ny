#!/usr/bin/env python3
"""Dedicated parser for Chenango County 2024 general precinct PDF (NaturalPDF).

The Chenango SOVC PDF (55 pages) uses a "by District" SOVC layout the shared
ny2024_rpp_parser.py cannot open. Each office is printed once per COUNTING GROUP
("All", "Election Day", "Early Voting", "Absentee, Early Mail Ballot, ..."). Only
the "Counting Group - All" page is the grand total; the others are disjoint
subsets that would double-count votes if merged. This parser processes ONLY the
"All" pages.

Each "All" page is a wide table: one column per party line (candidate names repeat
for fusion candidates), then write-in column(s), Void, Blank, Total Votes.
extract_text wraps the multi-line column headers into a garbled mess, but
page.extract_tables() recovers the header row cleanly -- each vote-column cell is
"<candidate>\\n(<party>)" (or "(Write-in)" for an individual named write-in, or
"Write-in" for the aggregate). Precinct names lose their spaces in
extract_tables ("NorwichWard1"), so precinct names are taken from extract_text
(with spaces) by splitting each data row as  precinct = tokens[:-N],
votes = tokens[-N:], where N = (number of table columns - 1) from the header.

Canonical office-districts (their "All" pages): President (p5), U.S. Senate
(p9), U.S. House 19 (p13), State Senate 51 (p17), State Senate 53 (p21), State
Assembly 121 (p25), State Assembly 131 (p29). Non-canonical "All" pages
(Family Court Judge p31, town offices p35+) are skipped because their office
title does not classify. Pages 2-4 etc. (non-"All" counting groups) are skipped
by the counting-group gate.

Write-ins: the aggregate "Write-in" column is emitted as a single "Write-in"
row (party empty) for every office, including President. President also has
individual named write-in columns (Claudia De la Cruz, Chase Oliver, Jill Stein,
Cornel West), but they are only a PARTIAL breakdown -- countywide the named
columns sum to 69 while the aggregate is 115 (46 votes are unnamed write-ins the
BOE did not break out), so the named columns are skipped to avoid undercounting
and double-counting. (The committed NY 2024 corpus uses aggregate "Write-in" for
most counties; the user's individual-named-rows preference applied to Albany,
where the named breakdown is complete and sums to the aggregate. Here it is
not.) 0-vote rows are omitted throughout.

Candidate names: the PDF prints short/wrapped names; this parser resolves the
full canonical name from (office, district, party) via a hardcoded CAND map
matching the committed NY 2024 counties (Tompkins/Broome/Oneida/...).

Page stacking: a page may print more than one counting group (e.g. the Assembly
131 page carries both "Counting Group - All" and "Counting Group: Election
Day"); only the "All" section's lines are parsed (truncated at the next
"Counting Group" line) so the disjoint subsets are not merged and double-counted.

Verification: every party-line column's county sum over precincts must equal
that column's "Total" row value, and the aggregate write-in column's precinct
sum must equal its "Total" row. Run with uv:  uv run python chenango_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "CHENANGO_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Chenango.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__chenango__precinct.csv"
)

PARTY_NORM = {
    "DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
    "LaRouche": "LAR", "LAR": "LAR", "WFP": "WOR", "WF": "WOR",
}

# (office, district, party) -> full canonical candidate name (matches committed
# NY 2024 counties). Each party line of a fusion candidate is a separate row.
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
    ("State Senate", "53", "DEM"): "James Meyers",
    ("State Senate", "53", "WOR"): "James Meyers",
    ("State Senate", "53", "REP"): "Joseph A. Griffo",
    ("State Senate", "53", "CON"): "Joseph A. Griffo",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}

def _is_int(s):
    return bool(s) and s.replace(",", "").isdigit()


def _i(s):
    return int(s.replace(",", ""))


def office_of(text):
    """Classify a page's office from its header text -> (office, district) or None."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    office_line = next((l for l in lines if l.startswith("Office:")), "")
    district_line = next((l for l in lines
                          if l.startswith("District:") and
                          ("Senatorial" in l or "Assembly District" in l)), "")
    o = office_line.lower()
    if "president" in o:
        return ("President", "")
    if "united states senator" in o:
        return ("U.S. Senate", "")
    if "rep in congress" in o or "congress" in o:
        m = re.search(r"(\d+)\w*\s*District", office_line)
        return ("U.S. House", m.group(1) if m else "")
    if "state senator" in o:
        m = re.search(r"(\d+)", district_line)
        return ("State Senate", m.group(1) if m else "")
    if "member of assembly" in o:
        m = re.search(r"(\d+)", district_line)
        return ("State Assembly", m.group(1) if m else "")
    return None


def parse_col_header(cell):
    """Vote-column header cell -> {'kind','party','name'}.

    kind: 'candidate' (party line), 'writein_individual' (named write-in),
          'writein_aggregate' (the "Write-in" total column), 'void', 'blank',
          'total', or 'unknown'.
    """
    if not cell:
        return {"kind": "unknown", "party": "", "name": ""}
    m = re.search(r"\(([^)]+)\)", cell)
    if m:
        code = m.group(1).strip()
        low = code.lower()
        if "write" in low:  # "(Write-in)" with a candidate name before it
            name_part = cell[:m.start()]
            name = " ".join(name_part.split())
            return {"kind": "writein_individual", "party": "", "name": name}
        party = PARTY_NORM.get(code, code)
        return {"kind": "candidate", "party": party, "name": ""}
    cleaned = " ".join(cell.split()).lower().replace("-", " ")
    if "write" in cleaned and "in" in cleaned:
        return {"kind": "writein_aggregate", "party": "", "name": ""}
    if "void" in cleaned:
        return {"kind": "void", "party": "", "name": ""}
    if "blank" in cleaned:
        return {"kind": "blank", "party": "", "name": ""}
    if "total" in cleaned and "vote" in cleaned:
        return {"kind": "total", "party": "", "name": ""}
    if cleaned == "total":
        return {"kind": "total", "party": "", "name": ""}
    return {"kind": "unknown", "party": "", "name": ""}


def all_section_lines(text):
    """Return the lines of the '... Group - All' section only.

    A page may stack several counting groups on one page (e.g. the Assembly 131
    page prints both 'Counting Group - All' and 'Counting Group: Election Day');
    parsing the whole page would merge the disjoint subsets and double-count
    votes. The 'All' section runs from its group line up to the next group line
    (or end of page). Returns [] if no 'All' section is present.

    Matching is on the word 'Group' (not 'Counting Group'): a handful of pages
    in this PDF have a source typo 'County Group - All' (missing the 'ing'), so
    requiring 'Counting Group' would silently drop State Senate 51 and State
    Assembly 121. 'All' is matched case-sensitively so the 'Absentee, Early Mail
    Ballot, ...' group line (lowercase 'all' inside 'Ballot') is not confused
    with the All section.
    """
    lines = text.splitlines()
    group_idx = [i for i, l in enumerate(lines) if "Group" in l]
    all_idx = next((i for i in group_idx if "All" in lines[i]), None)
    if all_idx is None:
        return []
    end_idx = next((i for i in group_idx if i > all_idx), len(lines))
    return lines[all_idx:end_idx]


def parse_page(page):
    """Parse one "Counting Group - All" page.

    Returns (rows, col_totals) where rows = [(office,district,party,candidate,
    precinct,votes)] and col_totals = [int per vote column] from the Total row
    (for verification).
    """
    text = page.extract_text() or ""
    section = all_section_lines(text)
    if not section:
        return [], []
    cls = office_of(text)
    if cls is None:
        return [], []
    office, district = cls

    try:
        tables = page.extract_tables()
    except Exception:
        return [], []
    if not tables or not tables[0] or not tables[0][0]:
        return [], []
    hdr = tables[0][0]
    ncols = len(hdr)
    n_votes = ncols - 1  # all columns except ElectionDistrict

    cols = [parse_col_header(hdr[i]) for i in range(1, ncols)]

    rows = []
    col_totals = [None] * n_votes  # filled from the Total row

    for raw in section:
        tokens = raw.split()
        if len(tokens) < n_votes + 1:
            continue
        votes = tokens[-n_votes:]
        if not all(_is_int(v) for v in votes):
            continue
        name_tokens = tokens[:-n_votes]
        if not name_tokens or not name_tokens[0][:1].isalpha():
            continue
        precinct = " ".join(name_tokens)

        if precinct.lower() == "total":
            col_totals = [_i(v) for v in votes]
            continue

        for i, v in enumerate(votes):
            votes_i = _i(v)
            if votes_i == 0:
                continue
            c = cols[i]
            kind = c["kind"]
            if kind == "candidate":
                cand = CAND.get((office, district, c["party"]))
                if cand is None:
                    continue
                rows.append((office, district, c["party"], cand, precinct, votes_i))
            elif kind == "writein_aggregate":
                # The aggregate "Write-in" column is the true per-precinct
                # write-in total. President also has named write-in columns, but
                # they are only a PARTIAL breakdown (named 69 vs aggregate 115
                # countywide -- 46 votes are unnamed), so emitting the aggregate
                # is the accurate representation; named columns are skipped to
                # avoid double-counting.
                rows.append((office, district, "", "Write-in", precinct, votes_i))
            # writein_individual / void / blank / total / unknown -> skip
    return rows, col_totals


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    party_line_totals = {}      # (office,district,party,candidate) -> Total-row col value
    writein_agg_totals = {}     # (office,district) -> aggregate write-in Total-row value

    for page in pdf.pages:
        rows, col_totals = parse_page(page)
        if not rows and not col_totals:
            continue
        all_rows.extend(rows)
        text = page.extract_text() or ""
        cls = office_of(text)
        if cls is None:
            continue
        office, district = cls

        # Walk the page's column totals alongside the header kinds to record
        # party-line totals and write-in totals for verification.
        try:
            hdr = page.extract_tables()[0][0]
        except Exception:
            hdr = []
        n_votes = len(hdr) - 1 if hdr else 0
        cols = [parse_col_header(hdr[i]) for i in range(1, n_votes + 1)] if hdr else []
        for i, c in enumerate(cols):
            if i >= len(col_totals):
                break
            tv = col_totals[i]
            if tv is None:
                continue
            if c["kind"] == "candidate":
                cand = CAND.get((office, district, c["party"]))
                if cand:
                    party_line_totals[(office, district, c["party"], cand)] = tv
            elif c["kind"] == "writein_aggregate":
                writein_agg_totals[(office, district)] = \
                    writein_agg_totals.get((office, district), 0) + tv

    # ---- Verification -------------------------------------------------------
    problems = []

    # 1. Each party-line column: precinct-sum == Total-row column total.
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        if party == "":
            continue  # write-ins checked separately
        k = (office, district, party, cand)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in party_line_totals.items():
        sv = sums.get(k, 0)
        if sv != tv:
            problems.append(f"party-line total mismatch {k}: precinct-sum={sv} pdf-total={tv}")
    for k in sorted(set(sums) - set(party_line_totals)):
        problems.append(f"{k}: emitted party-line votes but no Total row found")

    # 2. Aggregate write-in column: precinct-sum == Total row (every office).
    agg_sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        if party == "" and cand == "Write-in":
            agg_sums[(office, district)] = agg_sums.get((office, district), 0) + votes
    for k, tv in writein_agg_totals.items():
        sv = agg_sums.get(k, 0)
        if sv != tv:
            problems.append(f"write-in aggregate total mismatch {k}: precinct-sum={sv} pdf-total={tv}")
    for k in sorted(set(agg_sums) - set(writein_agg_totals)):
        problems.append(f"{k}: emitted write-in votes but no Total row found")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Chenango", precinct, office, district, party, cand, votes])

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
          f"{len(agg_sums)} aggregate write-in sums == Total rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())