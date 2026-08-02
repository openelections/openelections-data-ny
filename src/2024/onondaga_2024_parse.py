#!/usr/bin/env python3
"""Dedicated parser for Onondaga County 2024 general precinct results (PDF).

The Onondaga County BOE publishes an "Election Book" PDF (`Onondaga.pdf`,
152 pp) -- the same family as Monroe/Saratoga, and it extracts CLEANLY via
`extract_text()` (unlike the rotated SOVC PDFs). Each contest spans several
detail pages ("... Rows Continued") plus a final "Summary --" page (a town-level
rollup, SKIPPED to avoid double-count). On the last detail page a "TOWN TOTAL"
subtotal and a "GRAND TOTAL" county grand-total row appear.

Each detail page repeats a column header whose data rows look like:
    1ST WARD 01 445 240 145 26 26 4 4
    02      375 208 138 7 18 0 4
    DEWITT 16 329 212 84 10 16 3 4
Columns are letter-coded in a fixed order: A = WHOLE NUMBER (ballots cast, skip
but use for verification), then the candidate party lines in canonical NY
ballot order (DEM, REP, CON, WOR, LAR -- filtered to the lines present for that
office), then the last candidate letter = WRITE-IN, then a single "Voids /
Blanks" column (skip). So the per-row number count after the ward/town label is
Dst + (1 + num_cand + 1 + 1) = Dst + num_cols. Party is assigned POSITIONALLY
from the hardcoded CAND map (canonical order); the column-letter count from the
"Wards/Towns Dst A B C ... Voids" header line is cross-checked against
num_cand.

Ward/town names appear only on the first ED row of a group and are carried
forward on continuation rows (which begin with the bare Dst number). Precinct
naming matches the committed 2022 Onondaga file EXACTLY: Syracuse city wards
-> "<ordinal> Ward <ED-int>" ("1ST WARD 01" -> "1st Ward 1"); towns -> "<TOWN>
<ED-int>" ("DEWITT 16" -> "DEWITT 16"; "VAN BUREN 11" -> "VAN BUREN 11").

Onondaga is WHOLLY inside NY-22 (one House table covers the whole county). It is
SPLIT across State Senate (SD-48 + SD-50 partition the county -- their GRAND
TOTALs 105,518 + 126,189 = 231,707 = President) and Assembly (AD-126 + 127 +
128 + 129 partition the county -- 54,806 + 70,960 + 57,495 + 48,446 = 231,707).
9 office-districts (detected from the row-0 title line):
  ELECTORS FOR PRESIDENT AND VICE PRESIDENT   President       Harris (DEM/WOR) / Trump (REP/CON)
  UNITED STATES SENATOR                      U.S. Senate     Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  REPRESENTATIVE IN CONGRESS - DISTRICT 22   U.S. House 22   John W. Mannion (DEM/WOR) / Brandon M. Williams (REP/CON)
  STATE SENATOR - 48TH DISTRICT              State Senate 48 Rachel May (DEM/WOR) / Caleb C. Slater (REP)   [no CON]
  STATE SENATOR - DISTRICT 50                State Senate 50 Christopher J. Ryan (DEM/WOR) / Nick Paro (REP/CON)
  MEMBER OF ASSEMBLY - DISTRICT 126          State Assembly 126  Ian Phillips (DEM/WOR) / John Lemondes Jr. (REP/CON)
  MEMBER OF ASSEMBLY - DISTRICT 127          State Assembly 127  Albert A. Stirpe, Jr. (DEM/WOR) / Timothy R. Kelly (REP/CON)
  MEMBER OF ASSEMBLY - DISTRICT 128          State Assembly 128  Pamela Jo Hunter (DEM/WOR) / Daniel A. Ciciarelli (REP/CON)
  MEMBER OF ASSEMBLY - DISTRICT 129          State Assembly 129  William B. Magnarelli (DEM)   [uncontested]
Non-canonical pages (Family Court Judge, City Court Judge, town/village
offices, Proposals) have no canonical title -> skipped. Candidate names via a
hardcoded CAND[(office,district,party)] map; cross-county siblings matched
EXACTLY: AD-126 -> Cayuga 2024 ("John Lemondes Jr." / "Ian Phillips"), AD-127 ->
Madison 2024 ("Albert A. Stirpe, Jr." / "Timothy R. Kelly" -- Madison keeps the
comma before Jr.; AD-126's Cayuga does NOT, matching each committed sibling),
SD-48 -> Cayuga 2024 ("Rachel May" / "Caleb C. Slater", no CON line); House 22
-> Cayuga/Cortland (Mannion/Williams); President/Senate -> standard. SD-50,
AD-128, AD-129 are Onondaga-only (no 2024 committed sibling) -> source names.
President "Kamala D. Harris and Tim Walz" / "Donald J. Trump and JD Vance" ->
VP mate dropped. WOR=Working Families, LAR=LaRouche.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON columns) -- exactly
#148 convention; emit one row per party-line column. Write-ins: the WRITE-IN
letter column is an aggregate -> ONE "Write-in" row (party empty) per
(precinct, office) when >0. Voids/Blanks omitted. 0-vote candidate rows omitted.
Numbers are comma-grouped ("1,066") -> strip.

Verification (all HARD):
  1. per data row: A (whole number) == sum(candidates) + write-ins + voids/blanks.
  2. per (office, district, party): precinct-sum == GRAND TOTAL row; write-in
     precinct-sum == GRAND TOTAL write-in.
  3. candidate surname PRESENCE in the page header text (the header is clean
     enough to confirm each candidate appears on the right office's pages).
  4. SD-48/50 split + AD-126/127/128/129 split disjoint + complete == President.
Run with uv (natural_pdf):  uv run python onondaga_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

from natural_pdf import PDF

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "ONONDAGA_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Onondaga.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__onondaga__precinct.csv"
)
COUNTY = "Onondaga"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "22"),
                ("State Senate", "48"), ("State Senate", "50"),
                ("State Assembly", "126"), ("State Assembly", "127"),
                ("State Assembly", "128"), ("State Assembly", "129")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
CANON_ORDER = ["DEM", "REP", "CON", "WOR", "LAR"]
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
    ("U.S. House", "22", "DEM"): "John W. Mannion",
    ("U.S. House", "22", "WOR"): "John W. Mannion",
    ("U.S. House", "22", "REP"): "Brandon M. Williams",
    ("U.S. House", "22", "CON"): "Brandon M. Williams",
    ("State Senate", "48", "DEM"): "Rachel May",
    ("State Senate", "48", "WOR"): "Rachel May",
    ("State Senate", "48", "REP"): "Caleb C. Slater",
    ("State Senate", "50", "DEM"): "Christopher J. Ryan",
    ("State Senate", "50", "WOR"): "Christopher J. Ryan",
    ("State Senate", "50", "REP"): "Nick Paro",
    ("State Senate", "50", "CON"): "Nick Paro",
    ("State Assembly", "126", "DEM"): "Ian Phillips",
    ("State Assembly", "126", "WOR"): "Ian Phillips",
    ("State Assembly", "126", "REP"): "John Lemondes Jr.",
    ("State Assembly", "126", "CON"): "John Lemondes Jr.",
    ("State Assembly", "127", "DEM"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "WOR"): "Albert A. Stirpe, Jr.",
    ("State Assembly", "127", "REP"): "Timothy R. Kelly",
    ("State Assembly", "127", "CON"): "Timothy R. Kelly",
    ("State Assembly", "128", "DEM"): "Pamela Jo Hunter",
    ("State Assembly", "128", "WOR"): "Pamela Jo Hunter",
    ("State Assembly", "128", "REP"): "Daniel A. Ciciarelli",
    ("State Assembly", "128", "CON"): "Daniel A. Ciciarelli",
    ("State Assembly", "129", "DEM"): "William B. Magnarelli",
}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def _office_of_title(title):
    t = (title or "").strip()
    if t.startswith("Summary --"):
        return None  # town-level rollup page -> skip (would double-count)
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    m = re.search(r"REPRESENTATIVE IN CONGRESS\s*-\s*DISTRICT\s*(\d+)", t)
    if m:
        return ("U.S. House", m.group(1))
    if "STATE SENATOR" in t:
        m = re.search(r"(\d+)", t)
        if m:
            return ("State Senate", m.group(1))
    m = re.search(r"MEMBER OF ASSEMBLY\s*-\s*DISTRICT\s*(\d+)", t)
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


def _ordinal(n):
    n = int(n)
    if 11 <= n % 100 <= 13:
        s = "th"
    elif n % 10 == 1:
        s = "st"
    elif n % 10 == 2:
        s = "nd"
    elif n % 10 == 3:
        s = "rd"
    else:
        s = "th"
    return f"{n}{s}"


def _precinct(label_tokens, dst):
    """label_tokens = ward/town tokens (upper); dst = ED string -> precinct name
    matching the 2022 Onondaga convention."""
    dst_int = int(dst)
    if "WARD" in label_tokens:
        m = re.match(r"(\d+)", label_tokens[0])
        return f"{_ordinal(m.group(1))} Ward {dst_int}"
    return " ".join(label_tokens) + f" {dst_int}"


def main():
    pdf = PDF(SRC_PATH)
    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)          # (office,district,party) -> precinct sum
    wisum = defaultdict(int)         # (office,district) -> write-in precinct sum
    anchor = {}                      # (office,district,party) -> GRAND TOTAL
    wi_anchor = {}                   # (office,district) -> GRAND TOTAL write-in
    od_seen = []
    sd_precincts = defaultdict(set)
    ad_precincts = defaultdict(set)
    pres_precincts = set()
    od_precincts = defaultdict(set)
    name_fail = []
    arith_fail = []
    name_checked = set()

    for pno in range(len(pdf.pages)):
        lines = [l for l in pdf.pages[pno].extract_text().split("\n") if l.strip()]
        if not lines:
            continue
        od = _office_of_title(lines[0])
        if od is None or od not in OFFICE_RANK:
            continue
        office, district = od
        if od not in od_seen:
            od_seen.append(od)
        parties = [p for p in CANON_ORDER if (office, district, p) in CAND]
        num_cand = len(parties)
        num_cols = num_cand + 3      # A + num_cand + WRITE-IN + Voids/Blanks
        # parse the "Wards/Towns Dst A B C ... Voids" header to get column letters
        col_letters = None
        for l in lines:
            if "Wards/Towns" in l and "Dst" in l:
                toks = l.split()
                # letters between "Dst" and "Voids"
                if "Dst" in toks and "Voids" in toks:
                    di = toks.index("Dst")
                    vi = toks.index("Voids")
                    col_letters = toks[di + 1:vi]
                break
        if col_letters is not None:
            # letters = [A, <cand...>, WRITE-IN-letter]; expect len-2 == num_cand
            if len(col_letters) - 2 != num_cand:
                name_fail.append(
                    f"{office} {district}: header letters {col_letters} -> "
                    f"{len(col_letters)-2} cand cols != CAND {num_cand}")
        # header text for surname-presence check (lines 1..6). Candidate names
        # appear ONLY on the first detail page of each office; continuation
        # ("Rows Continued") pages repeat only the column-letter header, so run
        # the surname check ONCE per office (first page seen).
        if od not in name_checked:
            name_checked.add(od)
            header_text = " ".join(lines[1:6]).lower()
            for p in parties:
                if _surname(CAND[(office, district, p)]) not in header_text:
                    name_fail.append(
                        f"{office} {district} {p}: surname "
                        f"{_surname(CAND[(office,district,p)])!r} not in page "
                        f"{pno} header")

        cur_label = None
        for l in lines[1:]:
            toks = l.split()
            if not toks:
                continue
            # split into leading non-numeric label + numeric run; require the
            # numeric run to extend to end of line (else header/footer noise)
            i = 0
            while i < len(toks) and not _is_num(toks[i]):
                i += 1
            if i == len(toks):
                continue  # no numbers
            label = toks[:i]
            nums = toks[i:]
            if not all(_is_num(t) for t in nums):
                continue  # trailing non-numeric -> header/footer noise
            vals = [_int(t) for t in nums]
            lab = " ".join(label).upper()
            if "TOTAL" in lab:
                # total row: A + cand + WI + Voids (no Dst)
                if len(vals) != num_cols:
                    continue
                if lab == "GRAND TOTAL":
                    for j, p in enumerate(parties):
                        anchor[(office, district, p)] = vals[1 + j]
                    wi_anchor[(office, district)] = vals[1 + num_cand]
                continue
            # data row: Dst + A + cand + WI + Voids
            if len(vals) != num_cols + 1:
                continue
            dst = vals[0]
            if dst > 999:  # a stray big number (not an ED)
                continue
            a_whole = vals[1]
            cand_vals = vals[2:2 + num_cand]
            wi = vals[2 + num_cand]
            voids = vals[-1]
            if a_whole != sum(cand_vals) + wi + voids:
                arith_fail.append((pno, lab or cur_label, dst, a_whole,
                                   sum(cand_vals), wi, voids))
            if label:
                cur_label = label
            if cur_label is None:
                continue
            prec = _precinct([t.upper() for t in cur_label], str(dst))
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            od_precincts[od].add(prec)
            if office == "President":
                pres_precincts.add(prec)
            elif office == "State Senate":
                sd_precincts[district].add(prec)
            elif office == "State Assembly":
                ad_precincts[district].add(prec)
            for j, p in enumerate(parties):
                v = cand_vals[j]
                psum[(office, district, p)] += v
                if v > 0 and (office, district, p) in CAND:
                    all_rows.append((prec, office, district, p,
                                     CAND[(office, district, p)], v))
            wisum[(office, district)] += wi
            if wi > 0:
                all_rows.append((prec, office, district, "", "Write-in", wi))

    # ---- HARD verification --------------------------------------------------
    hard = []
    for pno, lab, dst, a_whole, cs, wi, voids in arith_fail:
        hard.append(f"p{pno} {lab} ED {dst}: whole={a_whole} != "
                    f"cand{cs}+wi{wi}+voids{voids}={cs+wi+voids}")
    hard.extend(name_fail)
    for od in OFFICE_ORDER:
        office, district = od
        for p in CANON_ORDER:
            if (office, district, p) not in CAND:
                continue
            s = psum.get((office, district, p), 0)
            a = anchor.get((office, district, p))
            if a is None:
                hard.append(f"{od} {p}: no GRAND TOTAL anchor")
            elif s != a:
                hard.append(f"{od} {p}: precinct-sum={s} != GRAND TOTAL={a}")
        ws_ = wisum.get(od, 0)
        wa = wi_anchor.get(od)
        if wa is None:
            hard.append(f"{od} write-in: no GRAND TOTAL anchor")
        elif ws_ != wa:
            hard.append(f"{od} write-in: precinct-sum={ws_} != GRAND TOTAL={wa}")

    # SD-48/50 split + AD-126/127/128/129 split disjoint + complete == President
    sd_union = set()
    for d, ps in sd_precincts.items():
        sd_union |= ps
    if sd_union != pres_precincts:
        hard.append(f"SD split not complete: union={len(sd_union)} "
                    f"president={len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - sd_union)[:5]}")
    ad_union = set()
    for d, ps in ad_precincts.items():
        ad_union |= ps
    if ad_union != pres_precincts:
        hard.append(f"AD split not complete: union={len(ad_union)} "
                    f"president={len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - ad_union)[:5]}")
    for label, groups in (("SD", sd_precincts), ("AD", ad_precincts)):
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
        print(f"  {office} {district}: {', '.join(parts)} (GRAND TOTAL={a})")
    print(f"  SD split: {dict((d, len(ps)) for d, ps in sd_precincts.items())}")
    print(f"  AD split: {dict((d, len(ps)) for d, ps in ad_precincts.items())}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())