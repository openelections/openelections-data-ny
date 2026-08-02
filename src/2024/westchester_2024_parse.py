#!/usr/bin/env python3
"""Dedicated parser for Westchester County 2024 general precinct results (PDF).

The Westchester County BOE publishes an "Election Book" PDF (`Westchester.pdf`,
688 pp) — same family as Onondaga/Warren/Monroe/Saratoga, and the DATA extracts
cleanly via `extract_text()`. The old shared-RPP scan note ("1284 precincts,
fabricates rows, parties swapped REP=Harris, major structural issue") was WRONG
— an artifact of the shared parser trying to read the ROTATED candidate-name
header (which `extract_text` garbles) instead of the UPRIGHT party-code row.

Layout (per the printed INDEX p1-2, and confirmed on every data page):
  - Each office spans a page range; every data page carries an UPRIGHT line
    `2024 GENERAL <OFFICE TITLE> <N> OF 688` and an UPRIGHT party-code row
    `DEM REP CON WOR [LAR] W/I W/I ...` (the column header). The candidate
    NAMES are printed ROTATED/vertical above the party row and are garbled by
    `extract_text` ("SIRRAH"=Harris, "PMURT"=Trump) — IGNORED; names come from
    a hardcoded CAND map.
  - The party-code row is always in CANONICAL NY ballot order (DEM, REP, CON,
    WOR, LAR — filtered to the lines present for that office) followed by one
    or more `W/I` (write-in) columns. So party is assigned POSITIONALLY from
    the row tokens (each non-W/I token = that column's party; each W/I = a
    write-in column). This is the key difference from Warren (where the party
    row is non-standard and must be parsed per-column from header parens) —
    Westchester's upright row gives it directly and it is canonical.
  - Data row: `<precinct label> <EDCODE> <v1>...<vN> <CANVASS> <VOID-BLANK>
    <BALLOT TOTAL>` where N = #party tokens (incl. W/I). EDCODE is the first
    4+ digit token (5 or 6 digits — town codes 10001.. are 5d, city/town
    codes 140010..250101 are 6d; Yonkers labels "City of Yonkers Ward 1 ED 1"
    contain single-digit Ward/ED words, so the EDCODE is located as the first
    token of >=4 digits, NOT the first numeric token). Per-row arithmetic:
    sum(v1..vN) == CANVASS; CANVASS + VOID == BALLOT.
  - Sub-total/total rows: per-town "TOTAL:" subtotals on each page and, on the
    LAST page of each office, a rollup "TOTAL OF YONKERS"/"TOTAL OF TOWNS"/
    "TOTAL OF CITIES"/"TOTAL OF COUNTY WIDE" each followed by a "TOTALS:" row.
    The "TOTAL OF COUNTY WIDE" TOTALS row is the county grand total for that
    office (within Westchester) — the verification anchor. All TOTAL rows are
    skipped as precincts (they don't start with "Town of"/"City of").

16 office-districts (detected from the upright office-title line):
  PRESIDENT OF THE UNITED STATES        President       Harris (DEM/WOR) / Trump (REP/CON)
  UNITED STATES SENATOR                U.S. Senate     Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  CONGRESSIONAL DISTRICT - 16TH        U.S. House 16   George S. Latimer (DEM) / Miriam Levitt Flisser (REP)
  CONGRESSIONAL DISTRICT - 17TH        U.S. House 17   Mondaire L. Jones (DEM) / Mike Lawler (REP/CON) / Anthony Frascone (WOR)
  SENATORIAL DISTRICT - 34TH           State Senate 34 Nathalia Fernandez (DEM) / Edwinna Herrera (REP/CON)
  SENATORIAL DISTRICT - 35TH           State Senate 35 Andrea Stewart-Cousins (DEM/WOR) / Khristen M. Kerr (REP)
  SENATORIAL DISTRICT - 36TH           State Senate 36 Jamaal T. Bailey (DEM) / Irene Estrada (CON)  [no REP]
  SENATORIAL DISTRICT - 37TH           State Senate 37 Shelley B. Mayer (DEM/WOR) / Tricia S. Lindsay (REP/CON)
  SENATORIAL DISTRICT - 40TH           State Senate 40 Peter B. Harckham (DEM/WOR) / Gina M. Arena (REP/CON)
  ASSEMBLY DISTRICT - 88TH             State Assembly 88  Amy Paulin (DEM/WOR) / Thomas H. Fix Jr. (REP/CON)
  ASSEMBLY DISTRICT - 89TH             State Assembly 89  Gary J. Pretlow (DEM)  [uncontested]
  ASSEMBLY DISTRICT - 90TH             State Assembly 90  Nader J. Sayegh (DEM) / John Isaac (REP/CON)
  ASSEMBLY DISTRICT - 91ST             State Assembly 91  Steven Otis (DEM/WOR) / Katie Manger (REP)
  ASSEMBLY DISTRICT - 92ND             State Assembly 92  MaryJane C. Shimsky (DEM/WOR) / Alessandro Crocco (REP/CON)
  ASSEMBLY DISTRICT - 93RD             State Assembly 93  Chris Burdick (DEM/WOR)  [uncontested]
  ASSEMBLY DISTRICT - 94TH             State Assembly 94  Zachary C. Couzens (DEM) / Matthew J. Slater (REP/CON)
  ASSEMBLY DISTRICT - 95TH             State Assembly 95  Dana Levenberg (DEM/WOR) / Michael L. Capalbo (REP/CON)
Non-canonical offices (Supreme Court Justice 9th JD, District Attorney, County
Court Judge, Family Court Judge, all town/village offices, Proposals) have no
canonical title -> skipped. Candidate names via CAND[(office,district,party)]
matched to committed siblings: House 17/SD-40/AD-94/AD-95 -> Putnam corpus
(Mondaire L. Jones, Mike Lawler, Peter B. Harckham, Gina M. Arena, Zachary C.
Couzens, Matthew J. Slater, Dana Levenberg, Michael L. Capalbo); House 16 ->
NYS BOE confirmed (George S. Latimer, Miriam Levitt Flisser); the rest are
Westchester-unique 2024 ballot names from the rotated PDF header (reversed to
read), cross-checked against the 2022 Westchester file for the same incumbents
(Paulin, Pretlow, Sayegh, Otis, Shimsky, Burdick, Stewart-Cousins, Fernandez,
Bailey, Mayer). WOR=Working Families, LAR=LaRouche.

Westchester is SPLIT across NY-16/NY-17 (House), SD-34/35/36/37/40 (Senate),
and AD-88..95 (Assembly); each partition is disjoint and complete == President
(verified by precinct-set union). President/Senate are county-wide.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON columns) — exactly
#148 convention; emit one row per party-line column. Write-ins: every W/I
column (named write-ins, e.g. President's 9: Stein/West/Oliver/De la Cruz/
Sonski/Ayyadurai/Garrity/O'Donnell/"Future Madam Potus"; House 16's Bowman
write-in campaign) is AGGREGATED into ONE "Write-in" row (party empty) per
(precinct, office) when the sum > 0 (#128/#148 convention — named write-ins
are NOT emitted as separate candidate rows). VOID-BLANK and BALLOT TOTAL
omitted. 0-vote candidate rows omitted.

Precinct naming matches the committed 2022 Westchester file: towns/cities
"Town of Bedford -1" / "City of Rye -1" -> "Town of Bedford - 1" / "City of
Rye - 1" (spaces around the dash); City of Yonkers (the only warded city)
"City of Yonkers Ward 1 ED 1" is kept verbatim. The label is taken verbatim
from the PDF (which already matches the 2022 convention except for the
dash spacing).

Verification (all HARD):
  1. per data row: sum(vote cols) == CANVASS; CANVASS + VOID == BALLOT TOTAL.
  2. per (office, district, party): precinct-sum == "TOTAL OF COUNTY WIDE"
     TOTALS row + write-in precinct-sum == county-wide write-in.
  3. candidate surname PRESENCE in the (reversed) rotated page header text,
     checked ONCE per office.
  4. House 16/17 + SD-34/35/36/37/40 + AD-88..95 splits each disjoint +
     complete == President precinct set.
Run with uv (pdfplumber):  uv run python westchester_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "WESTCHESTER_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Westchester.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__westchester__precinct.csv"
)
COUNTY = "Westchester"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""),
                ("U.S. House", "16"), ("U.S. House", "17"),
                ("State Senate", "34"), ("State Senate", "35"),
                ("State Senate", "36"), ("State Senate", "37"),
                ("State Senate", "40"),
                ("State Assembly", "88"), ("State Assembly", "89"),
                ("State Assembly", "90"), ("State Assembly", "91"),
                ("State Assembly", "92"), ("State Assembly", "93"),
                ("State Assembly", "94"), ("State Assembly", "95")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4}

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
    ("U.S. House", "16", "DEM"): "George S. Latimer",
    ("U.S. House", "16", "REP"): "Miriam Levitt Flisser",
    ("U.S. House", "17", "DEM"): "Mondaire L. Jones",
    ("U.S. House", "17", "WOR"): "Anthony Frascone",
    ("U.S. House", "17", "REP"): "Mike Lawler",
    ("U.S. House", "17", "CON"): "Mike Lawler",
    ("State Senate", "34", "DEM"): "Nathalia Fernandez",
    ("State Senate", "34", "REP"): "Edwinna Herrera",
    ("State Senate", "34", "CON"): "Edwinna Herrera",
    ("State Senate", "35", "DEM"): "Andrea Stewart-Cousins",
    ("State Senate", "35", "WOR"): "Andrea Stewart-Cousins",
    ("State Senate", "35", "REP"): "Khristen M. Kerr",
    ("State Senate", "36", "DEM"): "Jamaal T. Bailey",
    ("State Senate", "36", "CON"): "Irene Estrada",
    ("State Senate", "37", "DEM"): "Shelley B. Mayer",
    ("State Senate", "37", "WOR"): "Shelley B. Mayer",
    ("State Senate", "37", "REP"): "Tricia S. Lindsay",
    ("State Senate", "37", "CON"): "Tricia S. Lindsay",
    ("State Senate", "40", "DEM"): "Peter B. Harckham",
    ("State Senate", "40", "WOR"): "Peter B. Harckham",
    ("State Senate", "40", "REP"): "Gina M. Arena",
    ("State Senate", "40", "CON"): "Gina M. Arena",
    ("State Assembly", "88", "DEM"): "Amy Paulin",
    ("State Assembly", "88", "WOR"): "Amy Paulin",
    ("State Assembly", "88", "REP"): "Thomas H. Fix Jr.",
    ("State Assembly", "88", "CON"): "Thomas H. Fix Jr.",
    ("State Assembly", "89", "DEM"): "Gary J. Pretlow",
    ("State Assembly", "90", "DEM"): "Nader J. Sayegh",
    ("State Assembly", "90", "REP"): "John Isaac",
    ("State Assembly", "90", "CON"): "John Isaac",
    ("State Assembly", "91", "DEM"): "Steven Otis",
    ("State Assembly", "91", "WOR"): "Steven Otis",
    ("State Assembly", "91", "REP"): "Katie Manger",
    ("State Assembly", "92", "DEM"): "MaryJane C. Shimsky",
    ("State Assembly", "92", "WOR"): "MaryJane C. Shimsky",
    ("State Assembly", "92", "REP"): "Alessandro Crocco",
    ("State Assembly", "92", "CON"): "Alessandro Crocco",
    ("State Assembly", "93", "DEM"): "Chris Burdick",
    ("State Assembly", "93", "WOR"): "Chris Burdick",
    ("State Assembly", "94", "DEM"): "Zachary C. Couzens",
    ("State Assembly", "94", "REP"): "Matthew J. Slater",
    ("State Assembly", "94", "CON"): "Matthew J. Slater",
    ("State Assembly", "95", "DEM"): "Dana Levenberg",
    ("State Assembly", "95", "WOR"): "Dana Levenberg",
    ("State Assembly", "95", "REP"): "Michael L. Capalbo",
    ("State Assembly", "95", "CON"): "Michael L. Capalbo",
}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}
PARTY_TOKENS = {"DEM", "REP", "CON", "WOR", "LAR", "W/I"}


def _office_of_title(title):
    t = (title or "").strip()
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    m = re.search(r"CONGRESSIONAL DISTRICT - (\d+)(?:ST|ND|RD|TH)", t)
    if m:
        return ("U.S. House", m.group(1))
    m = re.search(r"SENATORIAL DISTRICT - (\d+)(?:ST|ND|RD|TH)", t)
    if m:
        return ("State Senate", m.group(1))
    m = re.search(r"ASSEMBLY DISTRICT - (\d+)(?:ST|ND|RD|TH)", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


def _int(v):
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _is_num(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _surname(name):
    toks = [t for t in (name or "").split() if t]
    while toks and _norm(toks[-1]) in NAME_SUFFIX:
        toks.pop()
    return _norm(toks[-1]) if toks else ""


def _precinct_name(label):
    # label e.g. "Town of Bedford -1" / "City of Rye -1" / "City of Yonkers
    # Ward 1 ED 1". Normalize "-N" -> " - N" to match the 2022 file; leave
    # the Yonkers ward form verbatim.
    m = re.match(r"^(.+?) -(\d+)$", label)
    if m:
        return f"{m.group(1)} - {m.group(2)}"
    return label


def _party_row(toks):
    """Return the list of party tokens if `toks` is a party-code header row
    (2..20 tokens, all in PARTY_TOKENS), else None."""
    if 2 <= len(toks) <= 20 and all(t in PARTY_TOKENS for t in toks):
        return toks
    return None


def main():
    pdf = pdfplumber.open(SRC_PATH)
    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)        # (office,district,party) -> precinct sum
    wisum = defaultdict(int)       # (office,district) -> write-in precinct sum
    anchor = {}                    # (office,district,party) -> county-wide total
    wi_anchor = {}                 # (office,district) -> county-wide write-in
    arith_fail = []
    name_fail = []
    name_checked = set()
    od_seen = []
    od_precincts = defaultdict(set)
    pres_precincts = set()
    house_precincts = defaultdict(set)
    sd_precincts = defaultdict(set)
    ad_precincts = defaultdict(set)
    header_text = {}              # od -> reversed rotated header text (lower)

    for pno in range(len(pdf.pages)):
        raw = pdf.pages[pno].extract_text()
        if not raw:
            continue
        lines = [l for l in raw.split("\n") if l.strip()]
        if not lines:
            continue
        # office from the upright "2024 GENERAL ... OF 688" line
        od = None
        for l in lines:
            m = re.search(r"2024 GENERAL (.+?) \d+ OF 688", l)
            if m:
                od = _office_of_title(m.group(1))
                break
        if od is None or od not in OFFICE_RANK:
            continue
        office, district = od
        if od not in od_seen:
            od_seen.append(od)
        # party-code row
        parties = None
        for l in lines:
            pr = _party_row(l.split())
            if pr:
                parties = pr
                break
        if parties is None:
            continue
        n_vote = len(parties)          # incl. W/I columns
        cand_parties = [p for p in parties if p != "W/I"]
        cand_set = set(cand_parties)
        # cross-check: header party set must match CAND keys for this od
        expected = {p for p in ("DEM", "REP", "CON", "WOR", "LAR")
                    if (office, district, p) in CAND}
        if cand_set != expected:
            name_fail.append(f"{od}: party row {parties} -> cand {sorted(cand_set)} "
                             f"!= CAND {sorted(expected)}")
        # surname-presence check ONCE per office: collect the rotated header
        # text on this (first seen) page, reverse each line, and require each
        # candidate's surname to appear (the rotated names read reversed).
        if od not in name_checked:
            name_checked.add(od)
            rev = []
            for l in lines:
                s = l.strip()
                if not s or "2024 GENERAL" in s:
                    continue
                if _party_row(s.split()):
                    continue
                if re.search(r"\d", s):
                    continue
                if re.search(r"[a-z]", s):
                    continue
                if re.search(r"[A-Z]", s):
                    rev.append(s[::-1].lower())
            header_text[od] = _norm(" ".join(rev))
            ht = header_text[od]
            for p in cand_set:
                sn = _surname(CAND[(office, district, p)])
                if sn and sn not in ht:
                    name_fail.append(f"{od} {p}: surname {sn!r} not in "
                                     f"reversed header (page {pno})")

        # capture county-wide anchor: prefer the "TOTAL OF COUNTY WIDE" rollup
        # (last section on the office's last page); fall back to the last plain
        # "TOTAL:" row on the office's last page (small districts like SD-36
        # have no rollup, just one grand-total TOTAL row). Track the last
        # TOTAL/TOTALS row with n_vote+3 values for the fallback.
        expect_county = False
        last_total = None
        for l in lines:
            s = l.strip()
            if "COUNTY WIDE" in s:
                expect_county = True
                continue
            if expect_county and (s.startswith("TOTALS:") or s.startswith("TOTAL:")):
                vals = [_int(t) for t in re.findall(r"[\d,]+", s)]
                if len(vals) == n_vote + 3:
                    for j, p in enumerate(parties):
                        if p != "W/I":
                            anchor[(office, district, p)] = vals[j]
                    wi_anchor[(office, district)] = sum(
                        vals[j] for j, p in enumerate(parties) if p == "W/I")
                expect_county = False
                continue
            if s.startswith("TOTALS:") or s.startswith("TOTAL:"):
                vals = [_int(t) for t in re.findall(r"[\d,]+", s)]
                if len(vals) == n_vote + 3:
                    last_total = vals
        if last_total is not None:
            od = (office, district)
            for j, p in enumerate(parties):
                if p != "W/I" and (od[0], od[1], p) not in anchor:
                    anchor[(od[0], od[1], p)] = last_total[j]
            if od not in wi_anchor:
                wi_anchor[od] = sum(last_total[j] for j, p in enumerate(parties)
                                    if p == "W/I")

        # data rows
        for l in lines:
            s = l.strip()
            if not (s.startswith("Town of ") or s.startswith("City of ")
                    or s.startswith("Village of ")):
                continue
            toks = s.split()
            k = next((j for j, t in enumerate(toks)
                      if re.match(r"^\d{4,}$", t)), None)
            if k is None or k == 0:
                continue
            nums = toks[k:]
            if not all(_is_num(t) for t in nums):
                continue
            vals = [_int(t) for t in nums]
            if len(vals) != n_vote + 4:    # EDcode + n_vote + CANVASS + VOID + BALLOT
                continue
            label = " ".join(toks[:k])
            prec = _precinct_name(label)
            vote = vals[1:1 + n_vote]
            canvass = vals[1 + n_vote]
            void = vals[2 + n_vote]
            ballot = vals[3 + n_vote]
            if sum(vote) != canvass:
                arith_fail.append((pno, prec, od, sum(vote), canvass, "canvass"))
            if canvass + void != ballot:
                arith_fail.append((pno, prec, od, canvass, void, ballot))
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            od_precincts[od].add(prec)
            if office == "President":
                pres_precincts.add(prec)
            elif office == "U.S. House":
                house_precincts[district].add(prec)
            elif office == "State Senate":
                sd_precincts[district].add(prec)
            elif office == "State Assembly":
                ad_precincts[district].add(prec)
            wi = 0
            for j, p in enumerate(parties):
                v = vote[j]
                if p == "W/I":
                    wi += v
                else:
                    psum[(office, district, p)] += v
                    if v > 0 and (office, district, p) in CAND:
                        all_rows.append((prec, office, district, p,
                                         CAND[(office, district, p)], v))
            wisum[(office, district)] += wi
            if wi > 0:
                all_rows.append((prec, office, district, "", "Write-in", wi))

    # ---- HARD verification ------------------------------------------------
    hard = []
    for pno, prec, od, a, b, c in arith_fail:
        hard.append(f"p{pno} {prec} {od}: {a} != {b} ({c})")
    hard.extend(name_fail)
    for od in OFFICE_ORDER:
        office, district = od
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, p) not in CAND:
                continue
            s = psum.get((office, district, p), 0)
            a = anchor.get((office, district, p))
            if a is None:
                hard.append(f"{od} {p}: no county-wide anchor")
            elif s != a:
                hard.append(f"{od} {p}: precinct-sum={s} != county-wide={a}")
        ws_ = wisum.get(od, 0)
        wa = wi_anchor.get(od)
        if wa is None:
            hard.append(f"{od} write-in: no county-wide anchor")
        elif ws_ != wa:
            hard.append(f"{od} write-in: precinct-sum={ws_} != county-wide={wa}")

    # split disjoint + complete == President
    def check_split(label, groups):
        union = set()
        for ps in groups.values():
            union |= ps
        if union != pres_precincts:
            hard.append(f"{label} split not complete: union={len(union)} "
                        f"president={len(pres_precincts)}; missing="
                        f"{sorted(pres_precincts - union)[:5]}")
        ds = list(groups)
        for a in range(len(ds)):
            for b in range(a + 1, len(ds)):
                ov = groups[ds[a]] & groups[ds[b]]
                if ov:
                    hard.append(f"{label} split overlap {ds[a]}/{ds[b]}: "
                                f"{sorted(ov)[:5]}")
    check_split("House", house_precincts)
    check_split("SD", sd_precincts)
    check_split("AD", ad_precincts)

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
    for od in OFFICE_ORDER:
        office, district = od
        parts = []
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, p) in CAND:
                parts.append(f"{p}={psum.get((office,district,p),0)}")
        parts.append(f"Write-in={wisum.get(od,0)}")
        a = anchor.get((office, district, next((p for p in ("DEM","REP","CON","WOR","LAR")
                if (office, district, p) in CAND), "")), "?")
        print(f"  {office} {district}: {', '.join(parts)} (county-wide={a})")
    print(f"  House split: {dict((d,len(ps)) for d,ps in house_precincts.items())}")
    print(f"  SD split: {dict((d,len(ps)) for d,ps in sd_precincts.items())}")
    print(f"  AD split: {dict((d,len(ps)) for d,ps in ad_precincts.items())}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:80]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())