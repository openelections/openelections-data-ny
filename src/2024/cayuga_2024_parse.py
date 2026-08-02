#!/usr/bin/env python3
"""Dedicated parser for Cayuga County 2024 general precinct results.

Unlike the other 2024 NY counties (PDF sources), Cayuga publishes a clean
CSV (`Cayuga.csv`) that already splits fusion party lines into SEPARATE columns
-- exactly the OpenElections #148-branch convention. So this parser reads the
CSV directly (no PDF / NaturalPDF needed) and reshapes it to the 7-column
OpenElections precinct format:
    county,precinct,office,district,party,candidate,votes

Source layout (one CSV, multiple office blocks, each block = title row + header
row + precinct rows + a "Total" county-grand-total row):
    L: <office title>                         (col0 only)
    L: Election District,<Name (Party)>,...,Write-in,Over Votes,Under Votes
    L: <precinct>,<votes>,<votes>,...,<wi>,<over>,<under>
    ...
    L: Total,<county totals>,...

Canonical offices (Cayuga is SPLIT across U.S. House 22/24 and State Assembly
120/126/131; each precinct is in exactly one of each; State Senate 48 covers all):
  President                       -- Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate                     -- Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 22                   -- Mannion (DEM/WOR) / Williams (REP/CON)
  U.S. House 24                   -- Wagenhauser (DEM) / Tenney (REP/CON)
  State Senate 48                 -- Slater (REP) / May (DEM/WOR)
  State Assembly 120              -- Barclay (REP/CON)  (uncontested)
  State Assembly 126              -- Phillips (DEM/WOR) / Lemondes (REP/CON)
  State Assembly 131              -- Gallahan (REP/CON) (uncontested)
Non-canonical (skipped): State Supreme Court Justice, Family Court Judge, town
offices (Town Justice / Council / Highway Supt), and Proposals/Propositions.

Candidate name + party are read directly from each header column (the source
prints "Kamala D. Harris (DEM)"). Party labels are inconsistent/truncated across
offices -- "Working Families" (President) vs "Famili" (others), "Conser" vs
"CON", "LaRouc" -- so party_of() normalizes all variants. Candidate full names
are taken verbatim from the source (they match the committed 2024 NY corpus:
John W. Mannion, Brandon M. Williams, William A. Barclay, Jeff Gallahan; for
U.S. House 24 the committed corpus is mixed -- genesee/seneca use surname-only
"Tenney"/"Wagenhauser" while jefferson/ontario use "Claudia Tenney"/"David
Wagenhauser"; this parser uses the source's full names, matching jefferson/
ontario). WOR = Working Families (#148-branch convention, NOT WFP/WF);
LaRouc/LaRouche -> LAR.

Write-ins: the source's single aggregate "Write-in" column is emitted as one
"Write-in" row (party empty) per precinct when >0. "Over Votes" / "Under Votes"
are omitted (per #148 convention). 0-vote rows are omitted throughout.

Precinct names are preserved verbatim from the source ("Auburn 8-1", "Aurelius
1") -- matching the "Town N" style of the committed Yates/Lewis 2024 files; the
"Auburn X-Y" codes are the BOE's own precinct identifiers (the 2024 Auburn
wards differ from the 2022 file's, so 2022 names are not reusable). The "Total"
row is skipped as a precinct but used as the verification anchor.

Verification (HARD): for every canonical office block, each candidate column's
precinct-sum and the write-in column's precinct-sum must equal the block's
"Total" row. This validates extraction of every number against the source's own
county grand total. Run with:  python3 cayuga_2024_parse.py   (no uv needed --
stdlib csv only).
"""
import os
import re
import sys
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "CAYUGA_CSV",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Cayuga.csv",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__cayuga__precinct.csv"
)
COUNTY = "Cayuga"

# Canonical office title -> (office, district). district "" = statewide.
def office_of(title):
    t = title.strip()
    if t == "Presidential Electors for President and Vice President":
        return ("President", "")
    if t == "United States Senator":
        return ("U.S. Senate", "")
    m = re.match(r"Representative in Congress D(\d+)$", t)
    if m:
        return ("U.S. House", m.group(1))
    m = re.match(r"State Senate D(\d+)$", t)
    if m:
        return ("State Senate", m.group(1))
    m = re.match(r"Member of Assembly (\d+)$", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


OFFICE_RANK = {
    ("President", ""): 0,
    ("U.S. Senate", ""): 1,
    ("U.S. House", "22"): 2,
    ("U.S. House", "24"): 3,
    ("State Senate", "48"): 4,
    ("State Assembly", "120"): 5,
    ("State Assembly", "126"): 6,
    ("State Assembly", "131"): 7,
}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}

# Party-label variants -> canonical 3-letter code, or None to skip the column.
PARTY_NORM = {
    "DEM": "DEM", "DEMOCRATIC": "DEM", "DEMOCRAT": "DEM",
    "REP": "REP", "REPUBLICAN": "REP", "REPUBLICANS": "REP",
    "CON": "CON", "CONSERVATIVE": "CON", "CONSER": "CON", "CONSV": "CON",
    "WOR": "WOR", "WORKING FAMILIES": "WOR", "WORKINGFAMILIES": "WOR",
    "FAMILIES": "WOR", "FAMILI": "WOR", "WFP": "WOR", "WF": "WOR",
    "LAR": "LAR", "LAROUCHE": "LAR", "LAROUC": "LAR", "LAROUCH": "LAR",
    "IND": "IND", "INDEPENDENCE": "IND",
}

NAME_PARTY_RE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")


def party_of(raw):
    return PARTY_NORM.get(re.sub(r"\s+", " ", raw.strip().upper()))


def parse_header(row):
    """Return (cand_cols, writein_idx) for a header row.
    cand_cols = [(col_index, party, candidate_name)], writein_idx = int or None.
    Over/Under/Yes/No and unknown-party columns are dropped."""
    cand = []
    wi = None
    for j, cell in enumerate(row):
        if j == 0:
            continue  # "Election District"
        c = (cell or "").strip()
        if not c:
            continue
        if c.lower() in ("write-in", "write in", "writeins", "write-ins"):
            wi = j
            continue
        if c.lower() in ("over votes", "undervotes", "under votes",
                         "overvotes", "over vote", "under vote"):
            continue
        if c.lower() in ("yes", "no"):
            continue  # proposal columns (proposals are skipped at office level)
        m = NAME_PARTY_RE.match(c)
        if not m:
            continue  # unparseable header cell -> skip
        name = m.group(1).strip()
        party = party_of(m.group(2))
        if party is None or not name:
            continue  # unknown party (e.g. Integrity) -> skip
        cand.append((j, party, name))
    return cand, wi


def main():
    with open(SRC_PATH, newline="") as f:
        rows = list(csv.reader(f))

    out_rows = []          # (precinct, office, district, party, candidate, votes)
    prec_order = []        # normalized precincts in first-seen order
    seen_prec = set()
    # per (office, district, col_index) -> [precinct votes]; totals dict
    col_sums = {}          # (office, district, col_index) -> precinct sum
    col_total = {}         # (office, district, col_index) -> Total-row value
    wi_sums = {}
    wi_total = {}
    cur_od = None
    cur_cand = []          # [(col_index, party, name)]
    cur_wi = None
    office_blocks = []     # (office, district) seen, for reporting

    for row in rows:
        if not row or not any((c or "").strip() for c in row):
            continue
        c0 = (row[0] or "").strip()
        # office title row: col0 nonempty, col1 empty, not the header
        if c0 and not (row[1] or "").strip() and c0 != "Election District":
            od = office_of(c0)
            cur_od = od
            cur_cand = []
            cur_wi = None
            if od and od not in office_blocks:
                office_blocks.append(od)
            continue
        if c0 == "Election District":
            if cur_od is None:
                continue
            cur_cand, cur_wi = parse_header(row)
            continue
        if cur_od is None or not cur_cand:
            continue
        office, district = cur_od
        # data row: "Total" or a precinct
        if c0 == "Total":
            for j, party, name in cur_cand:
                col_total[(office, district, j)] = int((row[j] or "0").replace(",", "")) if (row[j] or "").strip().lstrip("-").isdigit() else 0
            if cur_wi is not None:
                v = (row[cur_wi] or "0").replace(",", "")
                wi_total[(office, district)] = int(v) if v.strip().lstrip("-").isdigit() else 0
            continue
        # precinct row
        precinct = c0
        if precinct not in seen_prec:
            seen_prec.add(precinct)
            prec_order.append(precinct)
        for j, party, name in cur_cand:
            v = _int(row, j)
            if v > 0:
                out_rows.append((precinct, office, district, party, name, v))
            col_sums[(office, district, j)] = col_sums.get((office, district, j), 0) + v
        if cur_wi is not None:
            wv = _int(row, cur_wi)
            if wv > 0:
                out_rows.append((precinct, office, district, "", "Write-in", wv))
            wi_sums[(office, district)] = wi_sums.get((office, district), 0) + wv

    # ---- HARD verification: precinct sums == Total row ----------------------
    hard = []
    for (office, district, j), s in col_sums.items():
        tv = col_total.get((office, district, j))
        if tv is None:
            hard.append(f"{office}/{district} col{j}: precinct-sum={s} but no Total row")
        elif s != tv:
            # find the candidate name for this col
            nm = next((n for (jj, p, n) in cur_cand if jj == j), "?")
            hard.append(f"{office}/{district} {nm} col{j}: precinct-sum={s} != Total={tv}")
    for od, s in wi_sums.items():
        tv = wi_total.get(od)
        if tv is None:
            hard.append(f"{od} write-in: precinct-sum={s} but no Total row")
        elif s != tv:
            hard.append(f"{od} write-in: precinct-sum={s} != Total={tv}")

    # ---- Write CSV ----------------------------------------------------------
    out_rows.sort(key=lambda r: (prec_order.index(r[0]) if r[0] in prec_order else 999,
                                 OFFICE_RANK.get((r[1], r[2]), 99),
                                 PARTY_RANK.get(r[3], 9), r[4]))
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for precinct, office, district, party, name, v in out_rows:
            w.writerow([COUNTY, precinct, office, district, party, name, v])

    # ---- Report -------------------------------------------------------------
    precincts = {r[0] for r in out_rows}
    print(f"Wrote {len(out_rows)} rows, {len(precincts)} precincts, "
          f"office-districts={office_blocks} -> {OUT_PATH}")
    # county totals per office
    from collections import defaultdict
    ctot = defaultdict(int)
    cwi = defaultdict(int)
    for precinct, office, district, party, name, v in out_rows:
        if party == "":
            cwi[(office, district)] += v
        else:
            ctot[(office, district, party, name)] += v
    print("County-wide totals (per office-district):")
    for od in office_blocks:
        o, d = od
        parts = []
        for (oo, dd, p, n), v in ctot.items():
            if (oo, dd) == od:
                parts.append(f"{n}({p})={v}")
        wv = cwi.get(od, 0)
        parts.append(f"Write-in={wv}")
        print(f"  {o} {d}: {', '.join(parts)}")
    # split check
    from collections import Counter
    sd = Counter(); ad = Counter(); hs = Counter(); allp = set()
    for r in out_rows:
        o, d = r[1], r[2]
        if o == "President": allp.add(r[0])
        elif o == "U.S. House": hs[r[0]] = d
        elif o == "State Assembly": ad[r[0]] = d
    print(f"Split: House {dict(Counter(hs.values()))} (sum={len(hs)}); "
          f"Assembly {dict(Counter(ad.values()))} (sum={len(ad)}); "
          f"precincts={len(allp)}")
    n_chk = len(col_sums) + len(wi_sums)
    n_ok = n_chk - len(hard)
    print(f"Verification: {n_ok}/{n_chk} candidate/write-in columns satisfy "
          f"precinct-sum == Total row.")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


def _int(row, j):
    s = (row[j] if j < len(row) else "").strip().replace(",", "")
    return int(s) if s.lstrip("-").isdigit() else 0


if __name__ == "__main__":
    sys.exit(main())