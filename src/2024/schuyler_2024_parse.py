#!/usr/bin/env python3
"""Dedicated parser for Schuyler County 2024 general precinct PDF (NaturalPDF).

The Schuyler BOE "NYS SOVC Report" PDF (68 pages) is a "Statement of Vote Cast"
report the shared ny2024_rpp_parser.py cannot open. Each contest is printed once
per COUNTING GROUP ("All", "Election Day", "Absentee", "Early Voting",
"Military", "Affidavit"). Only "All" is the per-precinct grand total; the other
five are disjoint subsets that sum to "All" (verified for Senate: ED 1987 + Abs
391 + Early 1013 + Military 0 + Affidavit 27 = 3418 = All DEM). So this parser
uses ONLY the "All" group for the five offices that publish one, and sums the
sub-groups for U.S. House 24 (whose "All" page is empty/absent -- it starts
directly at "Election Day"). This avoids double-counting and handles House 24
uniformly.

WITHIN each counting group, every precinct has TWO rows: a non-CC row
(machine/Election-Day votes) and a "CC" row (centrally-counted paper ballots --
absentee/early/affidavit paper counted centrally). Per-precinct total for a
group = non-CC + CC. The earlier 2022 Schuyler file kept CC as separate precincts
("CC Catharine 1 Leg 1" vs "Catharine 1 Leg 1") with per-counting-group columns;
this 2024 parser follows the #148-branch 7-column convention (Putnam/Herkimer/
Orange/Chenango/Allegany/Albany): merge non-CC + CC (and across counting groups
for House 24) into ONE grand-total `votes` per (precinct, office, district, party,
candidate), emit a single aggregate "Write-in" row, and omit Overvotes/
Undervotes/Special Votes. 0-vote rows are omitted throughout.

extract_tables() is the clean source (it returns a header row naming every
column and a stable N-column grid), but counting groups can span page
boundaries: a continuation page carries the previous group's CC rows + TOTAL as
its FIRST table and the next group's non-CC rows as its SECOND table, so routing
tables to groups across pages is delicate. For the four offices whose "All"
group rows parse cleanly from extract_text (President, Senate, House 23, SD-58),
this parser walks extract_text() lines in document order across all pages,
tracking the current office (from office-header lines) and counting group (from
"Counting group: X" lines) -- both carry forward across pages until the next
header/group line. Each data line is routed to its (office, district, group)
bucket, which naturally handles page-spanning groups.

State Assembly 132 is the exception: its extract_text() CC rows carry an extra
"Blank" column (8 vote values where there should be 7), so trailing_ints(N)
drops a real vote. Assembly's "All" group fits on a single page (p36) as one
clean extract_tables() table with a header naming every column, so Assembly is
parsed directly from that table via find_office_all_table()/parse_table_rows().
(The N+1 int-counts seen for the other offices' CC rows are NOT the Blank-column
bug -- they are simply "joined" rows where the leg number is an int and is
correctly dropped by trailing_ints(N); only Assembly has the N+2 extra-column
bug.)

Row reassembly (the hard part): a precinct row is a "votes line" -- a line whose
trailing tokens are exactly N integers (N = vote columns for that office) --
plus name tokens on adjacent lines. Two patterns:
  * joined: "Cayuta 1 Leg 1 64 159 16 6 0 9 0 0 9 245" -- the leading tokens
    (Cayuta 1 Leg 1) ARE the precinct name, followed by N votes.
  * split:   "Catharine 1" / "226 423 50 34 4 29 0 0 29 737" / "Leg 1" -- the
    name is split: the line BEFORE the votes is the town+ED[+Leg] part (starts
    with a town or "CC"); the line AFTER is the Leg suffix ("Leg N", a bare
    integer, or "N Leg N"). CC rows split the same way ("CC Catharine" / votes /
    "1 Leg 1"). full_name = before + lead + after; strip "CC"; parse "Town ED Leg N".
The before-line is used only when the votes line has no leading name tokens
(split case); the after-line is used whenever it matches the Leg-suffix pattern.
"Orange" is the one 1-ED town whose CC row omits the ED ("CC Orange Leg 8"), so a
missing ED defaults to 1 to merge with the non-CC "Orange 1 Leg 8".

Canonical offices (district from the office-header line; vote-column count N):
  President      N=14  DEM/REP/CON/WOR (Harris/Trump) + 5 named write-ins +
                       Undervotes/Overvotes/Unqualified/TotalSpecial/TotalVotes
  U.S. Senate    N=10  DEM/REP/CON/WOR/LAR (Gillibrand/Sapraicone/Sare) + 5 trailing
  U.S. House 23  N=8   DEM/REP/CON (Carle/Langworthy) + 5 trailing
  U.S. House 24  N=8   DEM/REP/CON (Wagenhauser/Tenney) + 5 trailing  [no "All"]
  State Senate 58 N=8  REP/CON (Thomas F. O'Mara) + a "Write-in" party column for
                       Thomas Fellers (a named write-in candidate) + 5 trailing
  State Assembly 132 N=7 REP/CON (Philip A. Palmesano) + 5 trailing
Schuyler is split across NY-23 (Catharine/Cayuta/Dix/Montour/Orange, 9 precincts)
and NY-24 (Hector/Reading/Tyrone, 10 precincts) -- disjoint, emitted as separate
office-districts.

Write-ins: a single aggregate "Write-in" row (party empty) per precinct when >0,
= sum of the named-write-in columns + the "Unqualified Write-ins" column (the
total write-in votes). This matches the dominant committed-2024 convention
(Tompkins/Chenango/Herkimer/Orange/Allegany all emit aggregate "Write-in"; only
Albany emits individual named write-ins, where the named breakdown is complete).
For State Senate 58, Fellers (a named write-in with his own column) is folded
into the "Write-in" aggregate -- the committed 2024 corpus has no "Thomas
Fellers" row for SD-58, only O'Mara REP/CON + aggregate "Write-in". WOR = Working
Families (#148-branch convention); LAR = LaRouche.

Verification: the PRIMARY (hard) check is per-precinct self-consistency --
sum(candidate cols) + sum(write-in cols) == Total Votes -- which holds for every
office (President 750+13=763, Senate 737+0, House23 727+1=728, SD58 595+3=598,
Assembly 596+3=599). The SECONDARY (also hard) check compares each column's
precinct-sum to the group's SUB-TOTAL row (the precinct rows must sum to the
Sub-total, or extraction is wrong); for House 24, to the sum of the sub-groups'
SUB-TOTAL rows. A handful of centrally-counted WRITE-IN votes appear only in the
group's "Cumulative" row (TOTAL = Sub-total + Cumulative) and are NOT attributed
to any precinct by the BOE -- 12 for President (Oliver 8, De la Cruz 1, Stein 2,
Sonski 1) and 1 for SD-58 (Fellers). These cannot appear in a per-precinct file
(the committed 2024 NY corpus has no county-wide precinct rows), so they are not
emitted; the gap is reported as a non-fatal source limitation. Candidate votes
have Cumulative = 0 (fully attributed), so all candidate county totals match.
Run with uv (natural_pdf needs Python >=3.12):  uv run python schuyler_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "SCHUYLER_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Schuyler.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__schuyler__precinct.csv"
)

TOWNS = {
    "Catharine", "Cayuta", "Dix", "Hector",
    "Montour", "Orange", "Reading", "Tyrone",
}

# Per office-district: N (vote columns), candidate columns [(col, party, name)],
# write-in columns (their values sum into the aggregate "Write-in" row), and the
# Total-Votes column index (for the self-consistency check). Candidate names
# match the committed 2024 NY counties; Schuyler-specific candidates (Carle,
# Langworthy, Wagenhauser, Tenney, O'Mara, Palmesano) resolved from the source PDF
# + committed corpus.
OFFICES = {
    ("President", ""): {
        "N": 14,
        "candidates": [
            (0, "DEM", "Kamala D. Harris"),
            (1, "REP", "Donald J. Trump"),
            (2, "CON", "Donald J. Trump"),
            (3, "WOR", "Kamala D. Harris"),
        ],
        "writein_cols": [4, 5, 6, 7, 8, 11],  # 5 named write-ins + Unqualified
        "tv": 13,
    },
    ("U.S. Senate", ""): {
        "N": 10,
        "candidates": [
            (0, "DEM", "Kirsten E. Gillibrand"),
            (1, "REP", "Michael D. Sapraicone"),
            (2, "CON", "Michael D. Sapraicone"),
            (3, "WOR", "Kirsten E. Gillibrand"),
            (4, "LAR", "Diane Sare"),
        ],
        "writein_cols": [7],
        "tv": 9,
    },
    ("U.S. House", "23"): {
        "N": 8,
        "candidates": [
            (0, "DEM", "Thomas A. Carle"),
            (1, "REP", "Nicholas A. Langworthy"),
            (2, "CON", "Nicholas A. Langworthy"),
        ],
        "writein_cols": [5],
        "tv": 7,
    },
    ("U.S. House", "24"): {
        "N": 8,
        "candidates": [
            (0, "DEM", "David Wagenhauser"),
            (1, "REP", "Claudia Tenney"),
            (2, "CON", "Claudia Tenney"),
        ],
        "writein_cols": [5],
        "tv": 7,
    },
    ("State Senate", "58"): {
        "N": 8,
        "candidates": [
            (0, "REP", "Thomas F. O'Mara"),
            (1, "CON", "Thomas F. O'Mara"),
        ],
        "writein_cols": [2, 5],  # Fellers (named write-in col) + Unqualified
        "tv": 7,
    },
    ("State Assembly", "132"): {
        "N": 7,
        "candidates": [
            (0, "REP", "Philip A. Palmesano"),
            (1, "CON", "Philip A. Palmesano"),
        ],
        "writein_cols": [4],
        "tv": 6,
    },
}

# Offices that publish a "Counting group: All" page -> use it directly (grand
# total). House 24 has no All page -> sum its sub-groups instead.
USES_ALL = {
    ("President", ""), ("U.S. Senate", ""), ("U.S. House", "23"),
    ("State Senate", "58"), ("State Assembly", "132"),
}

# Office-header line detection: returns (office, district) or None. The header
# is a single line carrying the office name + district ordinal.
def detect_office(line):
    s = line
    if "Electors for President" in s:
        return ("President", "")
    if "US Senate" in s and "Schuyler" in s:
        return ("U.S. Senate", "")
    if "Representative In Congress" in s:
        m = re.search(r"(\d+)\w*\s*Congressional", s)
        return ("U.S. House", m.group(1) if m else "")
    if "New York State Senator" in s:
        m = re.search(r"(\d+)\w*\s*District", s)
        return ("State Senate", m.group(1) if m else "")
    if "Member of Assembly" in s:
        m = re.search(r"(\d+)\w*\s*District", s)
        return ("State Assembly", m.group(1) if m else "")
    return None


def _ci(s):
    """Coerce a table cell ('' or '1,364') to int, 0 on empty/non-numeric."""
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def is_int_tok(t):
    return bool(t) and t.replace(",", "").isdigit()


def trailing_ints(tokens, n):
    """If tokens ends with exactly n comma-stripped ints, return (lead, votes);
    else None. 'exactly' means the token before the run (if any) is not an int,
    so a name+votes line still qualifies (lead = the name tokens)."""
    if len(tokens) < n:
        return None
    tail = tokens[-n:]
    if not all(is_int_tok(t) for t in tail):
        return None
    return tokens[:-n], [int(t.replace(",", "")) for t in tail]


AFTER_RE = re.compile(r"^(?:\d+ )?Leg \d+$|^\d+$")


def starts_town_or_cc(tokens):
    """True if the line's first token is a precinct town or 'CC'."""
    return bool(tokens) and (tokens[0] in TOWNS or tokens[0] == "CC")


def normalize_precinct(tokens):
    """tokens (a precinct-name fragment list, possibly starting with 'CC') ->
    canonical 'Town ED Leg N', or None if not a valid precinct. A missing ED
    (only 1-ED towns do this, e.g. 'CC Orange Leg 8') defaults to 1."""
    toks = list(tokens)
    if toks and toks[0] == "CC":
        toks = toks[1:]
    # find town
    town = next((t for t in toks if t in TOWNS), None)
    if town is None:
        return None
    if "Leg" not in toks:
        return None
    leg_idx = toks.index("Leg")
    if leg_idx + 1 >= len(toks) or not toks[leg_idx + 1].isdigit():
        return None
    leg = toks[leg_idx + 1]
    town_idx = toks.index(town)
    ed = None
    for et in toks[town_idx + 1:leg_idx]:
        if et.isdigit():
            ed = et
            break
    if ed is None:
        ed = "1"  # 1-ED town whose CC row omitted the ED (Orange)
    return f"{town} {ed} Leg {leg}"


def reassemble(lines, n):
    """Parse one counting group's lines into {precinct: [n votes]} summing
    non-CC + CC rows, and return (precincts, subtotal, total) where subtotal
    is the [n votes] from the group's SUB-TOTAL row (what the precinct rows sum
    to) and total is the TOTAL row (subtotal + Cumulative). Either may be None."""
    precincts = defaultdict(lambda: [0] * n)
    group_total = None
    group_subtotal = None
    consumed = set()
    for i, raw in enumerate(lines):
        if i in consumed:
            continue
        line = raw.strip()
        if not line:
            continue
        tokens = line.split()
        head = tokens[0].upper() if tokens else ""
        # Totals/marker rows: capture SUB-TOTAL + TOTAL, skip Cumulative.
        if head == "TOTAL":
            ti = trailing_ints(tokens, n)
            if ti is not None:
                group_total = ti[1]
            consumed.add(i)
            continue
        if head in ("SUB-TOTAL", "SUBTOTAL"):
            ti = trailing_ints(tokens, n)
            if ti is not None:
                group_subtotal = ti[1]
            consumed.add(i)
            continue
        if head == "CUMULATIVE":
            consumed.add(i)
            continue
        # votes line?
        ti = trailing_ints(tokens, n)
        if ti is None:
            continue
        lead, votes = ti
        if lead and not starts_town_or_cc(lead):
            # e.g. "Schuyler County", candidate-header fragments, file paths --
            # ends with n ints by coincidence but isn't a precinct. (A real
            # joined precinct's lead starts with a town or 'CC'.)
            continue
        before = []
        if not lead:  # split case: name is on the adjacent lines
            if i - 1 >= 0 and (i - 1) not in consumed:
                btoks = lines[i - 1].strip().split()
                if btoks and starts_town_or_cc(btoks) and trailing_ints(btoks, n) is None:
                    before = btoks
                    consumed.add(i - 1)
        # after-line (Leg suffix) if the next line matches and isn't a votes line
        after = []
        if i + 1 < len(lines) and (i + 1) not in consumed:
            nxt = lines[i + 1].strip()
            ntoks = nxt.split()
            if (ntoks and not starts_town_or_cc(ntoks)
                    and trailing_ints(ntoks, n) is None
                    and AFTER_RE.match(nxt)):
                after = ntoks
                consumed.add(i + 1)
        name = normalize_precinct(before + lead + after)
        consumed.add(i)
        if name is None:
            continue
        cur = precincts[name]
        for k in range(n):
            cur[k] += votes[k]
    return precincts, group_subtotal, group_total


# Non-canonical (local) office headers -- when seen, stop collecting (the
# canonical contests all precede the local ones in this report). Matching any
# of these keywords resets cur_office so local-office rows never pollute the
# canonical buckets.
LOCAL_OFFICE_KEYS = (
    "Council Member", "Town of", "Justice", "Judge", "Clerk",
    "Superintendent", "Proposition", "Question", "Referendum",
    "Member of the County", "Ballot Question",
)

# Page artifacts that carry no precinct data but can land between a votes line
# and its Leg-suffix line when a precinct spans a page boundary (page header at
# the top of the next page, file-path footer at the bottom of the previous one).
# These would break after-line reassembly, so they are stripped from buckets.
NOISE_KEYS = ("Statement of Vote Cast", "file://", "file:", ".HTML",
              "vote for", "District type:")


def is_noise(line):
    return any(k in line for k in NOISE_KEYS)


def build_buckets(pdf):
    """Walk all pages' text in order, tracking office + counting group, and
    route each data line to bucket[(office, district, group)] = [lines]."""
    buckets = defaultdict(list)
    cur_office = None
    cur_district = None
    cur_group = None
    for page in pdf.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            od = detect_office(line)
            if od is not None:
                cur_office, cur_district = od
                cur_group = None  # office header precedes its first group line
                continue
            # A local/non-canonical office header ends canonical collection.
            if any(k in line for k in LOCAL_OFFICE_KEYS):
                cur_office = None
                cur_district = None
                cur_group = None
                continue
            if line.startswith("Counting group:"):
                cur_group = line.split(":", 1)[1].strip()
                continue
            if cur_office is None or cur_group is None:
                continue
            if (cur_office, cur_district) in OFFICES and not is_noise(line):
                buckets[(cur_office, cur_district, cur_group)].append(line)
    return buckets


def parse_table_rows(table, n):
    """Parse an extract_tables() table (with a header row whose col0 == 'ED')
    into (precincts, subtotal, total): {precinct: [n votes]} summing non-CC + CC
    rows, plus the SUB-TOTAL and TOTAL vectors. Assembly's "All" group fits on a
    single page as one clean table -- extract_text() is unreliable for Assembly
    (its CC rows carry an extra "Blank" column, so trailing_ints(N) drops a real
    vote), but extract_tables() gives a clean N-col grid with a header that names
    every column. This returns None for any vector not present."""
    precincts = defaultdict(lambda: [0] * n)
    subtotal = None
    total = None
    for r in table[1:]:  # row 0 is the header
        if not r:
            continue
        name = (r[0] or "").replace("\n", " ").strip()
        if not name:
            continue
        head = name.split()[0].upper()
        if head == "SCHUYLER":  # "Schuyler County" sub-header row
            continue
        if head in ("SUB-TOTAL", "SUBTOTAL"):
            if len(r) >= n + 1:
                subtotal = [_ci(r[j]) for j in range(1, n + 1)]
            continue
        if head == "TOTAL":
            if len(r) >= n + 1:
                total = [_ci(r[j]) for j in range(1, n + 1)]
            continue
        if head == "CUMULATIVE":
            continue
        if len(r) < n + 1:
            continue
        votes = [_ci(r[j]) for j in range(1, n + 1)]
        pname = normalize_precinct(name.split())
        if pname is None:
            continue
        cur = precincts[pname]
        for k in range(n):
            cur[k] += votes[k]
    return precincts, subtotal, total


def find_office_all_table(pdf, surname):
    """Find the FIRST extract_tables() table (in page order) whose header row
    (col0 == 'ED') contains `surname` -- the "All" counting group is always the
    first group printed for an office, so this is that office's "All" table.
    Returns (page_index, table) or (None, None). Used for Assembly, whose "All"
    group is a single clean page (no spanning)."""
    for i, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables:
            if not table or not table[0]:
                continue
            header = table[0]
            if (header[0] or "").strip() == "ED" and any(
                    surname in (c or "") for c in header):
                return i, table
    return None, None


def main():
    pdf = npdf.PDF(PDF_PATH)
    buckets = build_buckets(pdf)

    all_rows = []
    soft = []   # county-total mismatches (non-fatal unless we choose to fail)
    hard = []   # per-precinct self-consistency failures (fatal)
    groups_found = defaultdict(set)  # (office,district) -> {group names used}

    for od, cfg in OFFICES.items():
        office, district = od
        n = cfg["N"]
        if od == ("State Assembly", "132"):
            # Assembly's "All" group is a single clean extract_tables() page;
            # extract_text() is unreliable for Assembly (CC rows carry an extra
            # "Blank" column), so parse the table directly.
            pi, table = find_office_all_table(pdf, "Palmesano")
            if table is None:
                hard.append(f"{od}: no Assembly 'All' table found via extract_tables")
                continue
            groups_found[od].add("All (extract_tables p{})".format(pi + 1))
            precincts, subtotal, total = parse_table_rows(table, n)
            for name, votes in precincts.items():
                emit_and_check(office, district, cfg, name, votes, all_rows, hard)
            check_county(od, cfg, precincts, subtotal, total, "All", hard, soft)
        elif od in USES_ALL:
            lines = buckets.get((office, district, "All"), [])
            groups_found[od].add("All")
            if not lines:
                hard.append(f"{od}: no 'All' bucket found")
                continue
            precincts, subtotal, total = reassemble(lines, n)
            # per-precinct self-consistency + emission
            for name, votes in precincts.items():
                emit_and_check(office, district, cfg, name, votes, all_rows, hard)
            # county check vs All Sub-total (hard) + Cumulative gap (soft)
            check_county(od, cfg, precincts, subtotal, total, "All", hard, soft)
        else:
            # House 24: sum sub-groups (everything except "All")
            sub_groups = sorted(g for (o, d, g) in buckets
                                 if (o, d) == od and g != "All")
            groups_found[od].update(sub_groups)
            if not sub_groups:
                hard.append(f"{od}: no sub-group buckets found")
                continue
            agg = defaultdict(lambda: [0] * n)
            sub_subtotals = [0] * n
            sub_totals = [0] * n
            for g in sub_groups:
                lines = buckets[(office, district, g)]
                prec, subtotal, total = reassemble(lines, n)
                for name, votes in prec.items():
                    cur = agg[name]
                    for k in range(n):
                        cur[k] += votes[k]
                if subtotal:
                    for k in range(n):
                        sub_subtotals[k] += subtotal[k]
                if total:
                    for k in range(n):
                        sub_totals[k] += total[k]
            for name, votes in agg.items():
                emit_and_check(office, district, cfg, name, votes, all_rows, hard)
            check_county(od, cfg, agg, sub_subtotals, sub_totals,
                         "+".join(sub_groups), hard, soft)
            if not any(sub_subtotals):
                soft.append(f"{od}: no sub-group Sub-total rows found")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Schuyler", precinct, office, district, party, cand, votes])

    precincts = {r[4] for r in all_rows}
    offices = []
    for r in all_rows:
        od = (r[0], r[1])
        if od not in offices:
            offices.append(od)
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"office-districts={offices} -> {OUT_PATH}")
    print("Counting groups used per office:")
    for od, groups in sorted(groups_found.items()):
        print(f"  {od}: {sorted(groups)}")
    n_h = len(all_rows) - len(hard)  # rough; hard counts per-precinct failures
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:80]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 80:
            print(f"  ... and {len(hard) - 80} more", file=sys.stderr)
    if soft:
        print(f"--- {len(soft)} county-total mismatch(es) (non-fatal) ---",
              file=sys.stderr)
        for p in soft[:60]:
            print("  " + p, file=sys.stderr)
    if hard:
        return 1
    print(f"Verification OK: {len(hard)} hard failures, {len(soft)} county-total "
          f"mismatch(es).")
    return 0


def emit_and_check(office, district, cfg, name, votes, all_rows, hard):
    """Emit candidate + aggregate write-in rows for one precinct's vote vector,
    and run the per-precinct self-consistency check."""
    n = cfg["N"]
    if len(votes) != n:
        hard.append(f"{office}/{district} {name}: vote vector length "
                     f"{len(votes)} != {n}")
        return
    cand_cols = [c[0] for c in cfg["candidates"]]
    for col, party, cand in cfg["candidates"]:
        v = votes[col]
        if v > 0:
            all_rows.append((office, district, party, cand, name, v))
    wv = sum(votes[c] for c in cfg["writein_cols"])
    if wv > 0:
        all_rows.append((office, district, "", "Write-in", name, wv))
    # self-consistency: sum(cand cols) + sum(writein cols) == Total Votes
    s = sum(votes[c] for c in cand_cols) + wv
    tv = votes[cfg["tv"]]
    if s != tv:
        hard.append(f"{office}/{district} {name}: cand+writein({s}) "
                    f"!= TotalVotes({tv})")


def check_county(od, cfg, precincts, subtotal, total, label, hard, soft):
    """Compare each column's precinct-sum to the SUB-TOTAL vector (a HARD check:
    the precinct rows must sum to the group's Sub-total, or extraction is wrong),
    and report any centrally-counted write-in votes that live only in the
    Cumulative row (TOTAL - Sub-total) as a non-fatal source limitation -- those
    votes are real but not attributed to any precinct by the BOE, so they cannot
    appear in a per-precinct file (the committed 2024 NY corpus has no county-wide
    precinct rows)."""
    n = cfg["N"]
    sums = [0] * n
    for votes in precincts.values():
        for k in range(n):
            sums[k] += votes[k]
    if subtotal is not None:
        for k in range(n):
            if sums[k] != subtotal[k]:
                hard.append(f"{od} col{k}: precinct-sum={sums[k]} "
                            f"!= {label} Sub-total={subtotal[k]}")
    else:
        soft.append(f"{od}: no Sub-total row found for county check")
    if total is not None and subtotal is not None:
        for c in cfg["writein_cols"]:
            gap = total[c] - subtotal[c]
            if gap != 0:
                soft.append(f"{od} write-in col{c}: {gap} centrally-counted "
                             f"write-in vote(s) in Cumulative row not attributed "
                             f"to any precinct (source limitation; not emitted)")


if __name__ == "__main__":
    sys.exit(main())