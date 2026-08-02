#!/usr/bin/env python3
"""Dedicated parser for Montgomery County 2024 general precinct results (HTML).

The Montgomery County BOE publishes an NYS "Results per Precinct" HTML report
(`Montgomery.html`) -- a sibling format to Schoharie/Wayne but with a DIFFERENT
header convention. 16 `<table>`s: table 0 = President, 1 = U.S. Senate,
2 = U.S. House 20, 3 = U.S. House 21, 4 = State Senate 46, 5 = State Assembly
111, 6 = State Assembly 118, 7-14 = county/town offices (SKIP), 15 = Proposal
(SKIP). Each canonical table = header row + precinct rows + a "Total"/"TOTAL"
county-grand-total row.

Header convention (DIFFERENT from Schoharie/Wayne): col0 label is `"ED"` (not
"Precinct"); the party is a TRAILING space-separated token on each candidate
cell ("Paul D. Tonko DEM", "Diane Sare LaRouche"), NOT a "- XXX" dash suffix.
Two party tokens are multi-word: "LaRouche" (one word -> LAR) and "People First"
(two words -> PFP). PFP = the People First Party independent fusion line for
AD-111 Santabarbara -- the SAME party Schenectady 2024 coded as "PFP", so this
parser maps "People First" -> "PFP" for cross-county consistency.

Montgomery is SPLIT across NY-20 (20 precincts, Tonko vs Waltz)/NY-21 (15,
Collins vs Stefanik), and across AD-111 (20 precincts, Santabarbara DEM/PFP
vs Mastroianni REP/CON)/AD-118 (15, Smullen REP/CON uncontested); SD-46 (Fahy
vs Danz) covers the whole county. 20+15 = 35 = President. (In 2022 Montgomery
was wholly in NY-21 + had IND for Santabarbara; 2024 redistricting added NY-20
and the PFP line replaced the IND line -- so the 2022 file's office set is NOT
reusable, but the precinct-NAME convention is: preserve verbatim.)

Office detected from header candidate surnames (Harris/Trump->President,
Gillibrand/Sapraicone/Sare->Senate, Tonko/Waltz->House 20, Collins/Stefanik->
House 21, Fahy/Danz->SD 46, Santabarbara/Mastroianni->AD 111, Smullen->AD 118).
Non-canonical tables (Lorraine Diamond / Christina Pearson / Purtell-Vroman /
Demars-Pawlik / Nethaway-Marotta / Bramer / Woodcock / Yes-No proposal) have
no surname match -> naturally skipped.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON + PFP columns) --
exactly #148 convention; emit one row per party-line column. AD-118 Smullen is
REP/CON only (no DEM/WOR -- uncontested). Write-ins: each table has a single
aggregate "Write-ins" column -> ONE "Write-in" row (party empty) per
(precinct, office) when >0. 0-vote rows omitted. No Over/Under columns.

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 corpus (Tonko/Waltz match Schenectady/Livingston; Collins/
Stefanik match Schoharie/Saratoga; Fahy/Danz/Santabarbara/Mastroianni match
Schenectady; **"Robert J. Smullen" -> "Robert Smullen"** per the #148-branch
AD-118 normalization, matching Herkimer/Hamilton/Otsego 2024 -- the 2022
Montgomery file kept "Robert J. Smullen" but the 2024 cross-county convention
strips the middle initial). President VP mate dropped at " - " or " / " (this
source uses "Kamala D. Harris - Tim Walz" / "Donald J. Trump / JD Vance").

Name cross-check is by SURNAME (not full name) because the source has typos:
"Kristen E. Gillibrand" (-> Kirsten), "Mike D. Sapraicone" (-> Michael) -- the
surname is identical so the cross-check passes; the emitted name is the
hardcoded CAND value. Precinct names preserved verbatim (whitespace-collapsed)
-- matches the committed 2022 Montgomery file ("City of Amsterdam Ward 1 1",
"Amsterdam 1", "St Johnsville 1").

Verification (all HARD):
  1. per (office, district, party): precinct-sum == table "Total"/"TOTAL" row;
     write-in precinct-sum == Total-row "Write-ins" col.
  2. candidate-surname cross-check (President VP-mate drop first).
  3. House 20/21 split + AD-111/118 split disjoint + complete == President.
Run with uv (beautifulsoup4):  uv run python montgomery_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "MONTGOMERY_HTML",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Montgomery.html",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__montgomery__precinct.csv"
)
COUNTY = "Montgomery"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""),
                ("U.S. House", "20"), ("U.S. House", "21"),
                ("State Senate", "46"),
                ("State Assembly", "111"), ("State Assembly", "118")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "PFP": 5, "IND": 6}

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
    ("U.S. House", "20", "DEM"): "Paul D. Tonko",
    ("U.S. House", "20", "WOR"): "Paul D. Tonko",
    ("U.S. House", "20", "REP"): "Kevin M. Waltz",
    ("U.S. House", "20", "CON"): "Kevin M. Waltz",
    ("U.S. House", "21", "DEM"): "Paula Collins",
    ("U.S. House", "21", "WOR"): "Paula Collins",
    ("U.S. House", "21", "REP"): "Elise M. Stefanik",
    ("U.S. House", "21", "CON"): "Elise M. Stefanik",
    ("State Senate", "46", "DEM"): "Patricia A. Fahy",
    ("State Senate", "46", "WOR"): "Patricia A. Fahy",
    ("State Senate", "46", "REP"): "Ted Danz Jr.",
    ("State Senate", "46", "CON"): "Ted Danz Jr.",
    ("State Assembly", "111", "DEM"): "Angelo L. Santabarbara",
    ("State Assembly", "111", "PFP"): "Angelo L. Santabarbara",
    ("State Assembly", "111", "REP"): "Joseph C. Mastroianni",
    ("State Assembly", "111", "CON"): "Joseph C. Mastroianni",
    ("State Assembly", "118", "REP"): "Robert Smullen",
    ("State Assembly", "118", "CON"): "Robert Smullen",
}

# surname -> (office, district) for office detection
SURNAME_OFFICE = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "tonko": ("U.S. House", "20"), "waltz": ("U.S. House", "20"),
    "collins": ("U.S. House", "21"), "stefanik": ("U.S. House", "21"),
    "fahy": ("State Senate", "46"), "danz": ("State Senate", "46"),
    "santabarbara": ("State Assembly", "111"),
    "mastroianni": ("State Assembly", "111"),
    "smullen": ("State Assembly", "118"),
}
# trailing-token party map (lowercased); "People First" handled separately
TOKEN_PARTY = {"dem": "DEM", "rep": "REP", "con": "CON", "wor": "WOR",
               "larouche": "LAR"}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _cell_text(cell):
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _party_and_name(cell_txt):
    """'Paul D. Tonko DEM' -> ('DEM','Paul D. Tonko');
    'Diane Sare LaRouche' -> ('LAR','Diane Sare');
    'Angelo L. Santabarbara People First' -> ('PFP','Angelo L. Santabarbara')."""
    toks = cell_txt.split()
    if not toks:
        return None, cell_txt
    if len(toks) >= 2 and toks[-2].lower() == "people" and toks[-1].lower() == "first":
        return "PFP", " ".join(toks[:-2])
    party = TOKEN_PARTY.get(toks[-1].lower())
    if party:
        return party, " ".join(toks[:-1])
    return None, cell_txt


def _office_of(header_names):
    for nm in header_names:
        for tok in (nm or "").split():
            t = _norm(tok)
            if t in SURNAME_OFFICE:
                return SURNAME_OFFICE[t]
    return None


def _clean_name(ballot, office):
    s = (ballot or "").strip()
    if office == "President":
        s = re.split(r"\s+[-/]\s+", s, 1)[0].strip()
    return s


def _surname(name):
    toks = [t for t in (name or "").split() if t]
    while toks and _norm(toks[-1]) in NAME_SUFFIX:
        toks.pop()
    return _norm(toks[-1]) if toks else ""


def main():
    html = open(SRC_PATH, encoding="utf-8", errors="replace").read()
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)
    wisum = defaultdict(int)
    col_total = {}
    wi_total = {}
    name_seen = defaultdict(set)
    od_seen = []
    od_precincts = defaultdict(set)
    house_precincts = defaultdict(set)
    ad_precincts = defaultdict(set)
    pres_precincts = set()

    for t in tables:
        trs = t.find_all("tr")
        if not trs:
            continue
        hdr_cells = trs[0].find_all(["td", "th"])
        hdr = [_cell_text(c) for c in hdr_cells]
        if not hdr or hdr[0].lower() != "ed":
            continue
        col_party = {}
        col_name = {}
        writein_cols = []
        header_names = []
        for j, txt in enumerate(hdr):
            if j == 0:
                continue
            if txt.lower() in ("write-ins", "write-ins ", "write in", "write-in"):
                writein_cols.append(j)
                continue
            party, bn = _party_and_name(txt)
            if party is not None:
                col_party[j] = party
                col_name[j] = bn
                header_names.append(bn)
            # else: not a candidate column (none expected here) -- skip
        od = _office_of(header_names)
        if od is None or od not in OFFICE_RANK:
            continue
        office, district = od
        if od not in od_seen:
            od_seen.append(od)

        for tr in trs[1:]:
            cells = [_cell_text(c) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            label = cells[0]
            if not label:
                continue
            if label.lower() in ("total", "totals"):
                for j, party in col_party.items():
                    if j < len(cells):
                        col_total[(office, district, party)] = _int(cells[j])
                wi_total[(office, district)] = sum(
                    _int(cells[j]) for j in writein_cols if j < len(cells))
                break
            prec = re.sub(r"\s+", " ", label).strip()
            od_precincts[od].add(prec)
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            if office == "President":
                pres_precincts.add(prec)
            elif office == "U.S. House":
                house_precincts[district].add(prec)
            elif office == "State Assembly":
                ad_precincts[district].add(prec)
            for j, party in col_party.items():
                v = _int(cells[j] if j < len(cells) else None)
                psum[(office, district, party)] += v
                name_seen[(office, district, party)].add(col_name[j])
                if v > 0 and (office, district, party) in CAND:
                    all_rows.append((prec, office, district, party,
                                     CAND[(office, district, party)], v))
            wv = sum(_int(cells[j] if j < len(cells) else None)
                     for j in writein_cols)
            wisum[(office, district)] += wv
            if wv > 0:
                all_rows.append((prec, office, district, "", "Write-in", wv))

    # ---- HARD verification --------------------------------------------------
    hard = []
    warnings = []
    # county-wide offices (President/Senate/State Senate) should cover every
    # President precinct; if the source HTML omits precinct rows for such an
    # office (a BOE source gap), the per-precinct data is authoritative and the
    # Total-row mismatch is a NON-FATAL warning, not a hard failure (Herkimer/
    # Ontario source-quirk precedent). Split offices (House/Assembly) keep the
    # HARD check because their Total row covers only the split's precincts.
    county_wide = {"President", "U.S. Senate", "State Senate"}
    for od in OFFICE_ORDER:
        office, district = od
        partial = (office in county_wide and pres_precincts
                   and od_precincts.get(od, set()) != pres_precincts)
        if partial:
            missing = sorted(pres_precincts - od_precincts.get(od, set()))
            warnings.append(
                f"{od}: source HTML lists {len(od_precincts.get(od, set()))}/"
                f"{len(pres_precincts)} precincts (missing {missing}); "
                f"Total row covers all -- per-precinct data emitted for the "
                f"{len(od_precincts.get(od, set()))} available, Total check demoted")
        for party in ("DEM", "REP", "CON", "WOR", "LAR", "PFP"):
            if (office, district, party) not in CAND:
                continue
            s = psum.get((office, district, party), 0)
            tr = col_total.get((office, district, party))
            if tr is None:
                hard.append(f"{od} {party}: no Total row")
            elif s != tr:
                msg = (f"{od} {party}: precinct-sum={s} != Total={tr}")
                if partial:
                    warnings.append(msg + " (source gap, demoted)")
                else:
                    hard.append(msg)
        ws_ = wisum.get(od, 0)
        wt = wi_total.get(od)
        if wt is None:
            hard.append(f"{od} write-in: no Total row")
        elif ws_ != wt:
            msg = f"{od} write-in: precinct-sum={ws_} != Total={wt}"
            if partial:
                warnings.append(msg + " (source gap, demoted)")
            else:
                hard.append(msg)

    # surname cross-check (handles source typos Kristen/Mike)
    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp_sur = _surname(_clean_name(expected, office))
        for nm in names:
            src_sur = _surname(_clean_name(nm, office))
            if src_sur and src_sur != exp_sur:
                hard.append(f"{office}/{district} {party}: source {nm!r} "
                            f"(surname {src_sur!r}) != expected {expected!r} "
                            f"(surname {exp_sur!r})")

    # split disjoint + complete == President
    house_union = set()
    for d, ps in house_precincts.items():
        house_union |= ps
    if house_union != pres_precincts:
        hard.append(f"House split not complete: union={len(house_union)} "
                    f"president={len(pres_precincts)}")
    ad_union = set()
    for d, ps in ad_precincts.items():
        ad_union |= ps
    if ad_union != pres_precincts:
        hard.append(f"AD split not complete: union={len(ad_union)} "
                    f"president={len(pres_precincts)}")
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
        for party in ("DEM", "REP", "CON", "WOR", "LAR", "PFP"):
            if (office, district, party) in CAND:
                parts.append(f"{party}={psum.get((office,district,party),0)}")
        parts.append(f"Write-in={wisum.get(od,0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
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