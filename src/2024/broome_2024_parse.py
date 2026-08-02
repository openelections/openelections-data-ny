#!/usr/bin/env python3
"""Dedicated parser for Broome County 2024 general precinct results (PDF).

The Broome County BOE publishes the NYS "Statement Of Votes Cast -- Subtotals
by City Town and District" PDF (`Broome.pdf`, 103 pp), which extracts CLEANLY
via pdfplumber `extract_text()`. Each canonical contest spans several pages of
per-election-district rows, each preceded by an upright column header:

    Kamala D. Donald J. Donald J. Kamala D.
    Harris & Trump & Trump & Harris &
    Election District Tim JD JD Tim
    Walz Vance Vance Walz Write-ins OverVotes UnderVotes Whole Number Eligible
    DEM REP CON WOR (Total) (Void) (Blank) (Ballots Cast) Voters Turnout (%)
    City of Binghamton
    City Binghamton 1 215 114 13 22 3 3 4 374 500 74.80%

The candidate names are printed UPRIGHT (not rotated), so they extract cleanly
(unlike the Westchester/Onondaga Election-Book family). The upright party-code
row gives the candidate columns in ballot order, followed by (Total)/(Scatter)
= aggregate write-ins, (Void) = overvotes, (Blank) = undervotes, (Ballots Cast)
= whole number, Voters = eligible, Turnout (%). So a DATA row is:

    <label> <ED> <cand_0>..<cand_{n-1}> <write-ins> <void> <blank> <ballots> <voters> <turnout%>

=> n_cand + 7 numeric tokens (the last is "NN.NN%"). Town subtotals and the
county "COUNTY / TOTALS" grand-total row have NO ED => n_cand + 6 numerics, so
they are cleanly distinguished from data rows by token count and skipped
(subtotals) or captured (the COUNTY TOTALS anchor, for verification).

Broome's 9 canonical office-districts (from the "Vote for" title lines):
  PRESIDENTIAL ELECTORS ...                         President       Harris (DEM/WOR) / Trump (REP/CON)
  UNITED STATES SENATOR                             U.S. Senate     Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  REPRESENTATIVE IN CONGRESS, 19TH ...              U.S. House 19   Josh Riley (DEM/WOR) / Marcus Molinaro (REP/CON)
  STATE SENATOR, 51st SENATE DISTRICT               State Senate 51 Michele Frazier (DEM/WOR) / Peter Oberacker (REP/CON)
  STATE SENATOR, 52nd SENATE DISTRICT               State Senate 52 Lea Webb (DEM/WOR) / Michael Sigler (REP/"Local 607")
  MEMBER OF ASSEMBLY, 121st ...                     State Assembly 121  Vicki Davis (DEM) / Joe Angelino (REP/CON)
  MEMBER OF ASSEMBLY, 123rd ...                     State Assembly 123  Donna Lupardo (DEM/WOR) / Lisa M. OKeefe (REP/CON/ECO)
  MEMBER OF ASSEMBLY, 124th ...                     State Assembly 124  Christopher S. Friend (REP/CON)  [uncontested]
  MEMBER OF ASSEMBLY, 131st ...                     State Assembly 131  Jeff Gallahan (REP/CON)  [uncontested]

Non-canonical pages (County Executive, Family Court Judge, County Legislator,
town/village offices, the "PRESIDENTIAL WRITE-IN CANDIDATES" scatter breakdown)
have no canonical title -> skipped. Candidate names via a hardcoded
CAND[(office,district,party)] map; cross-county siblings matched EXACTLY:
SD-52 -> Cortland 2024 ("Lea Webb" / "Michael Sigler" with party "Local 607"
-- Sigler's independent line, verbatim as Cortland records it); AD-123 ->
committed siblings ("Donna Lupardo" / "Lisa M. OKeefe"); House 19 / SD-51 /
AD-121 / AD-124 / AD-131 -> committed sibling spellings. President/Senate ->
standard. WOR=Working Families, LAR=LaRouche, ECO and "Local 607" are
independent lines kept verbatim (per the Cortland SD-52 convention).

NOTE on SD-52: Sigler has REP + "Local 607" (NO Conservative line); Webb has
DEM + WOR. Always trust the source party row, not a fusion assumption.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON + ... columns) --
exactly #148 convention; emit one row per party-line column. Write-ins: the
(Total)/(Scatter) column is an aggregate -> ONE "Write-in" row (party empty)
per (precinct, office) when >0. Voids/Blanks (over/undervotes) omitted.
0-vote candidate rows omitted. Numbers are comma-grouped ("1,152") -> strip.

Precinct naming uses the upright section header ("City of Binghamton" /
"Town of Barker") + ED number, matching the 2022 Broome convention minus the
"LD N" suffix (which the 2024 subtotal source does not carry): "City of
Binghamton 1", "Town of Barker 1".

Verification (all HARD):
  1. per data row: ballots == sum(candidates) + write-ins + void + blank.
  2. per (office, district, party): precinct-sum == COUNTY TOTALS anchor;
     write-in precinct-sum == COUNTY TOTALS write-in.
  3. candidate surname PRESENCE in the upright page header text.
  4. SD-51/52 split + AD-121/123/124/131 split + House 19 each disjoint +
     complete (precinct SET) == President precinct set.

Run with uv:  uv run python broome_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "BROOME_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Broome.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__broome__precinct.csv"
)
COUNTY = "Broome"

OFFICE_ORDER = [
    ("President", ""),
    ("U.S. Senate", ""),
    ("U.S. House", "19"),
    ("State Senate", "51"),
    ("State Senate", "52"),
    ("State Assembly", "121"),
    ("State Assembly", "123"),
    ("State Assembly", "124"),
    ("State Assembly", "131"),
]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}

# Candidate party-line columns in source ballot order, per office-district.
PARTIES_BY_OD = {
    ("President", ""): ["DEM", "REP", "CON", "WOR"],
    ("U.S. Senate", ""): ["DEM", "REP", "CON", "WOR", "LAR"],
    ("U.S. House", "19"): ["DEM", "REP", "CON", "WOR"],
    ("State Senate", "51"): ["DEM", "REP", "CON", "WOR"],
    ("State Senate", "52"): ["DEM", "REP", "WOR", "Local 607"],
    ("State Assembly", "121"): ["DEM", "REP", "CON"],
    ("State Assembly", "123"): ["DEM", "REP", "CON", "WOR", "ECO"],
    ("State Assembly", "124"): ["REP", "CON"],
    ("State Assembly", "131"): ["REP", "CON"],
}
# Output party sort rank (canonical-ish; "Local 607"/ECO after the majors).
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "ECO": 5,
              "Local 607": 6}

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
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Senate", "52", "DEM"): "Lea Webb",
    ("State Senate", "52", "WOR"): "Lea Webb",
    ("State Senate", "52", "REP"): "Michael Sigler",
    ("State Senate", "52", "Local 607"): "Michael Sigler",
    ("State Assembly", "121", "DEM"): "Vicki Davis",
    ("State Assembly", "121", "REP"): "Joe Angelino",
    ("State Assembly", "121", "CON"): "Joe Angelino",
    ("State Assembly", "123", "DEM"): "Donna Lupardo",
    ("State Assembly", "123", "WOR"): "Donna Lupardo",
    ("State Assembly", "123", "REP"): "Lisa M. OKeefe",
    ("State Assembly", "123", "CON"): "Lisa M. OKeefe",
    ("State Assembly", "123", "ECO"): "Lisa M. OKeefe",
    ("State Assembly", "124", "REP"): "Christopher S. Friend",
    ("State Assembly", "124", "CON"): "Christopher S. Friend",
    ("State Assembly", "131", "REP"): "Jeff Gallahan",
    ("State Assembly", "131", "CON"): "Jeff Gallahan",
}
NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def _office_of_title(title):
    t = (title or "").strip()
    if "PRESIDENTIAL ELECTORS" in t and "Vote for" in t:
        return ("President", "")
    if t.startswith("UNITED STATES SENATOR") and "Vote for" in t:
        return ("U.S. Senate", "")
    m = re.search(r"REPRESENTATIVE IN CONGRESS,\s*(\d+)[A-Za-z]*\s+CONGRESSIONAL", t)
    if m and "Vote for" in t:
        return ("U.S. House", m.group(1))
    m = re.search(r"STATE SENATOR,\s*(\d+)[A-Za-z]*\s+SENATE", t)
    if m and "Vote for" in t:
        return ("State Senate", m.group(1))
    m = re.search(r"MEMBER OF ASSEMBLY,\s*(\d+)[A-Za-z]*\s+ASSEMBLY", t)
    if m and "Vote for" in t:
        return ("State Assembly", m.group(1))
    return None


def _int(v):
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _is_int(tok):
    return bool(re.match(r"^[\d,]+$", tok))


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _surname(name):
    toks = [t for t in (name or "").split() if t]
    while toks and _norm(toks[-1]) in NAME_SUFFIX:
        toks.pop()
    return _norm(toks[-1]) if toks else ""


def _is_turnout(tok):
    return bool(re.match(r"^\d+\.\d+%$", tok))


def main():
    pdf = pdfplumber.open(SRC_PATH)
    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)          # (office,district,party) -> precinct sum
    wisum = defaultdict(int)         # (office,district) -> write-in precinct sum
    anchor = {}                      # (office,district,party) -> COUNTY TOTALS
    wi_anchor = {}                   # (office,district) -> COUNTY TOTALS write-in
    od_seen = []
    od_precincts = defaultdict(set)
    pres_precincts = set()
    sd_precincts = defaultdict(set)
    ad_precincts = defaultdict(set)
    house_precincts = set()
    header_text = {}                 # od -> header text (for surname check)
    name_fail = []
    arith_fail = []

    cur_od = None          # current (office, district) or None
    cur_section = None     # current "City of X" / "Town of X"
    expect_county = False  # saw a bare "COUNTY" line -> next TOTALS is anchor

    for pno in range(len(pdf.pages)):
        lines = [l for l in (pdf.pages[pno].extract_text() or "").split("\n")
                 if l.strip()]
        for raw in lines:
            s = raw.strip()

            # office title -> update current office (canonical) or clear it
            if "Vote for" in s:
                od = _office_of_title(s)
                cur_od = od if od in OFFICE_RANK else None
                if cur_od and cur_od not in od_seen:
                    od_seen.append(cur_od)
                expect_county = False
                continue

            # bare section header: "City of Binghamton" / "Town of Barker"
            if re.match(r"^(City|Town|Village) of [A-Za-z.'\- ]+$", s) \
                    and not any(c.isdigit() for c in s):
                cur_section = s
                continue

            if cur_od is None:
                continue

            office, district = cur_od
            parties = PARTIES_BY_OD[cur_od]
            n_cand = len(parties)
            n_data = n_cand + 7    # ED + n_cand + writeins + void + blank + ballots + voters + turnout
            n_total = n_cand + 6   # n_cand + writeins + void + blank + ballots + voters + turnout

            # capture header text (lines before the first data row of the office)
            # -- upright candidate names appear in the few lines after the title.
            if cur_od not in header_text and (
                    "Election District" in s or "(Scatter)" in s or "(Total)" in s):
                # gather this and the next couple of lines lazily: just use the
                # party-row + name lines we've already seen this page. Instead,
                # mark to collect on the page; simpler: store the party row line
                # plus scan the page once. We'll capture below via a page pass.
                pass

            # county grand-total anchor: "COUNTY" then "TOTALS ..."
            if s == "COUNTY":
                expect_county = True
                continue
            if expect_county and s.startswith("TOTALS"):
                # strip the trailing "NN.NN%" turnout so it isn't split into
                # two integer tokens by the [\d,]+ scan; the remaining integer
                # fields are n_cand + writeins + void + blank + ballots + voters
                # = n_total - 1 (n_total counts the turnout token).
                s2 = re.sub(r"\d+\.\d+%?\s*$", "", s)
                vals = [_int(t) for t in re.findall(r"[\d,]+", s2)]
                if len(vals) == n_total - 1:
                    for j, p in enumerate(parties):
                        anchor[(office, district, p)] = vals[j]
                    wi_anchor[(office, district)] = vals[n_cand]
                expect_county = False
                continue

            # split leading non-numeric label from numeric tail
            toks = s.split()
            if not toks:
                continue
            i = 0
            while i < len(toks) and not _is_int(toks[i]):
                i += 1
            if i == 0 or i == len(toks):
                continue  # no label, or no numbers
            nums = toks[i:]
            if not all(_is_int(t) or _is_turnout(t) for t in nums):
                continue  # trailing non-numeric noise (e.g. header labels)
            # require the trailing token to be a turnout percentage
            if not _is_turnout(nums[-1]):
                continue
            vals = [_int(t) for t in nums]

            if len(vals) == n_total:
                # town subtotal or stray total row -> skip (not data)
                continue
            if len(vals) != n_data:
                continue

            ed = vals[0]
            if ed > 999 or ed < 1:
                continue  # not an ED
            cand_vals = vals[1:1 + n_cand]
            wi = vals[1 + n_cand]
            void = vals[2 + n_cand]
            blank = vals[3 + n_cand]
            ballots = vals[4 + n_cand]
            if ballots != sum(cand_vals) + wi + void + blank:
                arith_fail.append((pno, cur_section, ed, ballots,
                                   sum(cand_vals), wi, void, blank))
            if cur_section is None:
                continue
            prec = f"{cur_section} {ed}"
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
            od_precincts[cur_od].add(prec)
            if office == "President":
                pres_precincts.add(prec)
            elif office == "U.S. House":
                house_precincts.add(prec)
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

    # ---- surname-presence check (upright header per office) ----------------
    # Re-scan: for each office, the upright candidate names sit in the lines
    # between the title and the first data row on the office's first page.
    name_checked = set()
    for pno in range(len(pdf.pages)):
        lines = [l for l in (pdf.pages[pno].extract_text() or "").split("\n")
                 if l.strip()]
        od_here = None
        for k, raw in enumerate(lines):
            s = raw.strip()
            if "Vote for" in s:
                od = _office_of_title(s)
                od_here = od if od in OFFICE_RANK else None
                if od_here and od_here not in name_checked:
                    name_checked.add(od_here)
                    office, district = od_here
                    parties = PARTIES_BY_OD[od_here]
                    # collect up to 8 lines after the title (upright names)
                    blob = " ".join(lines[k + 1:k + 9]).lower()
                    for p in parties:
                        sn = _surname(CAND[(office, district, p)])
                        if sn and sn not in _norm(blob):
                            name_fail.append(
                                f"{office} {district} {p}: surname {sn!r} "
                                f"not in p{pno} header")
                continue

    # ---- HARD verification --------------------------------------------------
    hard = []
    for pno, sec, ed, ballots, cs, wi, void, blank in arith_fail:
        hard.append(f"p{pno} {sec} ED {ed}: ballots={ballots} != "
                    f"cand{cs}+wi{wi}+void{void}+blank{blank}={cs+wi+void+blank}")
    hard.extend(name_fail)
    for od in OFFICE_ORDER:
        office, district = od
        parties = PARTIES_BY_OD[od]
        for p in parties:
            s = psum.get((office, district, p), 0)
            a = anchor.get((office, district, p))
            if a is None:
                hard.append(f"{od} {p}: no COUNTY TOTALS anchor")
            elif s != a:
                hard.append(f"{od} {p}: precinct-sum={s} != COUNTY TOTALS={a}")
        ws_ = wisum.get(od, 0)
        wa = wi_anchor.get(od)
        if wa is None:
            hard.append(f"{od} write-in: no COUNTY TOTALS anchor")
        elif ws_ != wa:
            hard.append(f"{od} write-in: precinct-sum={ws_} != COUNTY TOTALS={wa}")

    # split completeness: House 19 == President; SD-51/52 == President;
    # AD-121/123/124/131 == President (precinct SET, disjoint + complete)
    def _check_split(label, groups):
        union = set()
        ds = list(groups)
        for d, ps in groups.items():
            union |= ps
        if union != pres_precincts:
            hard.append(f"{label} split not complete: union={len(union)} "
                        f"president={len(pres_precincts)}; missing="
                        f"{sorted(pres_precincts - union)[:5]}")
        for a in range(len(ds)):
            for b in range(a + 1, len(ds)):
                ov = groups[ds[a]] & groups[ds[b]]
                if ov:
                    hard.append(f"{label} split overlap: {sorted(ov)[:5]}")
    if house_precincts != pres_precincts:
        hard.append(f"House 19 != President: {len(house_precincts)} vs "
                    f"{len(pres_precincts)}; missing="
                    f"{sorted(pres_precincts - house_precincts)[:5]}")
    _check_split("SD", sd_precincts)
    _check_split("AD", ad_precincts)

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
        parties = PARTIES_BY_OD[od]
        parts = [f"{p}={psum.get((office,district,p),0)}" for p in parties]
        parts.append(f"Write-in={wisum.get(od,0)}")
        a = anchor.get((office, district, parties[0]), "?")
        print(f"  {office} {district}: {', '.join(parts)} (COUNTY TOTALS {parties[0]}={a})")
    print(f"  House19 precincts={len(house_precincts)}; "
          f"SD split={ {d: len(ps) for d,ps in sd_precincts.items()} }; "
          f"AD split={ {d: len(ps) for d,ps in ad_precincts.items()} }")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())