#!/usr/bin/env python3
"""Dedicated parser for Wayne County 2024 general precinct results (HTML).

The Wayne County BOE publishes an NYS "Results per Precinct" HTML report
(`Wayne.html`) -- same format as Schoharie. 27 tables: table 0 = title block;
tables 1-26 = one per contest (each = header + 67 precinct rows + "Total" county
-grand-total row); tables 25-26 = Proposals. Each canonical table's header row
carries the party code as a " - XXX" suffix on each candidate cell ("Kamala D.
Harris and Tim Walz - WOR"), so the party is parsed per-column (the column ORDER
is WOR, DEM, CON, REP -- NOT the standard DEM/REP/CON/WOR -- so positional
assumptions would misassign).

Wayne is WHOLLY inside NY-24 / SD-54 / AD-130 -- NO split (confirmed: the source
has exactly one House / one State Senate / one Assembly table, each with all 67
precincts; matches the committed 2022 Wayne file which also has only NY-24/
SD-54/AD-130 plus statewide offices). Canonical offices (the HTML carries office
titles, but detection is by header candidate surnames for robustness):
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 24                       David Wagenhauser (DEM) / Claudia Tenney (REP/CON)
  State Senate 54                     Scott Comegys (DEM) / Pamela A. Helming (REP/CON)
  State Assembly 130                  James Schuler (DEM) / Brian D. Manktelow (REP/CON)
Non-canonical tables skipped: State Supreme Court Justice 7th JD (vote-for-2),
District Attorney, County Coroner, town/village offices, Proposals -- none match
the surname map, naturally ignored.

Fusion is SPLIT at the source (separate DEM/WOR + REP/CON columns) -- exactly
the #148-branch convention; emit one row per party-line column. Note: House 24,
SD-54 and AD-130 have NO Working Families line in this source (Wagenhauser/
Comegys/Schuler ran DEM-only) -- CAND only lists the party lines that appear.
Write-ins: each table has a single aggregate "Write-in" column (no named write-in
columns) -- emit it as ONE "Write-in" row (party empty) per (precinct, office)
when >0. 0-vote rows omitted. Numbers are comma-grouped ("15,964") -> strip.

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed corpus: Tenney/Wagenhauser match Niagara/Livingston; Helming/Comegys
match Livingston (SD-54); **Brian D. Manktelow kept WITH the middle initial** to
match the committed 2022 Wayne AD-130 file (cross-county "drop middle initial"
convention does NOT apply when the existing committed file keeps it). President
"Kamala D. Harris and Tim Walz" -> VP mate dropped. Precinct names normalized:
"Town of Arcadia 1 LD 1" -> "Arcadia 1" (strip "Town of " prefix and " LD N"
county-legislative suffix) -- matches the committed 2022 Wayne file ("Arcadia
1"). WOR=Working Families (#148 convention), LAR=LaRouche.

Office detected from header candidate surnames (Harris/Trump->President,
Gillibrand/Sapraicone/Sare->Senate, Wagenhauser/Tenney->House 24, Comegys/
Helming->SD 54, Schuler/Manktelow->AD 130), not by table index.

Verification (all HARD):
  1. per (office, district, party): precinct-sum == table "Total" row;
     write-in precinct-sum == Total-row "Write-in" col.
  2. candidate-name cross-check (President VP-mate drop).
Run with uv (beautifulsoup4):  uv run python wayne_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "WAYNE_HTML",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Wayne.html",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__wayne__precinct.csv"
)
COUNTY = "Wayne"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "24"),
                ("State Senate", "54"), ("State Assembly", "130")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}

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
    ("U.S. House", "24", "DEM"): "David Wagenhauser",
    ("U.S. House", "24", "REP"): "Claudia Tenney",
    ("U.S. House", "24", "CON"): "Claudia Tenney",
    ("State Senate", "54", "DEM"): "Scott Comegys",
    ("State Senate", "54", "REP"): "Pamela A. Helming",
    ("State Senate", "54", "CON"): "Pamela A. Helming",
    ("State Assembly", "130", "DEM"): "James Schuler",
    ("State Assembly", "130", "REP"): "Brian D. Manktelow",
    ("State Assembly", "130", "CON"): "Brian D. Manktelow",
}

# surname -> (office, district) for office detection
SURNAME_OFFICE = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "wagenhauser": ("U.S. House", "24"), "tenney": ("U.S. House", "24"),
    "comegys": ("State Senate", "54"), "helming": ("State Senate", "54"),
    "schuler": ("State Assembly", "130"), "manktelow": ("State Assembly", "130"),
}
PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
              "WFP": "WOR", "LAR": "LAR"}


def _int(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _cell_text(cell):
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _party_from_header(cell_txt):
    """'Kamala D. Harris and Tim Walz - WOR' -> 'WOR'."""
    m = re.search(r"-\s*([A-Z]{2,4})\s*$", cell_txt)
    if m:
        return PARTY_NORM.get(m.group(1))
    return None


def _base_name(cell_txt):
    """'Kamala D. Harris and Tim Walz - WOR' -> 'Kamala D. Harris and Tim Walz'."""
    return re.sub(r"\s*-\s*[A-Z]{2,4}\s*$", "", cell_txt).strip()


def _office_of(header_names):
    """Detect (office, district) from the set of candidate base-names."""
    for nm in header_names:
        for tok in (nm or "").split():
            t = _norm(tok)
            if t in SURNAME_OFFICE:
                return SURNAME_OFFICE[t]
    return None


def _clean_name(ballot, office):
    s = (ballot or "").strip()
    if office == "President" and " and " in s:
        s = s.split(" and ", 1)[0].strip()
    return s


def _strip_precinct(label):
    """'Town of Arcadia 1 LD 1' -> 'Arcadia 1' (match 2022 Wayne convention)."""
    s = re.sub(r"\s+", " ", str(label)).strip()
    s = re.sub(r"^Town of\s+", "", s)
    s = re.sub(r"\s+LD\s+\d+$", "", s)
    s = re.sub(r"^City of\s+", "", s)
    return s.strip()


def main():
    html = open(SRC_PATH, encoding="utf-8", errors="replace").read()
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    all_rows = []
    prec_order = []
    seen_prec = set()
    psum = defaultdict(int)       # (office,district,party) -> precinct sum
    wisum = defaultdict(int)      # (office,district) -> write-in precinct sum
    col_total = {}                # (office,district,party) -> Total-row val
    wi_total = {}                 # (office,district) -> Total-row write-in val
    name_seen = defaultdict(set)
    od_seen = []

    for t in tables:
        trs = t.find_all("tr")
        if not trs:
            continue
        hdr_cells = trs[0].find_all(["td", "th"])
        hdr = [_cell_text(c) for c in hdr_cells]
        if not hdr or hdr[0].lower() != "precinct":
            continue
        col_party = {}      # col_idx -> party
        col_name = {}       # col_idx -> base name
        writein_cols = []   # col_idx of "Write-in" (+ any named write-in cols)
        header_names = []
        for j, txt in enumerate(hdr):
            if j == 0:
                continue
            if txt.lower() in ("write-in", "write in"):
                writein_cols.append(j)
                continue
            party = _party_from_header(txt)
            if party is not None:
                col_party[j] = party
                bn = _base_name(txt)
                col_name[j] = bn
                header_names.append(bn)
            else:
                # named write-in column (none in Wayne) -- not a control row
                if txt and txt.lower() not in ("blanks", "voids", "over votes",
                        "under votes", "total votes", "totals", "total"):
                    writein_cols.append(j)
        od = _office_of(header_names)
        if od is None or od not in OFFICE_RANK:
            continue  # non-canonical office table
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
            if label.lower() == "total":
                for j, party in col_party.items():
                    if j < len(cells):
                        col_total[(office, district, party)] = _int(cells[j])
                wi_total[(office, district)] = sum(
                    _int(cells[j]) for j in writein_cols if j < len(cells))
                break
            prec = _strip_precinct(label)
            if prec not in seen_prec:
                seen_prec.add(prec)
                prec_order.append(prec)
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
    for od in OFFICE_ORDER:
        office, district = od
        for party in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, party) not in CAND:
                continue
            s = psum.get((office, district, party), 0)
            tr = col_total.get((office, district, party))
            if tr is None:
                hard.append(f"{od} {party}: no Total row")
            elif s != tr:
                hard.append(f"{od} {party}: precinct-sum={s} != Total={tr}")
        ws_ = wisum.get(od, 0)
        wt = wi_total.get(od)
        if wt is None:
            hard.append(f"{od} write-in: no Total row")
        elif ws_ != wt:
            hard.append(f"{od} write-in: precinct-sum={ws_} != Total={wt}")

    for (office, district, party), names in name_seen.items():
        expected = CAND.get((office, district, party))
        if expected is None:
            continue
        exp = _norm(expected)
        for nm in names:
            cn = _clean_name(nm, office)
            if cn and _norm(cn) != exp:
                hard.append(f"{office}/{district} {party}: source {nm!r} "
                            f"!= expected {expected!r}")

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
        for party in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, party) in CAND:
                parts.append(f"{party}={psum.get((office,district,party),0)}")
        parts.append(f"Write-in={wisum.get(od,0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())