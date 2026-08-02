#!/usr/bin/env python3
"""Dedicated parser for Schoharie County 2024 general precinct results (HTML).

The Schoharie County BOE publishes an NYS "Results per Precinct" HTML report
(`Schoharie.HTML`) -- 25 tables. Tables 1-5 are the 5 canonical offices (each =
24 rows: 1 header + 22 precincts + 1 "Total" county-grand-total row); tables 6-21
are town/village offices (skipped); tables 22-24 are Proposals (skipped); table 0
is a title block. Each canonical table's header row carries the party code as a
" - XXX" suffix on each candidate cell ("Kamala D. Harris and Tim Walz - WOR"),
so the party is parsed per-column (the column ORDER is WOR, DEM, CON, REP -- NOT
the standard DEM/REP/CON/WOR -- so positional assumptions would misassign).

Schoharie is WHOLLY inside NY-21 / SD-51 / AD-102 -- no split. Canonical offices:
  President             (statewide)   Harris (DEM/WOR) / Trump (REP/CON)
  U.S. Senate           (statewide)   Gillibrand (DEM/WOR) / Sapraicone (REP/CON) / Sare (LAR)
  U.S. House 21                       Paula Collins (DEM/WOR) / Elise M. Stefanik (REP/CON)
  State Senate 51                     Michele Frazier (DEM/WOR) / Peter Oberacker (REP/CON)
  State Assembly 102                  Janet S. Tweed (DEM/WOR) / Christopher Tague (REP/CON)

Fusion is split at the source (separate DEM/WOR + REP/CON columns) -- exactly the
#148-branch convention; emit one row per party-line column. Write-ins: each table
has an aggregate "Write-in" column plus named-write-in columns (Jill Stein, Peter
Sonski, MISC., Claudia De la Cruz, Chase Oliver, Donald J. Trump, Cornel West,
...). The named columns are all 0 countywide, so the aggregate "Write-in" column
IS the full write-in total; emit it as ONE "Write-in" row (party empty) per
(precinct, office) when >0 (named columns are a breakdown, NOT added -- avoids
double-count). 0-vote rows omitted. Numbers are comma-grouped ("5,141") -> strip.

Candidate names via a hardcoded CAND[(office,district,party)] map matching the
committed 2024 NY corpus: Collins/Stefanik match Hamilton/Clinton; Frazier/
Oberacker match Otsego; Tweed/Tague match Otsego/Greene. President source
"Kamala D. Harris and Tim Walz" -> VP mate dropped. WOR=Working Families (#148
convention), LAR=LaRouche. Precinct names preserved verbatim ("Town of Blenheim
1 LD 1") -- matches the committed 2022 Schoharie file (which uses the same
"Town of X N LD 1" convention).

Office is detected from header candidate surnames (Harris/Trump->President,
Gillibrand/Sapraicone/Sare->Senate, Collins/Stefanik->House 21, Frazier/
Oberacker->SD 51, Tweed/Tague->AD 102), not by table index, so the parser is
robust to table reordering / local-office table insertion.

Verification (all HARD):
  1. per (office, party column): precinct-sum == table "Total" row (3-way with
     the hardcoded ANCHOR derived from the Total rows).
  2. candidate-name cross-check (President VP-mate drop).
Run with uv (beautifulsoup4):  uv run python schoharie_2024_parse.py
"""
import os
import re
import sys
import csv
from collections import defaultdict

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.environ.get(
    "SCHOHARIE_HTML",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Schoharie.HTML",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__schoharie__precinct.csv"
)
COUNTY = "Schoharie"

OFFICE_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", "21"),
                ("State Senate", "51"), ("State Assembly", "102")]
OFFICE_RANK = {od: i for i, od in enumerate(OFFICE_ORDER)}
PARTY_RANK = {"DEM": 0, "REP": 1, "CON": 2, "WOR": 3, "LAR": 4, "IND": 5}
PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR",
              "WFP": "WOR", "LAR": "LAR"}

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
    ("State Senate", "51", "DEM"): "Michele Frazier",
    ("State Senate", "51", "WOR"): "Michele Frazier",
    ("State Senate", "51", "REP"): "Peter Oberacker",
    ("State Senate", "51", "CON"): "Peter Oberacker",
    ("State Assembly", "102", "DEM"): "Janet S. Tweed",
    ("State Assembly", "102", "WOR"): "Janet S. Tweed",
    ("State Assembly", "102", "REP"): "Christopher Tague",
    ("State Assembly", "102", "CON"): "Christopher Tague",
}

# surname -> (office, district) for office detection
SURNAME_OFFICE = {
    "harris": ("President", ""), "trump": ("President", ""),
    "gillibrand": ("U.S. Senate", ""), "sapraicone": ("U.S. Senate", ""),
    "sare": ("U.S. Senate", ""),
    "collins": ("U.S. House", "21"), "stefanik": ("U.S. House", "21"),
    "frazier": ("State Senate", "51"), "oberacker": ("State Senate", "51"),
    "tweed": ("State Assembly", "102"), "tague": ("State Assembly", "102"),
}


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
        code = m.group(1)
        return PARTY_NORM.get(code)
    return None


def _base_name(cell_txt):
    """'Kamala D. Harris and Tim Walz - WOR' -> 'Kamala D. Harris and Tim Walz'."""
    s = re.sub(r"\s*-\s*[A-Z]{2,4}\s*$", "", cell_txt).strip()
    return s


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
    name_seen = defaultdict(set)  # (office,district,party) -> source names
    od_seen = []

    for t in tables:
        trs = t.find_all("tr")
        if not trs:
            continue
        hdr_cells = trs[0].find_all(["td", "th"])
        hdr = [_cell_text(c) for c in hdr_cells]
        if not hdr or hdr[0].lower() != "precinct":
            continue
        # build column layout from header (col0=precinct)
        col_party = {}      # col_idx -> party
        col_name = {}       # col_idx -> base name
        writein_cols = []   # col_idx of "Write-in" + named write-in cols
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
                # named write-in column (Jill Stein, MISC., etc.) -- no party
                if txt and txt.lower() not in ("blanks", "voids", "over votes",
                        "under votes", "total votes", "totals", "total"):
                    writein_cols.append(j)
        od = _office_of(header_names)
        if od is None or od not in OFFICE_RANK:
            continue  # non-canonical office table
        office, district = od
        if od not in od_seen:
            od_seen.append(od)

        # data rows until "Total"
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
            # precinct row
            prec = re.sub(r"\s+", " ", label).strip()
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