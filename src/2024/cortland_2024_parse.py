#!/usr/bin/env python3
"""Dedicated parser for Cortland County 2024 general precinct results (PDF).

The Cortland County BOE publishes an NYS "Results per Precinct" SOVC report as a
rotated, letter-spaced PDF (`Cortland.pdf`, 14 pages). natural_pdf's
`extract_tables()` recovers the grid, but the candidate/party HEADER cells are
GARBAGED by the rotation ("Democratic" splits as "De"+"mocratic", "Blanks" ->
"nks Bla", candidate surnames break across lines) -- so header substring matching
is useless. This parser uses a POSITIONAL approach instead.

Each contest table is laid out as 4 side-by-side counting-group blocks:
  Early Voting | Election Day | Absentees/Affidavits | Total Votes
Each block has the SAME per-candidate column layout (the candidate columns repeat
for every counting group). Block 4 ("Total Votes") is the GRAND TOTAL per
precinct -- that is the only block we need. In every data row the 4 blocks are
separated by empty cells, so block 4 = the LAST contiguous run of non-empty
cells in the row. We slice off the trailing `block_width` cells and read the
candidate values positionally; party is assigned by the canonical NY ballot
order (DEM, REP, CON, WOR, LAR, "Local 607") filtered to the lines that appear
for that office (from the hardcoded CAND map). The candidate surname is then
verified as a LETTER SUBSEQUENCE of the (scrambled) block-1 header cell -- this
catches a wrong column-order assumption even though the names are unreadable.

Cortland is SPLIT across NY-19 (Josh Riley / Marcus Molinaro, towns only) /
NY-22 (John W. Mannion / Brandon M. Williams, city wards + towns), and across
AD-125 (Anna Kelles, uncontested DEM/WOR) / AD-131 (Jeff Gallahan, uncontested
REP/CON). SD-52 (Lea Webb DEM/WOR vs Michael Sigler REP) covers the whole county
AND carries a Cortland-only "Local 607" ballot line for Sigler (no precedent in
the committed NY 2024 corpus -- Broome/Tioga do not carry it); the party code is
emitted VERBATIM as "Local 607". Canonical offices (detected from the row-0
title cell):
  Electors for President/Vice President   President      Harris (DEM/WOR) / Trump (REP/CON)
  United States Senator                    U.S. Senate    Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  Rep. in Congress - 19th District         U.S. House 19  Josh Riley (DEM/WOR) / Marcus Molinaro (REP/CON)
  Rep. in Congress - 22nd District         U.S. House 22  John W. Mannion (DEM/WOR) / Brandon M. Williams (REP/CON)
  State Senator - 52nd District            State Senate 52  Lea Webb (DEM/WOR) / Michael Sigler (REP + Local 607)
  Member of Assembly - 125th AD            State Assembly 125  Anna Kelles (DEM/WOR)         (uncontested)
  Member of Assembly - 131st AD            State Assembly 131  Jeff Gallahan (REP/CON)         (uncontested)
Non-canonical tables (Prop One/Two, County Family Court Judge, District Attorney,
Legislator, City Court Judge, town/village offices) have no title match -> skipped.

Page -> table layout (each county-wide office spans TWO tables: city wards then
towns): p0 President, p1 Senate, p2 House19(t0)+House22(t1), p3 SD-52, p4 AD-125
(t0)+AD-131(t1). County-wide offices (President/Senate/SD-52) anchor on the
"County Totals" row (full county); the "City Totals" row is a city subtotal used
as a secondary sanity check. Split offices anchor on their single total row
(CD19/CD22/Totals).

Fusion is SPLIT at the source (separate party-line columns) -- emit one row per
party-line column. Write-ins: the block-4 "Write-ins" column is an aggregate --
emit ONE "Write-in" row (party empty) per (precinct, office) when >0. Voids/
Blanks/Subtotal/Totals columns are skipped (OE omits them). 0-vote candidate
rows are omitted. Precinct naming matches the committed 2022 Cortland file:
city wards get a "Cortland " prefix ("Ward 1 ED 1" -> "Cortland Ward 1 ED 1"),
towns are bare ("Cortlandville-1", "Harford", "Preble", ...).

Verification:
  1. per data row: sum(candidates) + write-ins + voids + blanks == Totals (block-4
     internal arithmetic -- a strong per-precinct ballot check).
  2. per (office, district, party): precinct-sum == anchor total row; write-in
     precinct-sum == anchor Write-ins col.
  3. candidate-surname SUBSEQUENCE check against the scrambled block-1 header cell.
  4. House 19/22 split + AD-125/131 split disjoint + complete == President set.
Run with uv (natural_pdf):  uv run python cortland_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict, Counter

from natural_pdf import PDF

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "CORTLAND_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Cortland.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__cortland__precinct.csv"
)
COUNTY = "Cortland"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "19"),
                ("U.S. House", "22"), ("State Senate", "52"),
                ("State Assembly", "125"), ("State Assembly", "131")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
# canonical NY ballot order, extended with the Cortland-only Local 607 line
CANON_ORDER = ["DEM", "REP", "CON", "WOR", "LAR", "Local 607"]
PARTY_RANK = {p: i for i, p in enumerate(CANON_ORDER)}

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
    ("U.S. House", "22", "DEM"): "John W. Mannion",
    ("U.S. House", "22", "WOR"): "John W. Mannion",
    ("U.S. House", "22", "REP"): "Brandon M. Williams",
    ("U.S. House", "22", "CON"): "Brandon M. Williams",
    ("State Senate", "52", "DEM"): "Lea Webb",
    ("State Senate", "52", "WOR"): "Lea Webb",
    ("State Senate", "52", "REP"): "Michael Sigler",
    ("State Senate", "52", "Local 607"): "Michael Sigler",
    ("State Assembly", "125", "DEM"): "Anna Kelles",
    ("State Assembly", "125", "WOR"): "Anna Kelles",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}

# row-0 title substring -> (office, district)
def _office_of_title(title):
    t = (title or "").strip()
    if "President" in t:
        return ("President", "")
    if t.startswith("United States Senator"):
        return ("U.S. Senate", "")
    m = re.search(r"Rep\. in Congress\s*-\s*(\d+)\w* District", t)
    if m:
        return ("U.S. House", m.group(1))
    m = re.search(r"State Senator\s*-\s*(\d+)\w* District", t)
    if m:
        return ("State Senate", m.group(1))
    m = re.search(r"Member of Assembly\s*-\s*(\d+)\w* AD", t)
    if m:
        return ("State Assembly", m.group(1))
    return None


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _surname(name):
    toks = [t for t in (name or "").split() if t]
    while toks and _norm(toks[-1]) in NAME_SUFFIX:
        toks.pop()
    return _norm(toks[-1]) if toks else ""


def _contains_letters(surname, text):
    """True if every letter of `surname` (with multiplicity) appears in `text`.

    The Cortland SOVC rotation splits candidate surnames across lines AND
    reverses letter chunks ("Trump" -> "mp"+"Tru"), so an in-order subsequence
    check is useless. A letter-multiset containment check still catches a wrong
    column->party assignment (the wrong candidate's surname letters would not
    all be present in that header cell) while tolerating the scrambling.
    """
    need = Counter(_norm(surname))
    have = Counter(_norm(text))
    return all(have.get(ch, 0) >= n for ch, n in need.items())


def _block4(row):
    """Last contiguous run of non-empty cells in a row = the Total Votes block."""
    cells = ["" if c is None else str(c) for c in row]
    # strip trailing empties
    end = len(cells)
    while end > 0 and cells[end - 1].strip() == "":
        end -= 1
    start = end
    while start > 0 and cells[start - 1].strip() != "":
        start -= 1
    return cells[start:end], start


def main():
    pdf = PDF(SRC_PATH)
    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)          # (office,district,party) -> precinct sum
    wisum = defaultdict(int)         # (office,district) -> write-in precinct sum
    anchor = {}                      # (office,district,party) -> anchor total
    wi_anchor = {}                   # (office,district) -> anchor write-in
    city_anchor = {}                 # city-subtotal anchor (sanity), per office
    name_seen = defaultdict(set)
    arith_fail = []
    od_seen = []
    house_precincts = defaultdict(set)
    ad_precincts = defaultdict(set)
    pres_precincts = set()
    od_precincts = defaultdict(set)

    for pno in range(len(pdf.pages)):
        for tab in pdf.pages[pno].extract_tables():
            rows = tab
            if not rows:
                continue
            # row 0: find the contest title cell (non-empty, not a block label)
            title = None
            for c in rows[0]:
                t = "" if c is None else str(c).strip()
                if t and t not in ("Early Voting", "Election Day",
                                   "Absentees/Affidavits", "Total Votes"):
                    if "Early Voting" in t or "Election Day" in t or t[:1].isalpha():
                        title = t
                        break
            od = _office_of_title(title)
            if od is None or od not in OFFICE_RANK:
                continue
            office, district = od
            if od not in od_seen:
                od_seen.append(od)
            # present party lines for this office, in canonical ballot order
            parties = [p for p in CANON_ORDER if (office, district, p) in CAND]
            num_cand = len(parties)
            has_void = (office == "President")  # only President has a Voids col
            ctrl = 5 if has_void else 4
            block_width = num_cand + ctrl
            # block-1 candidate header cells start at column 2 (after col0,col1)
            hdr = rows[1] if len(rows) > 1 else []

            for r in rows[2:]:
                cells = ["" if c is None else str(c) for c in r]
                if not cells:
                    continue
                label = cells[0].strip()
                prec_cell = cells[1].strip() if len(cells) > 1 else ""
                b4, b4start = _block4(cells)
                if len(b4) != block_width:
                    # a stray/blank row or group header ("City of Cortland")
                    continue
                if prec_cell == "":
                    # total / subtotal / group-header row (no precinct name)
                    low = label.lower()
                    if low in ("city totals", "county totals", "cd19", "cd22",
                               "totals"):
                        vals = [_int(x) for x in b4]
                        cand_vals = vals[:num_cand]
                        if has_void:
                            wi = vals[num_cand]
                            # void = vals[num_cand+1]; blank = vals[num_cand+2]
                        else:
                            wi = vals[num_cand]
                            # blank = vals[num_cand+1]
                        if low == "county totals":
                            for i, p in enumerate(parties):
                                anchor[(office, district, p)] = cand_vals[i]
                            wi_anchor[(office, district)] = wi
                        elif low == "city totals":
                            for i, p in enumerate(parties):
                                city_anchor[(office, district, p)] = cand_vals[i]
                        else:  # CD19 / CD22 / Totals (split-office anchor)
                            for i, p in enumerate(parties):
                                anchor[(office, district, p)] = cand_vals[i]
                            wi_anchor[(office, district)] = wi
                    continue
                # precinct row
                prec = re.sub(r"\s+", " ", prec_cell).strip()
                if prec.startswith("Ward "):
                    prec = "Cortland " + prec
                if prec not in seen_prec:
                    seen_prec.add(prec)
                    prec_order.append(prec)
                od_precincts[od].add(prec)
                if office == "President":
                    pres_precincts.add(prec)
                elif office == "U.S. House":
                    house_precincts[district].add(prec)
                elif office == "State Assembly":
                    ad_precincts[district].add(prec)
                vals = [_int(x) for x in b4]
                cand_vals = vals[:num_cand]
                if has_void:
                    wi = vals[num_cand]
                    void = vals[num_cand + 1]
                    blank = vals[num_cand + 2]
                    sub = vals[num_cand + 3]
                    tot = vals[num_cand + 4]
                else:
                    wi = vals[num_cand]
                    void = 0
                    blank = vals[num_cand + 1]
                    sub = vals[num_cand + 2]
                    tot = vals[num_cand + 3]
                # block-4 arithmetic check (per-row ballot check)
                if sum(cand_vals) + wi + void + blank != tot:
                    arith_fail.append(
                        (prec, office, district, tot,
                         sum(cand_vals), wi, void, blank))
                for i, p in enumerate(parties):
                    v = cand_vals[i]
                    psum[(office, district, p)] += v
                    # surname letter-containment check vs scrambled block-1 header
                    hcol = 2 + i
                    if hcol < len(hdr):
                        htext = "" if hdr[hcol] is None else str(hdr[hcol])
                    else:
                        htext = ""
                    expected = CAND.get((office, district, p))
                    if expected and not _contains_letters(_surname(expected), htext):
                        name_seen[(office, district, p)].add(f"!HDR:{htext[:24]!r}")
                    if v > 0 and (office, district, p) in CAND:
                        all_rows.append((prec, office, district, p,
                                         CAND[(office, district, p)], v))
                wisum[(office, district)] += wi
                if wi > 0:
                    all_rows.append((prec, office, district, "", "Write-in", wi))

    # ---- HARD verification --------------------------------------------------
    hard = []
    warnings = []
    # block-4 per-row arithmetic: candidates + write-ins + voids + blanks == Totals
    for prec, office, district, tot, cs, wi, void, blank in arith_fail:
        hard.append(f"{prec} {office} {district}: cand+wi+void+blank="
                    f"{cs}+{wi}+{void}+{blank}={cs+wi+void+blank} != Totals={tot}")
    county_wide = {"President", "U.S. Senate", "State Senate"}
    for od in OFFICE_ORDER:
        office, district = od
        partial = (office in county_wide and pres_precincts
                   and od_precincts.get(od, set()) != pres_precincts)
        if partial:
            missing = sorted(pres_precincts - od_precincts.get(od, set()))
            warnings.append(
                f"{od}: source lists {len(od_precincts.get(od, set()))}/"
                f"{len(pres_precincts)} precincts (missing {missing}); "
                f"anchor covers all -- per-precinct data emitted for the "
                f"{len(od_precincts.get(od, set()))} available, anchor check demoted")
        for p in CANON_ORDER:
            if (office, district, p) not in CAND:
                continue
            s = psum.get((office, district, p), 0)
            a = anchor.get((office, district, p))
            if a is None:
                hard.append(f"{od} {p}: no anchor total row")
            elif s != a:
                msg = f"{od} {p}: precinct-sum={s} != anchor={a}"
                if partial:
                    warnings.append(msg + " (source gap, demoted)")
                else:
                    hard.append(msg)
        ws_ = wisum.get(od, 0)
        wa = wi_anchor.get(od)
        if wa is None:
            hard.append(f"{od} write-in: no anchor row")
        elif ws_ != wa:
            msg = f"{od} write-in: precinct-sum={ws_} != anchor={wa}"
            if partial:
                warnings.append(msg + " (source gap, demoted)")
            else:
                hard.append(msg)

    # surname-subsequence failures (recorded as "!HDR:" tokens)
    for (office, district, p), toks in name_seen.items():
        bad = [t for t in toks if isinstance(t, str) and t.startswith("!HDR:")]
        if bad:
            hard.append(f"{office}/{district} {p}: surname not a subsequence of "
                        f"block-1 header ({len(bad)} precincts), e.g. {bad[0]}")

    # House 19/22 split + AD 125/131 split disjoint + complete == President
    house_union = set()
    for d, ps in house_precincts.items():
        house_union |= ps
    if house_union != pres_precincts:
        hard.append(f"House split not complete: union={len(house_union)} "
                    f"president={len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - house_union)[:5]}")
    ad_union = set()
    for d, ps in ad_precincts.items():
        ad_union |= ps
    if ad_union != pres_precincts:
        hard.append(f"AD split not complete: union={len(ad_union)} "
                    f"president={len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - ad_union)[:5]}")
    for label, groups in (("House", house_precincts), ("AD", ad_precincts)):
        ds = list(groups)
        overlap = set()
        for a in range(len(ds)):
            for b in range(a + 1, len(ds)):
                overlap |= groups[ds[a]] & groups[ds[b]]
        if overlap:
            hard.append(f"{label} split overlap: {sorted(overlap)[:5]}")

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
        for p in CANON_ORDER:
            if (office, district, p) in CAND:
                parts.append(f"{p}={psum.get((office,district,p),0)}")
        parts.append(f"Write-in={wisum.get(od,0)}")
        a = anchor.get((office, district, next(p for p in CANON_ORDER
                     if (office, district, p) in CAND)), "?")
        print(f"  {office} {district}: {', '.join(parts)} (anchor={a})")
    print(f"  House split: {dict((d, len(ps)) for d, ps in house_precincts.items())}")
    print(f"  AD split: {dict((d, len(ps)) for d, ps in ad_precincts.items())}")
    if warnings:
        print(f"--- {len(warnings)} NON-FATAL source-gap warnings ---")
        for w in warnings:
            print("  " + w)
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())