#!/usr/bin/env python3
"""Dedicated parser for Albany County 2024 general precinct PDF (NaturalPDF).

The Albany SOVC PDF (1173 pages, 234 precincts) is a clean text-based layout.
Each precinct spans 5 pages; the precinct name is the 4th line of every page
(after a 3-line "Albany County OFFICIAL RESULTS / General Election 2024 /
November 5, 2024" boilerplate header), and each page may stack MORE THAN ONE
contest. A contest block looks like:

  <office title>
  Vote For N
  TOTAL VOTE % Election Early Absentee
  Day Voting
  DEM <name> <total> <%> <edday> <early> <absentee>   <- party-line rows
  REP <name> <total> <%> ...
  ...
  Totals by Candidate
  <name> <total> <%> ...                              <- candidate totals (skip)
  Write-In: <name> <total> <%> ...                   <- named write-ins
  Write-In Totals <total> <%> ...                     <- skip (aggregate)
  Not Assigned ... / Total Votes Cast ... / Overvotes ... / Undervotes ...
  Contest Totals ...

This parser keeps the five state/federal offices (President, U.S. Senate,
U.S. House, State Senate, State Assembly), maps WFP -> WOR and LAR -> LAR,
keeps individual named write-in rows with votes>0 (candidate=name, party=""),
and OMITS all 0-vote rows, Write-In Totals, and contest totals (Totals by
Candidate, Not Assigned, Total Votes Cast, Overvotes, Undervotes, Contest
Totals, Statistics/Ballots Cast).

Parsing is page-by-page (not by fixed page range), so it naturally handles the
multi-contest pages and the 43rd/46th State Senate split. Each kept contest is
verified: sum(party-line votes) + sum(named write-in votes) must equal the
contest's "Total Votes Cast" row, and sum(party lines per candidate) must equal
that candidate's "Totals by Candidate" row.

Standalone (precedent: cattaraugus_2024_parse.py) -- zero regression risk to
the shared ny2024_rpp_parser.py and the committed counties. Run with uv so the
natural_pdf dependency (>=3.12) is available:  uv run python albany_2024_parse.py
"""
import os
import sys
import re
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "ALBANY_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Albany.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__albany__precinct.csv"
)

# Canonical offices to keep. Each entry: (title_regex, office, district_template)
# where district_template is "" for fixed-district offices or None to extract the
# ordinal district number from the title.
OFFICE_RULES = [
    (re.compile(r"^Electors for President and Vice President$"), "President", ""),
    (re.compile(r"^United States Senator$"), "U.S. Senate", ""),
    (re.compile(r"^Representative in Congress (\d+)(?:st|nd|rd|th)? District$"),
     "U.S. House", None),
    (re.compile(r"^State Senator (\d+)(?:st|nd|rd|th)? District$"),
     "State Senate", None),
    (re.compile(r"^Member of Assembly (\d+)(?:st|nd|rd|th)? District$"),
     "State Assembly", None),
]

# Party-code map for party-line rows. Working Families prints "WFP" in this PDF
# but the committed 2024 NY convention (and the #148-branch counties) is "WOR";
# LaRouche prints "LAR" and stays "LAR". DEM/REP/CON pass through.
PARTY_MAP = {
    "DEM": "DEM", "REP": "REP", "WFP": "WOR", "CON": "CON", "LAR": "LAR",
    "IND": "IND", "GRE": "GRE", "LIB": "LIB", "SAM": "SAM", "CMN": "CMN",
    "WOR": "WOR",
}
_PARTY_ALT = "|".join(PARTY_MAP.keys())

# Vote counts may be comma-grouped thousands ("1,053") in larger precincts, so
# the integer patterns accept comma-separated digits and _i() strips the commas.
_NUM = r"[\d,]+"


def _i(s):
    return int(s.replace(",", ""))


# A party-line row: "<CODE> <Candidate Name> <total> <pct%> <ed> <early> <absentee>"
# The total is the first integer after the candidate name (immediately before the
# percentage). Candidate names may contain periods, commas, and suffixes
# ("Ted Danz, Jr.", "P. David Soares", "Jasper Mills, III"), but no standalone
# integer tokens, so the non-greedy name + "<num> ... %" anchor is unambiguous.
PARTY_ROW = re.compile(
    rf"^(?P<party>{_PARTY_ALT})\s+(?P<name>.+?)\s+(?P<votes>{_NUM})\s+\d+\.\d+%"
)

# An individual named write-in: "Write-In: <name> <total> <pct%> ..."
WRITEIN_ROW = re.compile(rf"^Write-In:\s+(?P<name>.+?)\s+(?P<votes>{_NUM})\s+\d+\.\d+%")

# "Totals by Candidate" -- after this, name+number rows are per-candidate totals
# (skip), but "Write-In:" rows still follow and must be captured.
TOTALS_BY_CAND = "Totals by Candidate"

# "Total Votes Cast <N> 100.00% ..." -- the contest's valid-vote total. It equals
# kept party-line votes + named write-in votes + "Not Assigned" (votes cast but
# not assigned to any candidate), so verification is kept + not_assigned == TVC.
TOTAL_VOTES_CAST = re.compile(rf"^Total Votes Cast\s+(?P<votes>{_NUM})\s+100\.00%")
NOT_ASSIGNED = re.compile(rf"^Not Assigned\s+(?P<votes>{_NUM})\s+\d+\.\d+%")

# A candidate-total row: "<Candidate Name> <total> <pct%> <ed> <early> <absentee>"
# (no party code). Used only for verification: sum of that candidate's party
# lines must equal it. Trailing ed/early/absentee follow the %, so no end anchor.
CAND_TOTAL = re.compile(rf"^(?P<name>.+?)\s+(?P<votes>{_NUM})\s+\d+\.\d+%")

# Lines that begin a non-row / non-contest line we always skip.
SKIP_PREFIXES = (
    "Vote For", "TOTAL VOTE", "Day Voting", "Write-In Totals", "Not Assigned",
    "Overvotes", "Undervotes", "Contest Totals", "Ballots Cast", "Statistics",
    "Precinct Summary",
)


def classify_office(title):
    """Map a raw office-title line to (office, district) or None if not kept."""
    for rx, office, tmpl in OFFICE_RULES:
        m = rx.match(title)
        if m:
            district = tmpl if tmpl is not None else m.group(1)
            return office, district
    return None


def precinct_of(lines):
    """Precinct name = first non-empty line after the 'November 5, 2024' header
    line. Falls back to line index 3 (the 4th line) if the header isn't found."""
    for i, l in enumerate(lines):
        if "November 5, 2024" in l:
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    return lines[j].strip()
            break
    return lines[3].strip() if len(lines) > 3 else ""


def parse_page(text):
    """Yield (office, district, party, candidate, votes) rows for one page, plus
    collect verification data. Returns (rows, totals_cast, cand_totals) where
    totals_cast is {(office,district): int} and cand_totals is
    {(office,district,name): int}."""
    lines = text.splitlines()
    precinct = precinct_of(lines)
    rows = []
    totals_cast = {}
    cand_totals = {}
    not_assigned = {}

    office = None
    district = None
    past_cand_totals = False

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("Precinct Summary"):
            break  # page footer

        # New contest?
        cls = classify_office(s)
        if cls is not None:
            office, district = cls
            past_cand_totals = False
            continue
        if office is None:
            continue  # header / Statistics / a non-kept contest

        if s == TOTALS_BY_CAND:
            past_cand_totals = True
            continue
        # "Not Assigned" is parsed below for verification, so don't skip it here.
        if any(s.startswith(p) for p in SKIP_PREFIXES) and not s.startswith("Not Assigned"):
            continue

        # Named write-in (captured regardless of past_cand_totals, since
        # write-ins follow the candidate-total rows).
        wm = WRITEIN_ROW.match(s)
        if wm:
            votes = _i(wm.group("votes"))
            if votes > 0:
                rows.append((office, district, "", wm.group("name").strip(), votes))
            continue

        # Party-line row (only before "Totals by Candidate"; candidate-total rows
        # that follow it have no party-code prefix so they cannot match).
        if not past_cand_totals:
            pm = PARTY_ROW.match(s)
            if pm:
                votes = _i(pm.group("votes"))
                if votes > 0:
                    party = PARTY_MAP[pm.group("party")]
                    rows.append((office, district, party, pm.group("name").strip(),
                                votes))
                continue

        # Verification: Total Votes Cast for this contest.
        tvm = TOTAL_VOTES_CAST.match(s)
        if tvm:
            totals_cast[(office, district)] = _i(tvm.group("votes"))
            continue

        # Verification: Not Assigned votes for this contest.
        nam = NOT_ASSIGNED.match(s)
        if nam:
            not_assigned[(office, district)] = _i(nam.group("votes"))
            continue

        # Verification: per-candidate total (only after "Totals by Candidate").
        if past_cand_totals:
            cm = CAND_TOTAL.match(s)
            if cm:
                cand_totals[(office, district, cm.group("name").strip())] = \
                    _i(cm.group("votes"))
            # else: skip (Overvotes/Undervotes/etc. already handled by prefixes,
            # but any remaining name+number line is a candidate total we skip)

    return precinct, rows, totals_cast, cand_totals, not_assigned


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []          # (precinct, office, district, party, candidate, votes)
    totals_cast = {}       # {(precinct, office, district): int}
    cand_totals = {}       # {(precinct, office, district, name): int}
    not_assigned = {}      # {(precinct, office, district): int}

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        precinct, rows, tc, ct, na = parse_page(text)
        if not precinct:
            continue
        for office, district, party, cand, votes in rows:
            all_rows.append((precinct, office, district, party, cand, votes))
        for k, v in tc.items():
            totals_cast[(precinct,) + k] = v
        for k, v in ct.items():
            cand_totals[(precinct,) + k] = v
        for k, v in na.items():
            not_assigned[(precinct,) + k] = v

    # ---- Verification -------------------------------------------------------
    problems = []

    # 1. kept party-line + named-write-in votes + Not Assigned must equal the
    #    contest's "Total Votes Cast" (Not Assigned = votes cast but not assigned
    #    to any candidate, not a row we emit).
    sums = {}
    for precinct, office, district, party, cand, votes in all_rows:
        k = (precinct, office, district)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in totals_cast.items():
        sv = sums.get(k, 0) + not_assigned.get(k, 0)
        if sv != tv:
            problems.append(f"Total Votes Cast mismatch {k}: kept+NA={sv} pdf={tv}")
    for k in sorted(set(sums) - set(totals_cast)):
        problems.append(f"{k}: kept votes but no Total Votes Cast row found")

    # 2. per-candidate: sum of that candidate's party-line votes must equal the
    #    "Totals by Candidate" row. Write-ins are individual named rows here (not
    #    aggregated), so they are not checked against cand_totals.
    per_cand = {}
    for precinct, office, district, party, cand, votes in all_rows:
        if party == "":
            continue  # write-in, not in cand_totals
        k = (precinct, office, district, cand)
        per_cand[k] = per_cand.get(k, 0) + votes
    for k, tv in cand_totals.items():
        sv = per_cand.get(k, 0)
        if sv != tv:
            problems.append(f"candidate total mismatch {k}: party-sum={sv} pdf={tv}")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for precinct, office, district, party, cand, votes in all_rows:
            w.writerow(["Albany", precinct, office, district, party, cand, votes])

    precincts = {r[0] for r in all_rows}
    offices = []
    for r in all_rows:
        if r[1] not in offices:
            offices.append(r[1])
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"offices={offices} -> {OUT_PATH}")
    if problems:
        print(f"=== {len(problems)} VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in problems[:50]:
            print("  " + p, file=sys.stderr)
        if len(problems) > 50:
            print(f"  ... and {len(problems) - 50} more", file=sys.stderr)
        return 1
    print(f"Verification OK: {len(sums)} (precinct,office) totals == Total Votes "
          f"Cast (incl. Not Assigned); {len(per_cand)} candidate sums == Totals "
          f"by Candidate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())