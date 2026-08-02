#!/usr/bin/env python3
"""Dedicated parser for St. Lawrence County 2024 general precinct PDF (NaturalPDF).

The St. Lawrence BOE "General Election November 5, 2024" PDF (74 pages) is a
rotated-text SOVC the shared ny2024_rpp_parser.py cannot open. Candidate names
are printed rotated/vertical, so extract_text() garbles them ("Ka mala D.
Harris", "Kirsten E. Gillibra T n"); BUT the precinct DATA rows extract cleanly,
and a second upright header row carries the party codes (DEM/REP/CON/WOR[/LAR])
-- that party-code row + a hardcoded CAND map is all the candidate mapping needs
(the rotated names are not relied on). The office TITLE is upright, so
offices/districts are read from it.

Layout (per office, paginated alphabetically by town, one table per page):
  row0   rotated office + candidate-name fragments  (garbled)
  row1   ''  DEM  REP  CON  WOR  [LAR]  ''  ...        <- upright party codes
  row2+  precinct rows:
         <Town> <ED> <TotalTurnout> <VoterReg> <%Turnout>
              <cand1> <cand2> ... <candN>      <- one col per party line (N)
              <CandidateTotal> ...            <- one col per fusion candidate
              <Write-in> <TotalVotesCast>

So after the '%' turnout token, a precinct row carries N candidate columns (in
party-code order), then a candidate-total column for each fusion candidate, then
the aggregate Write-in, then Total Votes Cast. The candidate columns are always
the FIRST N tokens after '%'; Write-in and Total Votes Cast are always the LAST
two. The candidate totals in between are not needed for emission (only for the
source's own layout). T = (#tokens-after-%) - N - 2 is derivable per row, so no
hardcoded column count is needed -- the party list alone fixes N.

Candidate votes = the party-line column (a single number -- no machine/absentee
sub-split here, unlike Herkimer). Candidate full names resolve from
(office, district, party) via a hardcoded CAND map matching the committed 2024 NY
corpus (and the 2022 St. Lawrence file). Fusion party lines are SEPARATE rows
(same candidate, different party). WOR = Working Families (#148-branch
convention -- NOT WFP/WF); LAR = LaRouche.

Canonical offices (district from the upright office title):
  President            (p1-5)   DEM/REP/CON/WOR -- Harris / Trump
  U.S. Senate          (p6-10)  DEM/REP/CON/WOR/LAR -- Gillibrand / Sapraicone / Sare
  U.S. House 21        (p11-15) DEM/REP/CON/WOR -- Paula Collins / Elise M. Stefanik
  State Senate 45      (p16-19) REP/CON -- Daniel G. Stec (uncontested fusion)
  State Senate 49      (p20-21) REP/CON -- Mark C. Walczyk
  State Assembly 116   (p22-24) REP/CON -- Scott A. Gray
  State Assembly 117   (p25-26) REP/CON -- Kenneth Blankenbush
St. Lawrence is SPLIT across SD-45 / SD-49 and AD-116 / AD-117 (each precinct is
in exactly one of each); the two single-candidate races (REP+CON fusion for the
same candidate) carry only 2 party columns. Pages 27+ (Family Court Judge,
Treasurer, town/city/village offices, Propositions) are non-canonical -- skipped.

Precinct names are "Town ED" (e.g. "Brasher 1", "Ogdensburg 3") -- exactly the
format used by the committed 2022 St. Lawrence file, so no normalization is
applied. Write-ins: the aggregate Write-in column is emitted as a single
"Write-in" row (party empty) when >0. 0-vote rows are omitted throughout.

Verification: the PRIMARY (hard) check is per-precinct self-consistency --
sum(candidate cols) + Write-in == Total Votes Cast (independent of any totals
row). The SECONDARY (hard) check compares each party-line column's precinct-sum
(and the write-in sum) to the office's "TOTAL" row printed on the last page.
Run with uv (natural_pdf needs Python >=3.12):  uv run python st_lawrence_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "ST_LAWRENCE_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/St Lawrence.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__st_lawrence__precinct.csv"
)
COUNTY = "St. Lawrence"

# (office, district, party) -> full canonical candidate name (matches the
# committed 2024 NY counties + the 2022 St. Lawrence file).
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
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Senate", "45", "CON"): "Daniel G. Stec",
    ("State Senate", "49", "REP"): "Mark C. Walczyk",
    ("State Senate", "49", "CON"): "Mark C. Walczyk",
    ("State Assembly", "116", "REP"): "Scott A. Gray",
    ("State Assembly", "116", "CON"): "Scott A. Gray",
    ("State Assembly", "117", "REP"): "Kenneth Blankenbush",
    ("State Assembly", "117", "CON"): "Kenneth Blankenbush",
}

# Per office-district: (start_page, end_page) 1-indexed, [party codes in column
# order]. Page ranges verified from the upright office-title lines.
OFFICES = [
    ("President", "", 1, 5, ["DEM", "REP", "CON", "WOR"]),
    ("U.S. Senate", "", 6, 10, ["DEM", "REP", "CON", "WOR", "LAR"]),
    ("U.S. House", "21", 11, 15, ["DEM", "REP", "CON", "WOR"]),
    ("State Senate", "45", 16, 19, ["REP", "CON"]),
    ("State Senate", "49", 20, 21, ["REP", "CON"]),
    ("State Assembly", "116", 22, 24, ["REP", "CON"]),
    ("State Assembly", "117", 25, 26, ["REP", "CON"]),
]


def _ci(tok):
    """Coerce a comma-grouped token ('1,086') to int, 0 on non-numeric."""
    s = (tok or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _is_num(tok):
    s = (tok or "").replace(",", "").strip()
    return s.isdigit()


PCT_RE = re.compile(r"\d+%")


def parse_row(line, n):
    """Parse one precinct/TOTAL data line. Returns (precinct, cand[N], writein,
    tvc) or None. Structure: <precinct...> <TT> <VR> <%pct> <cand*N> <totals*>
    <writein> <tvc>. precinct = tokens before the two turnout numbers that
    precede the '%'; cand = the first N tokens after '%'; writein/tvc = last 2."""
    toks = line.split()
    # locate the '% turnout' token
    pct_idx = None
    for i, t in enumerate(toks):
        if t.endswith("%") and re.match(r"^\d+%$", t):
            pct_idx = i
            break
    if pct_idx is None or pct_idx < 3:
        return None
    # the two tokens immediately before '%' are TotalTurnout and VoterReg
    if not (_is_num(toks[pct_idx - 2]) and _is_num(toks[pct_idx - 1])):
        return None
    precinct_toks = toks[:pct_idx - 2]
    if not precinct_toks or not precinct_toks[0][:1].isalpha():
        return None
    after = toks[pct_idx + 1:]
    if len(after) < n + 2:
        return None
    cand = after[:n]
    if not all(_is_num(c) for c in cand):
        return None
    if not (_is_num(after[-2]) and _is_num(after[-1])):
        return None
    precinct = " ".join(precinct_toks)
    return (precinct,
            [_ci(c) for c in cand],
            _ci(after[-2]),
            _ci(after[-1]))


def parse_office(pdf, office, district, p_start, p_end, parties):
    """Parse one office's pages. Returns (rows, county_total, selfcheck) where
    rows = [(office,district,party,candidate,precinct,votes)], county_total =
    {party: col_sum, 'WI': writein_sum} from the TOTAL row (for verification),
    selfcheck = [(precinct, cand_sum, writein, tvc)]."""
    n = len(parties)
    rows = []
    county_total = None
    selfcheck = []
    for p in range(p_start, p_end + 1):
        text = pdf.pages[p - 1].extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            toks = line.split()
            is_total = toks and toks[0].upper() == "TOTAL"
            parsed = parse_row(line, n)
            if parsed is None:
                continue
            precinct, cand, writein, tvc = parsed
            if is_total:
                # the office's grand-total row (one per office, last page)
                county_total = dict(zip(parties, cand))
                county_total["WI"] = writein
                continue
            # emit candidate party-line rows
            for i, party in enumerate(parties):
                v = cand[i]
                if v > 0:
                    cand_name = CAND.get((office, district, party))
                    if cand_name:
                        rows.append((office, district, party, cand_name,
                                     precinct, v))
            if writein > 0:
                rows.append((office, district, "", "Write-in", precinct, writein))
            selfcheck.append((precinct, sum(cand), writein, tvc))
    return rows, county_total, selfcheck


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    county_totals = {}   # (office,district) -> {party:sum, 'WI':sum}
    selfcheck = []       # (office,district,precinct,cand_sum,writein,tvc)
    offices_seen = []

    for office, district, p_start, p_end, parties in OFFICES:
        rows, ctotal, sc = parse_office(
            pdf, office, district, p_start, p_end, parties)
        if not rows and ctotal is None:
            print(f"WARNING: no data for {office}/{district} (pp {p_start}-{p_end})",
                  file=sys.stderr)
            continue
        all_rows.extend(rows)
        offices_seen.append((office, district))
        if ctotal is not None:
            county_totals[(office, district)] = ctotal
        for precinct, cs, wi, tvc in sc:
            selfcheck.append((office, district, precinct, cs, wi, tvc))

    # ---- Verification -------------------------------------------------------
    # PRIMARY (hard): per-precinct self-consistency -- cand sum + write-in == TVC.
    hard = []
    for office, district, precinct, cs, wi, tvc in selfcheck:
        if cs + wi != tvc:
            hard.append(f"{office}/{district} {precinct}: cand({cs})+wi({wi})="
                        f"{cs + wi} != TVC({tvc})")

    # SECONDARY (hard): each party-line + write-in precinct-sum == TOTAL row.
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        key = (office, district, party)
        sums[key] = sums.get(key, 0) + votes
    # write-in sums
    wi_sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        if party == "":
            wi_sums[(office, district)] = wi_sums.get((office, district), 0) + votes
    soft = []
    for od, ctotal in county_totals.items():
        office, district = od
        for party, tv in ctotal.items():
            if party == "WI":
                sv = wi_sums.get(od, 0)
                if sv != tv:
                    hard.append(f"{od} write-in: precinct-sum={sv} "
                                f"!= TOTAL={tv}")
            else:
                sv = sums.get((office, district, party), 0)
                if sv != tv:
                    hard.append(f"{od} {party}: precinct-sum={sv} "
                                f"!= TOTAL={tv}")
    for od in sorted(set((o, d) for o, d, *_ in selfcheck) - set(county_totals)):
        soft.append(f"{od}: emitted rows but no TOTAL row found")

    # ---- Write CSV ----------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow([COUNTY, precinct, office, district, party, cand, votes])

    precincts = {r[4] for r in all_rows}
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"office-districts={offices_seen} -> {OUT_PATH}")
    n_sc = len(selfcheck)
    n_ok = n_sc - len([h for h in hard if "TVC" in h])
    print(f"Self-consistency: {n_ok}/{n_sc} precincts satisfy "
          f"cand+write-in == TVC.")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===",
              file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
    if soft:
        print(f"--- {len(soft)} note(s) (non-fatal) ---", file=sys.stderr)
        for p in soft[:60]:
            print("  " + p, file=sys.stderr)
    if hard:
        return 1
    print(f"Verification OK: {len(hard)} hard failures, {len(soft)} note(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())