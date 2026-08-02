#!/usr/bin/env python3
"""Dedicated parser for Warren County 2024 general precinct results (PDF).

The Warren County BOE publishes an "Election Book" PDF (`Warren.pdf`, 48 pp) --
the SAME family as Monroe/Saratoga/Onondaga, and it extracts CLEANLY via
`extract_text()` (the old scan note "names garbage / needs Dst-column model"
was WRONG, an artifact of the shared RPP parser's approach; same situation as
Onondaga). Each contest = ONE detail page (per-ED rows with a `Dst` column) +
ONE `"Summary --"` page (a town-level rollup with NO `Dst` column, SKIPPED to
avoid double-count). Each detail page carries a `"TOWN/CITY TOTAL"` county row
at the TOP and a `"GRAND TOTAL"` row at the BOTTOM (identical values -- the
county grand total for that contest's coverage).

Each detail page repeats a column header whose data rows look like:
    BOLTON 1 1,330 566 38 635 71 7 13
    2 908 302 16 490 78 12 10            <- continuation (bare Dst, carry label)
    CITY OF GLENS FALLS 1 1,005 476 43 425 47 11 3
    1 1,445 809 52 490 57 28 9           <- Ward 2 ED 1 (Dst resets to 1)
Columns are letter-coded in FIXED order: A = WHOLE NUMBER (ballots cast, used
for the per-row arithmetic check, NOT emitted), then the candidate party lines,
then the last candidate letter = WRITE-IN, then a single "Voids / Blanks"
column (omitted). So a data row = label + Dst + (1 + num_cand + 1 + 1) numbers;
a total row = label + num_cols (no Dst).

PARTY IS PARSED PER-COLUMN FROM THE HEADER (NOT positional canonical). The
column order is NON-standard and VARIES by office: President/Senate/House are
DEM, WOR, REP, CON, [LAR]; SD-45 is REP, CON; AD-113 is DEM, REP, CON; AD-114
is REP, CON. The header text wraps across lines and the party parens land out
of reading order (e.g. President's "(CONSERVATIVE)" wraps to a line below
"WRITE-IN"), so naive text-order parsing misassigns. Instead the parser uses
pdfplumber WORD POSITIONS: each column letter (A-G, standalone) sits at a known
x, and each party paren is matched to the nearest column letter on its LEFT
within the letter-row at or above the paren ("row + x-range" matching,
validated for all 6 offices). Candidate letter list comes from the
"Wards/Towns Dst A B C D E F Voids" line (A=WHOLE NUMBER skipped, last
letter=WRITE-IN); num_cand = len(letters)-2 is cross-checked against the
hardcoded CAND map.

PRECINCT NAMING (the one real wrinkle vs Onondaga): Warren has TWO warded
municipalities -- City of Glens Falls and Town of Queensbury -- whose wards
are NOT a separate column; the `Dst` column carries only the ED, and a new
ward begins whenever Dst resets to 1 (a ward's first ED is always 1, and EDs
are sequential within a ward, so Dst==1 unambiguously starts a new ward). The
rule "Dst==1 -> new ward" is VALIDATED against the committed 2022 Warren file:
it reproduces 2022 Queensbury (W1 1-5 / W2 1-4 / W3 1-4 / W4 1-3) AND 2022
Glens Falls (W1 1 / W2 1-2 / W3 1-2 / W4 1 / W5 1-2) exactly. A group with >1
ward is named "<Town> - Ward <ward> <ED>"; a single-ward group is "<Town>
<ED>". Town names are title-cased with the "City of " prefix stripped,
matching the 2022 file ("Glens Falls", "Queensbury", "Bolton", "Lake George",
"Stony Creek", ...). The 2024 ED set differs from 2022 in several towns
(Bolton/Horicon/Johnsburg collapsed to 1 ED, Warrensburg 3->2, Glens Falls
ward/ED shifts) -- real 2024 ED consolidation, NOT a parser bug.

Warren is WHOLLY inside NY-21 / SD-45 (House 21 and State Senate 45 each cover
the whole county). It is SPLIT across State Assembly: AD-113 (Carrie Woerner
DEM vs Jeremy Messina REP/CON) = City of Glens Falls only (6,851 ballots),
AD-114 (Matthew J. Simpson REP/CON uncontested) = all other towns (29,467);
6,851 + 29,467 = 36,318 = President. 6 office-districts (detected from the
row-0 title line):
  PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES  President    Harris (DEM/WOR) / Trump (REP/CON)
  UNITED STATES SENATOR                             U.S. Senate  Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  REPRESENTATIVE IN CONGRESS (no district in title) U.S. House 21 Paula Collins (DEM/WOR) / Elise M. Stefanik (REP/CON)
  STATE SENATOR (no district in title)              State Senate 45 Daniel G. Stec (REP/CON) [uncontested, no DEM]
  MEMBER OF ASSEMBLY (113TH)                        State Assembly 113 Carrie Woerner (DEM) / Jeremy Messina (REP/CON)
  MEMBER OF ASSEMBLY (114TH)                        State Assembly 114 Matthew J. Simpson (REP/CON) [uncontested, no DEM]
House district (21) and State Senate district (45) are NOT in the title -- they
are inferred from the candidates (Stefanik=NY-21, Stec=SD-45) and hardcoded.
Non-canonical pages (City Court Judge, Town Council Member, Town Supervisor,
Town Justice, Library Trustee, Propositions) have no canonical title -> skipped.

Candidate names via a hardcoded CAND[(office,district,party)] map, matched
EXACTLY to committed siblings: Stec -> Washington (SD-45), Woerner/Messina/
Simpson -> Saratoga (AD-113/114), Collins/Stefanik -> Saratoga/Schoharie/
Montgomery (House 21); President/Senate standard. Warren prints "KAMALA
HARRIS" (no middle initial) but the emitted name is "Kamala D. Harris" per the
CAND map. President VP mate dropped. WOR=Working Families, LAR=LaRouche.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON columns) -- exactly
#148 convention; emit one row per party-line column. Write-ins: the WRITE-IN
letter column is an aggregate -> ONE "Write-in" row (party empty) per
(precinct, office) when >0. Voids/Blanks omitted. 0-vote rows omitted.
Numbers are comma-grouped ("1,330") -> strip.

Verification (all HARD):
  1. per data row: A (whole number) == sum(candidates) + write-in + voids/blanks.
  2. per (office, district, party): precinct-sum == GRAND TOTAL row (== TOWN/CITY
     TOTAL row, verified equal); write-in precinct-sum == grand write-in.
  3. candidate surname PRESENCE in the page header text (checked ONCE per office).
  4. AD-113/114 split disjoint + complete == President.
Run with uv (pdfplumber):  uv run python warren_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "WARREN_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Warren.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__warren__precinct.csv"
)
COUNTY = "Warren"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
                ("State Senate", "45"),
                ("State Assembly", "113"), ("State Assembly", "114")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
# party rank for output row ordering (canonical, regardless of source col order)
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
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "WOR"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "45", "REP"): "Daniel G. Stec",
    ("State Senate", "45", "CON"): "Daniel G. Stec",
    ("State Assembly", "113", "DEM"): "Carrie Woerner",
    ("State Assembly", "113", "REP"): "Jeremy Messina",
    ("State Assembly", "113", "CON"): "Jeremy Messina",
    ("State Assembly", "114", "REP"): "Matthew J. Simpson",
    ("State Assembly", "114", "CON"): "Matthew J. Simpson",
}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}
PARTY_OF = [("DEMOCRAT", "DEM"), ("REPUBLICAN", "REP"), ("CONSERV", "CON"),
            ("WORKING", "WOR"), ("FAMILIES", "WOR"), ("LAROUCHE", "LAR")]


def _office_of_title(title):
    t = (title or "").strip()
    if t.startswith("Summary --"):
        return None
    if "PRESIDENT" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR"):
        return ("U.S. Senate", "")
    if "REPRESENTATIVE IN CONGRESS" in t:
        return ("U.S. House", "21")      # Warren wholly in NY-21 (Stefanik)
    if "STATE SENATOR" in t:
        return ("State Senate", "45")   # Warren wholly in SD-45 (Stec)
    m = re.search(r"MEMBER OF ASSEMBLY\s*\((\d+)\w*\)", t)
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


def _town_name(label_tokens):
    lab = " ".join(label_tokens)               # uppercase, e.g. "CITY OF GLENS FALLS"
    m = re.match(r"CITY OF\s+(.+)", lab)
    rest = m.group(1) if m else lab
    return rest.title()


def _party_of_paren(s):
    u = s.upper()
    for key, party in PARTY_OF:
        if key in u:
            return party
    return None


def _header_letter_party(page):
    """Map each column letter (A-G) -> party, parsed from the page header by
    word positions (row + x-range matching; the header text wraps so reading
    order is unreliable). Returns {letter: party} for candidate letters only
    (A=WHOLE NUMBER and the WRITE-IN letter have no party)."""
    words = page.extract_words()
    wt = [w for w in words if w["text"] == "Wards/Towns"]
    if not wt:
        return {}, []
    cuty = wt[0]["top"]
    letters = [w for w in words if re.match(r"^[A-G]$", w["text"]) and w["top"] < cuty]
    parens = [w for w in words if ("(" in w["text"] or ")" in w["text"]) and w["top"] < cuty]
    # cluster letters into rows by top
    letters.sort(key=lambda w: (w["top"], w["x0"]))
    rows = []
    for w in letters:
        for r in rows:
            if abs(r[0] - w["top"]) < 8:
                r[1].append(w)
                break
        else:
            rows.append([w["top"], [w]])
    rows.sort(key=lambda r: r[0])
    # build x-ranges per row: (row_top, x_start, x_end, letter)
    ranges = []
    for rtop, lets in rows:
        lets.sort(key=lambda w: w["x0"])
        for i, w in enumerate(lets):
            x_end = lets[i + 1]["x0"] if i + 1 < len(lets) else 10 ** 9
            ranges.append((rtop, w["x0"], x_end, w["text"]))
    frags = defaultdict(list)
    for p in parens:
        cand = [r for r in ranges if r[0] <= p["top"] + 3]
        if not cand:
            continue
        cand.sort(key=lambda r: r[0], reverse=True)
        chosen = None
        for r in cand:
            if r[1] - 2 <= p["x0"] < r[2]:
                chosen = r
                break
        if chosen is None:
            continue
        frags[chosen[3]].append((p["top"], p["x0"], p["text"]))
    letter_party = {}
    for L, fl in frags.items():
        fl.sort(key=lambda t: (t[0], t[1]))
        s = " ".join(t[2] for t in fl)
        party = _party_of_paren(s)
        if party:
            letter_party[L] = party
    return letter_party, rows


def _col_letters_from_header(text_lines):
    for l in text_lines:
        if "Wards/Towns" in l and "Dst" in l:
            toks = l.split()
            if "Dst" in toks and "Voids" in toks:
                di = toks.index("Dst")
                vi = toks.index("Voids")
                return toks[di + 1:vi]
    return None


def main():
    pdf = pdfplumber.open(SRC_PATH)
    data_rows = []     # (office, district, group, ward, dst, party_vals, wi, voids)
    # party_vals is a list aligned to the candidate letters (parties in col order)
    psum = defaultdict(int)
    wisum = defaultdict(int)
    grand = {}          # (office,district) -> [A, cand..., wi, voids] (col order)
    grand_parties = {}  # (office,district) -> [parties in col order]
    wi_grand = {}
    name_fail = []
    arith_fail = []
    name_checked = set()
    od_seen = []
    ad_precincts = defaultdict(set)
    pres_precincts = set()
    od_precincts = defaultdict(set)
    group_max_ward = defaultdict(int)
    group_town = {}

    for pno in range(len(pdf.pages)):
        page = pdf.pages[pno]
        raw = page.extract_text()
        lines = [l for l in raw.split("\n") if l.strip()]
        if not lines:
            continue
        od = _office_of_title(lines[0])
        if od is None or od not in OFFICE_RANK:
            continue
        office, district = od
        if od not in od_seen:
            od_seen.append(od)
        col_letters = _col_letters_from_header(lines)
        if col_letters is None:
            name_fail.append(f"{od}: no Wards/Towns Dst header")
            continue
        # candidate letters = letters[1:-1] (exclude A=WHOLE NUMBER, last=WRITE-IN)
        cand_letters = col_letters[1:-1]
        num_cand = len(cand_letters)
        num_cols = num_cand + 3
        # expected parties from CAND map (set), for cross-check
        cand_parties_set = {p for p in ("DEM", "REP", "CON", "WOR", "LAR")
                           if (office, district, p) in CAND}
        if num_cand != len(cand_parties_set):
            name_fail.append(f"{od}: header cand cols {num_cand} != CAND "
                             f"{len(cand_parties_set)} ({col_letters})")
        letter_party, _ = _header_letter_party(page)
        parties = [letter_party.get(L) for L in cand_letters]
        for j, p in enumerate(parties):
            if p is None:
                name_fail.append(f"{od}: column {cand_letters[j]} has no party "
                                 f"in header")
            elif p not in cand_parties_set:
                name_fail.append(f"{od}: column {cand_letters[j]} party {p} not "
                                 f"in CAND set {cand_parties_set}")
        if od not in name_checked:
            name_checked.add(od)
            header_text = " ".join(lines[1:6]).lower()
            for p in cand_parties_set:
                if _surname(CAND[(office, district, p)]) not in header_text:
                    name_fail.append(f"{od} {p}: surname "
                                     f"{_surname(CAND[(office,district,p)])!r} not "
                                     f"in page {pno} header")

        cur_group = None
        ward = 0
        for l in lines[1:]:
            toks = l.split()
            if not toks:
                continue
            i = 0
            while i < len(toks) and not _is_num(toks[i]):
                i += 1
            if i == len(toks):
                continue
            label = toks[:i]
            nums = toks[i:]
            if not all(_is_num(t) for t in nums):
                continue
            vals = [_int(t) for t in nums]
            lab = " ".join(label).upper()
            if "TOTAL" in lab:
                if len(vals) != num_cols:
                    continue
                key = od
                if key in grand:
                    if vals != grand[key]:
                        name_fail.append(f"{od}: total rows differ "
                                         f"{grand[key]} vs {vals}")
                else:
                    grand[key] = vals
                    grand_parties[key] = parties
                    wi_grand[key] = vals[1 + num_cand]
                continue
            if len(vals) != num_cols + 1:
                continue
            dst = vals[0]
            if dst > 999:
                continue
            a_whole = vals[1]
            cand_vals = vals[2:2 + num_cand]
            wi = vals[2 + num_cand]
            voids = vals[-1]
            if a_whole != sum(cand_vals) + wi + voids:
                arith_fail.append((pno, lab or (cur_group[-1] if cur_group else "?"),
                                   dst, a_whole, sum(cand_vals), wi, voids))
            if label:
                cur_group = (office, district, tuple(t.upper() for t in label))
                ward = 0
                group_town[cur_group] = _town_name([t.upper() for t in label])
            if cur_group is None:
                continue
            if dst == 1:
                ward += 1
            group_max_ward[cur_group] = max(group_max_ward[cur_group], ward)
            data_rows.append((office, district, cur_group, ward, dst,
                              parties, cand_vals, wi, voids))

    # ---- name precincts + emit --------------------------------------------
    all_rows = []
    prec_order = []
    seen_prec = set()
    for office, district, group, ward, dst, parties, cand_vals, wi, voids in data_rows:
        town = group_town[group]
        maxw = group_max_ward[group]
        prec = (f"{town} - Ward {ward} {dst}" if maxw > 1
                else f"{town} {dst}")
        od = (office, district)
        if prec not in seen_prec:
            seen_prec.add(prec)
            prec_order.append(prec)
        od_precincts[od].add(prec)
        if office == "President":
            pres_precincts.add(prec)
        elif office == "State Assembly":
            ad_precincts[district].add(prec)
        for j, p in enumerate(parties):
            if p is None or (office, district, p) not in CAND:
                continue
            v = cand_vals[j]
            psum[(office, district, p)] += v
            if v > 0:
                all_rows.append((prec, office, district, p,
                                 CAND[(office, district, p)], v))
        wisum[(office, district)] += wi
        if wi > 0:
            all_rows.append((prec, office, district, "", "Write-in", wi))

    # ---- HARD verification ------------------------------------------------
    hard = []
    for pno, lab, dst, a_whole, cs, wi, voids in arith_fail:
        hard.append(f"p{pno} {lab} ED {dst}: whole={a_whole} != "
                    f"cand{cs}+wi{wi}+voids{voids}={cs+wi+voids}")
    hard.extend(name_fail)
    for od in OFFICE_ORDER:
        g = grand.get(od)
        if g is None:
            hard.append(f"{od}: no GRAND TOTAL anchor")
            continue
        parties = grand_parties[od]
        for j, p in enumerate(parties):
            if p is None or (od[0], od[1], p) not in CAND:
                continue
            s = psum.get((od[0], od[1], p), 0)
            if s != g[1 + j]:
                hard.append(f"{od} {p}: precinct-sum={s} != GRAND TOTAL={g[1+j]}")
        ws_ = wisum.get(od, 0)
        if ws_ != wi_grand[od]:
            hard.append(f"{od} write-in: precinct-sum={ws_} != GRAND TOTAL={wi_grand[od]}")

    ad_union = set()
    for d, ps in ad_precincts.items():
        ad_union |= ps
    if ad_union != pres_precincts:
        hard.append(f"AD split not complete: union={len(ad_union)} "
                    f"president={len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - ad_union)[:5]}")
    ds = list(ad_precincts)
    overlap = set()
    for a in range(len(ds)):
        for b in range(a + 1, len(ds)):
            overlap |= ad_precincts[ds[a]] & ad_precincts[ds[b]]
    if overlap:
        hard.append(f"AD split overlap: {sorted(overlap)[:5]}")

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
        g = grand.get(od)
        a = g[1] if g else "?"
        print(f"  {office} {district}: {', '.join(parts)} (GRAND TOTAL={a})")
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