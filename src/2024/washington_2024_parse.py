#!/usr/bin/env python3
"""Dedicated parser for Washington County 2024 general precinct PDF (NaturalPDF).

The Washington County BOE "Precinct Results Report - Official Results" PDF
(625 pages) is a clean, upright SOVC the shared ny2024_rpp_parser.py was
listed as unable to open -- but NaturalPDF's extract_text() reads it cleanly.
This is a PER-CANDIDATE (not per-party-line) report: each candidate row carries
ONE combined vote total across all of that candidate's fusion party lines, with
the party cell reading e.g. "DEM, WOR" (Harris) or "REP, CON" (Trump). The
official county summary
(https://www.washingtoncountyny.gov/DocumentCenter/View/27849/GE24-Election-Results-Summary)
confirms this: Trump (Republican, Conservative) = 17,268 and Harris (Democratic,
Working Families) = 11,224 as single combined numbers. There is NO DEM/WOR or
REP/CON split available at any level.

Per the #148-branch convention decision for this county, fusion candidates are
emitted as ONE row on their PRIMARY ballot line (DEM for Harris/Gillibrand/
Collins/Gamble/Woerner/Pierce; REP for Trump/Sapraicone/Stefanik/Ashby/Stec/
Bendett/Messina/Simpson; LAR for Sare), votes = the combined grand total. The
WOR/CON sub-lines carry no separate votes in the source and are dropped.
Candidate grand-totals are exactly correct; party-line sums are not separable
for Washington (a known source limitation). DEM-only / LAR-only candidates are
unaffected.

Each of the 50 precincts is printed in THREE sections:
  * regular  "<Town> [District N]  <TT> of <RV> registered voters = ..."  (Early + Affidavit + Election Day; the "Absentee Voting" column is always 0 here)
  * "<Town> [District N] - ABS      ..."                                    (absentee ballots)
  * "<Town> [District N] - Fed ABS   ..."                                   (federal/UOCAVA absentee; usually all-zero)
The grand total per candidate per precinct = regular Total + ABS Total + Fed-ABS Total. Each
section's choice rows have columns: Absentee / Early / Affidavit / Election Day / Total
(each as "count pct%"); the candidate's section total = the 5th (last) count.

Candidate names wrap across lines (e.g. "Kirsten E. DEM, 0 0.00% ... 192
34.41%" then "Gillibrand WOR"), and the VP running-mate prints on a no-votes
continuation line ("Tim Walz WOR", "JD Vance CON"). The vote line always carries
the FIRST/primary party + the 5 count/pct pairs; continuation lines have no
percentages. Candidate full names resolve from (office, district, primary_party)
via a hardcoded CAND map (matches the committed 2024 NY corpus), so the wrapped
names are not relied on.

Write-ins: every write-in line is marked "(W)" -- named write-in candidates
(Chase Oliver, Jill Stein, ...), "Scattering (W)", and "Void (W)". Per the
#148 convention, the valid write-ins (named + Scattering) are aggregated into
one "Write-in" row (party empty) when >0. "Void (W)" is an invalid-write-in
category (the official summary lists "Void 130" separately) -- EXCLUDED from the
Write-in aggregate, like Overvotes/Undervotes. 0-vote rows are omitted
throughout.

Canonical offices (Washington is SPLIT across SD-43/45 and AD-107/113/114;
each precinct is in exactly one of each):
  President             (statewide)            DEM/REP -- Harris / Trump
  U.S. Senate           (statewide)            DEM/REP/LAR -- Gillibrand / Sapraicone / Sare
  U.S. House 21         (statewide)            DEM/REP -- Collins / Stefanik
  State Senate 43       (SD-43)                DEM/REP -- Gamble / Ashby
  State Senate 45       (SD-45)                REP -- Stec (uncontested)
  State Assembly 107    (AD-107)               DEM/REP -- Pierce / Bendett
  State Assembly 113    (AD-113)               DEM/REP -- Woerner / Messina
  State Assembly 114    (AD-114)               REP -- Simpson (uncontested)
County Judge, town/village offices, and propositions are non-canonical -- skipped.

Precinct names normalize to match the committed 2022 Washington file:
"Argyle District 1" -> "Argyle 1"; single-district towns ("Dresden", "Hebron",
"Jackson", "Hampton", "Putnam") -> "Dresden 1" etc. county = "Washington".

Verification:
  PRIMARY (hard): per (section, office) self-consistency -- sum of every choice
    row's Total (named candidates + all write-ins incl. Void) == that section's
    "Cast Votes" total. This validates extraction of every number.
  SECONDARY (hard): county-wide grand totals per candidate == the official
    county summary (President: Harris 11,224 / Trump 17,268; valid write-ins 94;
    Void 130). Other offices' county totals are printed and checked against the
    NY BOE / county summary anchors embedded below.
Run with uv (natural_pdf needs Python >=3.12):  uv run python washington_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "WASHINGTON_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Washington.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__washington__precinct.csv"
)
COUNTY = "Washington"

# (office, district, primary_party) -> full canonical candidate name. The primary
# party is the one printed on the candidate's vote line (DEM, REP, or LAR); the
# fusion partner (WOR/CON) prints on a no-votes continuation line and is folded
# into the combined total on the primary line.
CAND = {
    ("President", "", "DEM"): "Kamala D. Harris",
    ("President", "", "REP"): "Donald J. Trump",
    ("U.S. Senate", "", "DEM"): "Kirsten E. Gillibrand",
    ("U.S. Senate", "", "REP"): "Michael D. Sapraicone",
    ("U.S. Senate", "", "LAR"): "Diane Sare",
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("State Senate", "43", "DEM"): "Alvin Gamble",
    ("State Senate", "43", "REP"): "Jake Ashby",
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Assembly", "107", "DEM"): "Chloe E. Pierce",
    ("State Assembly", "107", "REP"): "Scott H. Bendett",
    ("State Assembly", "113", "DEM"): "Carrie Woerner",
    ("State Assembly", "113", "REP"): "Jeremy Messina",
    ("State Assembly", "114", "REP"): "Matthew J. Simpson",
}

# (substring of upright office title, office, district). Only these are emitted.
CANON_OFFICES = [
    ("electors for president", "President", ""),
    ("united states senator", "U.S. Senate", ""),
    ("representative in congress 21st", "U.S. House", "21"),
    ("state senator 43rd", "State Senate", "43"),
    ("state senator 45th", "State Senate", "45"),
    ("member of assembly 107th", "State Assembly", "107"),
    ("member of assembly 113th", "State Assembly", "113"),
    ("member of assembly 114th", "State Assembly", "114"),
]
OFFICE_RANK = {(o, d): i for i, (_, o, d) in enumerate(CANON_OFFICES)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}
PARTY_CODES = set(PARTY_RANK)

# Official county-wide anchors (from the Washington County 2024 election-results
# summary + NY BOE), used for the SECONDARY hard check. (office, district, party)
# -> candidate grand total; "_WI" -> valid write-in total (excl Void); "_VOID".
# Every office-district is anchored: candidate grand totals + valid write-in
# totals (named write-ins + Scattering, excluding Void) all verified equal to
# the official cumulative report.
ANCHORS = {
    ("President", "", "DEM"): 11224,
    ("President", "", "REP"): 17268,
    ("President", "", "_WI"): 94,
    ("President", "", "_VOID"): 130,
    ("U.S. Senate", "", "DEM"): 12539,
    ("U.S. Senate", "", "REP"): 15221,
    ("U.S. Senate", "", "LAR"): 132,
    ("U.S. Senate", "", "_WI"): 19,
    ("U.S. House", "21", "DEM"): 10500,
    ("U.S. House", "21", "REP"): 17623,
    ("U.S. House", "21", "_WI"): 20,
    ("State Senate", "43", "DEM"): 6375,
    ("State Senate", "43", "REP"): 11860,
    ("State Senate", "43", "_WI"): 8,
    ("State Senate", "45", "REP"): 7598,
    ("State Senate", "45", "_WI"): 52,
    ("State Assembly", "107", "DEM"): 1674,
    ("State Assembly", "107", "REP"): 2324,
    ("State Assembly", "107", "_WI"): 4,
    ("State Assembly", "113", "DEM"): 3877,
    ("State Assembly", "113", "REP"): 3865,
    ("State Assembly", "113", "_WI"): 2,
    ("State Assembly", "114", "REP"): 12571,
    ("State Assembly", "114", "_WI"): 88,
}

HEADER_RE = re.compile(r"^(.+?) (\d[\d,]+) of (\d[\d,]+) registered voters =")
PAIR_RE = re.compile(r"(\d[\d,]*)\s+\d+\.\d+%")


def _ci(tok):
    s = (tok or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def office_of(title):
    """Return (office, district) for a canonical office title line.
    Return None for a non-canonical office that still carries 'Vote for one'
    (County Judge, town offices, etc.) -- the caller uses this to STOP
    accumulating choice rows under the previous canonical office. Returns None
    for non-title lines too; use is_vote_for_one() to tell the two apart."""
    low = title.lower()
    if "vote for one" not in low:
        return None
    for sub, o, d in CANON_OFFICES:
        if sub in low:
            return (o, d)
    return None


def is_vote_for_one(title):
    return "vote for one" in title.lower()


def normalize_precinct(raw):
    """'Argyle District 1' -> 'Argyle 1'; 'Argyle District 1 - ABS' -> 'Argyle 1';
    'Dresden' / 'Dresden - Fed ABS' -> 'Dresden 1'. Matches the 2022 file."""
    s = raw.strip()
    s = re.sub(r"\s*-\s*(Fed ABS|ABS)\s*$", "", s)
    m = re.match(r"^(.+?) District (\d+)$", s)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    # single-district town (Dresden, Hebron, Jackson, Hampton, Putnam) -> "Town 1"
    return f"{s} 1"


def parse():
    pdf = npdf.PDF(PDF_PATH)
    cand = {}      # (precinct, office, district, party) -> combined grand total
    wi = {}        # (precinct, office, district) -> valid write-in total (excl Void)
    void = {}      # (precinct, office, district) -> Void total
    sec_choices = {}  # (precinct_raw, office, district) -> [choice Totals]
    sec_cast = {}     # (precinct_raw, office, district) -> Cast Votes total
    unknown = {}   # (office, district, party) -> count of unmapped choice rows
    prec_order = []   # normalized precincts in first-seen order
    seen_prec = set()

    cur_prec_raw = None
    cur_od = None
    for page in pdf.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            hm = HEADER_RE.match(line)
            if hm:
                cur_prec_raw = hm.group(1).strip()
                norm = normalize_precinct(cur_prec_raw)
                if norm not in seen_prec:
                    seen_prec.add(norm)
                    prec_order.append(norm)
                continue
            od = office_of(line)
            if is_vote_for_one(line):
                # A vote-for-one title: set the canonical office, or clear it so
                # that a following non-canonical office's choice rows are skipped
                # (they must NOT be attributed to the previous canonical office).
                cur_od = od
                continue
            if cur_prec_raw is None or cur_od is None:
                continue
            office, district = cur_od
            low = line.lower()
            if low.startswith("cast votes:"):
                pairs = PAIR_RE.findall(line)
                if len(pairs) == 5:
                    key = (cur_prec_raw, office, district)
                    sec_cast[key] = sec_cast.get(key, 0) + _ci(pairs[-1])
                continue
            if low.startswith("undervotes") or low.startswith("overvotes"):
                continue
            # candidate / write-in choice row: exactly 5 "count pct%" pairs.
            pairs = PAIR_RE.findall(line)
            if len(pairs) != 5:
                continue
            total = _ci(pairs[-1])
            sec_key = (cur_prec_raw, office, district)
            sec_choices.setdefault(sec_key, []).append(total)
            norm = normalize_precinct(cur_prec_raw)
            nkey = (norm, office, district)
            # primary party = first token (stripped of punctuation) that is a party code
            party = None
            for t in line.split():
                u = re.sub(r"[^A-Za-z]", "", t)
                if u in PARTY_CODES:
                    party = u
                    break
            if party is not None and (office, district, party) in CAND:
                k = (norm, office, district, party)
                cand[k] = cand.get(k, 0) + total
            elif "(W)" in line or "( W )" in line:
                if "void" in low:
                    void[nkey] = void.get(nkey, 0) + total
                else:
                    wi[nkey] = wi.get(nkey, 0) + total
            elif party is not None:
                # a named party-line row we don't have a CAND entry for -> flag it
                unknown[(office, district, party)] = unknown.get((office, district, party), 0) + 1
            # else: a write-in without an explicit "(W)" marker (rare); treat as
            # write-in so its votes are not silently lost.
            elif total > 0:
                wi[nkey] = wi.get(nkey, 0) + total
    return cand, wi, void, sec_choices, sec_cast, unknown, prec_order


def main():
    cand, wi, void, sec_choices, sec_cast, unknown, prec_order = parse()

    # ---- PRIMARY hard check: per (section, office) sum(choices) == Cast Votes ---
    hard = []
    for key, tot in sec_cast.items():
        choices = sec_choices.get(key, [])
        s = sum(choices)
        if s != tot:
            hard.append(f"{key}: sum(choices)={s} != Cast Votes={tot} "
                        f"(diff {s - tot})")
    for key in set(sec_choices) - set(sec_cast):
        hard.append(f"{key}: choice rows but no Cast Votes line found")

    # ---- SECONDARY hard check: county-wide grand totals vs anchors ------------
    county = {}       # (office, district, party) -> sum
    county_wi = {}    # (office, district) -> write-in sum
    county_void = {}  # (office, district) -> void sum
    for (norm, office, district, party), v in cand.items():
        county[(office, district, party)] = county.get((office, district, party), 0) + v
    for (norm, office, district), v in wi.items():
        county_wi[(office, district)] = county_wi.get((office, district), 0) + v
    for (norm, office, district), v in void.items():
        county_void[(office, district)] = county_void.get((office, district), 0) + v

    for (office, district, party), av in ANCHORS.items():
        if party == "_WI":
            sv = county_wi.get((office, district), 0)
            if sv != av:
                hard.append(f"{office}/{district} write-in: county={sv} != anchor={av}")
        elif party == "_VOID":
            sv = county_void.get((office, district), 0)
            if sv != av:
                hard.append(f"{office}/{district} void: county={sv} != anchor={av}")
        else:
            sv = county.get((office, district, party), 0)
            if sv != av:
                hard.append(f"{office}/{district} {party}: county={sv} != anchor={av}")

    # ---- Write CSV ----------------------------------------------------------
    rows = []
    for (norm, office, district, party), v in cand.items():
        if v > 0:
            rows.append((norm, office, district, party,
                         CAND[(office, district, party)], v))
    for (norm, office, district), v in wi.items():
        if v > 0:
            rows.append((norm, office, district, "", "Write-in", v))
    rows.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order else 999,
                             OFFICE_RANK.get((r[1], r[2]), 99),
                             PARTY_RANK.get(r[3], 9), r[4]))

    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for norm, office, district, party, cand_name, v in rows:
            w.writerow([COUNTY, norm, office, district, party, cand_name, v])

    # ---- Report -------------------------------------------------------------
    precincts = {r[0] for r in rows}
    offices = []
    for r in rows:
        od = (r[1], r[2])
        if od not in offices:
            offices.append(od)
    print(f"Wrote {len(rows)} rows, {len(precincts)} precincts, "
          f"office-districts={offices} -> {OUT_PATH}")
    n_sec = len(sec_cast)
    n_sec_ok = n_sec - len([h for h in hard if "Cast Votes" in h or "no Cast Votes" in h])
    print(f"Self-consistency: {n_sec_ok}/{n_sec} (section,office) blocks satisfy "
          f"sum(choices) == Cast Votes.")
    print("County-wide grand totals:")
    for od in OFFICE_RANK:
        o, d = od
        parts = []
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (o, d, p) in county:
                parts.append(f"{p}={county[(o, d, p)]}")
        wv = county_wi.get(od, 0)
        vv = county_void.get(od, 0)
        parts.append(f"WI={wv}")
        if vv:
            parts.append(f"Void={vv}")
        print(f"  {o} {d}: {', '.join(parts)}")
    if unknown:
        print(f"--- {len(unknown)} unmapped party-line row type(s) ---", file=sys.stderr)
        for k, c in sorted(unknown.items()):
            print(f"  {k}: {c} row(s)", file=sys.stderr)
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
        return 1
    print(f"Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())