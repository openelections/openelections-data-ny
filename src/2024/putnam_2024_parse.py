#!/usr/bin/env python3
"""Dedicated parser for Putnam County 2024 general precinct PDF (NaturalPDF).

The Putnam BOE "November 5, 2024 General Election Results" PDF (61 pages) is a
rotated-text SOVC the shared ny2024_rpp_parser.py cannot open. Candidate names
are printed rotated/vertical, so extract_text() garbles them; but NaturalPDF's
extract_tables() recovers a clean grid, and a SECOND header row carries the
upright party codes (DEM/REP/CON/WOR/LAR) -- that party-code row is all the
candidate mapping needs (the full name is resolved from (office,district,party)
via a hardcoded CAND map). The office TITLE is upright text for every office
except President (whose title is rotated), so offices/districts are read from
the upright page text.

Layout (per office, one table per page, precincts paginated alphabetically):
  col0 = precinct code (2-letter town prefix + ED number, e.g. "CA 01"),
  col1-5 = turnout (Machine / Mail Ballot / Total Turnout / Voter Reg / %),
  col6+ = candidate party-line columns (party-code row gives the party),
  then write-in + Total/Void/Blank + enrollment columns.

Two distinct trailing layouts:
  * President (4 parties DEM/REP/CON/WOR, 23 cols): after the 4 candidate cols
    come 6 NAMED write-in columns, then Total Votes Cast (=cand+writein),
    Void/Over/Under, Total ballots, enrollment. The rotated labels bleed across
    these many columns, so label keyword detection is unreliable -- President
    uses a hardcoded column map (verified: cand 6-9, write-ins 10-15,
    Total-Votes-Cast 16, total-ballots 20).
  * All other offices (Senate/House/State Senate/Assembly): a single aggregate
    Write-in column. The trailing 5-column block is
    [cand_total, Blank, Void, Write-in, Total ballots], where Total ballots is
    the column whose rotated header fragment reads "TOTAL VOTES" (detected via
    the 'total'+'vote' keywords, forward or reversed). So cand_total = tb-4,
    Blank = tb-3, Void = tb-2, Write-in = tb-1.

Canonical offices (district from upright title):
  President (p1-6, rotated title -> detected structurally: 4 parties + 23 cols)
  U.S. Senate (p7-12, statewide)
  U.S. House 17 (p19-24) -- Mike Lawler (REP/CON) vs Mondaire L. Jones (DEM/WOR)
  State Senate 39 (p25-26) -- Rob Rolison (REP/CON) vs Yvette Valdes Smith (DEM/WOR)
           [Philipstown + Putnam Valley, 20 precincts]
  State Senate 40 (p27-30) -- Peter B. Harckham (DEM/WOR) vs Gina M. Arena (REP/CON)
           [Carmel/Kent/Patterson/Southeast, 61 precincts] -- a SECOND senate dist.
  State Assembly 94 (p31-35) -- Matthew J. Slater (REP/CON) vs Zachary C. Couzens (DEM)
  State Assembly 95 (p36)     -- Michael L. Capalbo (REP/CON) vs Dana Levenberg (DEM/WOR)
Putnam is SPLIT across AD-94 (Carmel/Kent/Patterson/Putnam Valley/Southeast, 71
precincts) and AD-95 (Philipstown, 10 precincts) -- no overlap, total 81 -- and
SPLIT across SD-39 (20 precincts) and SD-40 (61 precincts). District numbers are
read from the upright title (e.g. "40TH SENATORIAL DISTRICT"); the office title
is upright for every office except President.
Pages 13-18 (a 15-candidate multi-seat non-canonical office, e.g. Supreme Court)
and pages 37+ (local offices/propositions) are skipped -- their office title does
not classify and/or their party-code row is not the canonical set.

Precinct codes -> town names (Putnam's 6 towns):
  CA=Carmel, KE=Kent, PA=Patterson, PH=Philipstown, PV=Putnam Valley, SE=Southeast.
"CA 01" -> "Carmel ED 1" (leading zeros stripped). No wards in Putnam.

Write-ins: a single aggregate "Write-in" row per precinct (party empty) when >0.
For President this is the sum of the 6 named write-in columns (the named columns
ARE the complete write-in breakdown -- they sum into Total Votes Cast -- but the
rotated names are not reliably recoverable, so the accurate aggregate is emitted,
matching the committed-corpus convention). 0-vote rows are omitted throughout.
WOR = Working Families (#148-branch convention); LAR = LaRouche.

Verification: the PRIMARY (hard) check is per-precinct self-consistency:
  - President: Total Votes Cast (col16) == sum(candidates) + sum(write-ins),
    and total ballots (col20) == Total Votes Cast + Void(17) + col18 + col19.
  - Other offices: cand_total (tb-4) == sum(candidates), and
    total ballots == cand_total + Blank + Void + Write-in.
There is NO county grand-total row (only per-page "TOTAL" subtotals), so the
SECONDARY check sums each office-party-line's precinct votes and compares to the
sum of the pages' TOTAL-row subtotals (which together equal the county total).
Run with uv (natural_pdf needs Python >=3.12):  uv run python putnam_2024_parse.py
"""
import os
import re
import sys
import csv

import natural_pdf as npdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.environ.get(
    "PUTNAM_PDF",
    "/Users/dwillis/code/openelections-sources-ny/2024/general/Putnam.pdf",
)
OUT_PATH = os.path.join(
    HERE, "..", "..", "2024", "counties", "20241105__ny__general__putnam__precinct.csv"
)

TOWN = {
    "CA": "Carmel", "KE": "Kent", "PA": "Patterson",
    "PH": "Philipstown", "PV": "Putnam Valley", "SE": "Southeast",
}

# (office, district, party) -> full canonical candidate name (matches the
# committed 2024 NY counties; Putnam-only candidates resolved from the source +
# BOE results). Each fusion party line is a separate row.
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
    ("U.S. House", "17", "DEM"): "Mondaire L. Jones",
    ("U.S. House", "17", "WOR"): "Mondaire L. Jones",
    ("U.S. House", "17", "REP"): "Mike Lawler",
    ("U.S. House", "17", "CON"): "Mike Lawler",
    ("State Senate", "39", "DEM"): "Yvette Valdes Smith",
    ("State Senate", "39", "WOR"): "Yvette Valdes Smith",
    ("State Senate", "39", "REP"): "Rob Rolison",
    ("State Senate", "39", "CON"): "Rob Rolison",
    ("State Senate", "40", "DEM"): "Peter B. Harckham",
    ("State Senate", "40", "WOR"): "Peter B. Harckham",
    ("State Senate", "40", "REP"): "Gina M. Arena",
    ("State Senate", "40", "CON"): "Gina M. Arena",
    ("State Assembly", "94", "DEM"): "Zachary C. Couzens",
    ("State Assembly", "94", "REP"): "Matthew J. Slater",
    ("State Assembly", "94", "CON"): "Matthew J. Slater",
    ("State Assembly", "95", "DEM"): "Dana Levenberg",
    ("State Assembly", "95", "WOR"): "Dana Levenberg",
    ("State Assembly", "95", "REP"): "Michael L. Capalbo",
    ("State Assembly", "95", "CON"): "Michael L. Capalbo",
}

PARTY_NORM = {"DEM": "DEM", "REP": "REP", "CON": "CON", "WOR": "WOR", "LAR": "LAR"}
KNOWN_PARTIES = set(PARTY_NORM) | {"IND", "GRE", "LIB", "SAM", "CMN"}


def _ci(c):
    s = (c or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _letters(s):
    """Uppercase alphanumeric run (keeps digits so district numbers like '17TH'
    survive into the district regexes; spaces/punct stripped)."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _kw(cell):
    """Keywords whose rotated label (forward OR reversed) appears in a header
    cell. Rotation may read either direction, so check both."""
    f = re.sub(r"[^a-z]", "", (cell or "").lower())
    r = f[::-1]
    keys = ["total", "vote", "void", "blank", "write", "over", "under"]
    return {k for k in keys if k in f or k in r}


def detect_office(page, table):
    """Return (office, district) or None. Office from upright page title for
    Senate/House/StateSenate/Assembly; President detected structurally (party
    codes DEM/REP/CON/WOR + 23 cols) since its title is rotated."""
    up = _letters(page.extract_text() or "")
    if "UNITEDSTATESSENATOR" in up:
        return ("U.S. Senate", "")
    if "REPRESENTATIVEINCONGRESS" in up:
        m = re.search(r"(\d+)THCONGRESSIONALDISTRICT", up)
        return ("U.S. House", m.group(1) if m else "")
    if "MEMBEROFTHEASSEMBLY" in up:
        m = re.search(r"(\d+)THASSEMBLYDISTRICT", up)
        return ("State Assembly", m.group(1) if m else "")
    # "STATE SENATOR" -> "STATESENATOR" (single S between STATE and SENATOR).
    # US Senate ("UNITED STATES SENATOR" -> "UNITEDSTATESSENATOR") is caught above
    # and also contains "UNITEDSTATES", so the not-in guard excludes it here.
    if "STATESENATOR" in up and "UNITEDSTATES" not in up:
        m = re.search(r"(\d+)THSENATORIALDISTRICT", up)
        return ("State Senate", m.group(1) if m else "")
    # President: title is rotated; detect by structure.
    parties = [(j, (c or "").strip().rstrip("*")) for j, c in enumerate(table[1])
               if (c or "").strip().rstrip("*") in KNOWN_PARTIES]
    pset = {p for _, p in parties}
    if pset == {"DEM", "REP", "CON", "WOR"} and len(table[0]) >= 20:
        return ("President", "")
    return None


def cand_cols(table):
    """[(col_index, party)] for each candidate party-line column, from the
    party-code row (row index 1). Strips footnote '*'/"""
    out = []
    for j, c in enumerate(table[1]):
        code = (c or "").strip().rstrip("*")
        if code in KNOWN_PARTIES:
            out.append((j, PARTY_NORM.get(code, code)))
    return out


def normalize_precinct(s):
    """'CA 01' -> 'Carmel ED 1' (2-letter town prefix + zero-padded ED number)."""
    m = re.match(r"^([A-Z]{2})\s*0*(\d+)$", (s or "").strip())
    if not m:
        return (s or "").strip()
    town = TOWN.get(m.group(1), m.group(1))
    return f"{town} ED {m.group(2)}"


def is_precinct(name):
    return bool(re.match(r"^[A-Z]{2}\s*\d+$", (name or "").strip()))


def parse_page(page):
    """Parse one office page. Returns (office, district, rows, page_totals,
    selfcheck) where rows = [(office,district,party,candidate,precinct,votes)],
    page_totals = {(office,district,party,candidate): subtotal} from the page's
    TOTAL row (for the county-sum soft check), selfcheck = per-precinct tuples
    for the hard self-consistency check. Returns None if not a canonical office.
    """
    try:
        tables = page.extract_tables()
    except Exception:
        return None
    if not tables or not tables[0] or len(tables[0]) < 3:
        return None
    table = tables[0]
    od = detect_office(page, table)
    if od is None:
        return None
    office, district = od
    ncols = len(table[0])
    cc = cand_cols(table)
    if not cc:
        return None
    cand_idx = [j for j, _ in cc]
    last_cand = max(cand_idx)

    rows = []
    page_totals = {}
    selfcheck = []

    if office == "President":
        # Hardcoded, verified map (rotated labels bleed -> kw unreliable).
        WICOLS = list(range(10, 16))      # 6 named write-in columns
        TVC = 16                          # Total Votes Cast = cand + write-ins
        TB = 20                           # total ballots
        for r in table[2:]:
            name = (r[0] or "").strip()
            if name.upper() == "TOTAL":
                for j, party in cc:
                    c = CAND.get((office, district, party))
                    if c:
                        page_totals[(office, district, party, c)] = _ci(
                            r[j] if j < len(r) else None)
                # write-in subtotal
                wsum = sum(_ci(r[j] if j < len(r) else 0) for j in WICOLS)
                page_totals[(office, district, "", "Write-in")] = wsum
                continue
            if not is_precinct(name):
                continue
            precinct = normalize_precinct(name)
            sc = sum(_ci(r[j] if j < len(r) else 0) for j in cand_idx)
            sw = sum(_ci(r[j] if j < len(r) else 0) for j in WICOLS)
            for j, party in cc:
                v = _ci(r[j] if j < len(r) else 0)
                if v == 0:
                    continue
                cand = CAND.get((office, district, party))
                if cand:
                    rows.append((office, district, party, cand, precinct, v))
            if sw > 0:
                rows.append((office, district, "", "Write-in", precinct, sw))
            selfcheck.append((precinct, sc, sw, _ci(r[TVC]),
                              _ci(r[TB]), sum(_ci(r[k] if k < len(r) else 0)
                                              for k in (17, 18, 19))))
        return office, district, rows, page_totals, selfcheck

    # Single-write-in offices: Total ballots = the 'total'+'vote' kw column
    # after the candidates; the 5-col block is [cand_total, blank, void, wi, tb].
    tb = None
    for j in range(last_cand + 1, ncols):
        if _kw(table[0][j]) >= {"total", "vote"}:
            tb = j
            break
    if tb is None or tb - 4 < 0:
        return None
    ct_col, blank_col, void_col, wi_col, tb_col = tb - 4, tb - 3, tb - 2, tb - 1, tb
    for r in table[2:]:
        name = (r[0] or "").strip()
        if name.upper() == "TOTAL":
            for j, party in cc:
                c = CAND.get((office, district, party))
                if c:
                    page_totals[(office, district, party, c)] = _ci(
                        r[j] if j < len(r) else None)
            page_totals[(office, district, "", "Write-in")] = _ci(
                r[wi_col] if wi_col < len(r) else None)
            continue
        if not is_precinct(name):
            continue
        precinct = normalize_precinct(name)
        sc = sum(_ci(r[j] if j < len(r) else 0) for j in cand_idx)
        for j, party in cc:
            v = _ci(r[j] if j < len(r) else 0)
            if v == 0:
                continue
            cand = CAND.get((office, district, party))
            if cand:
                rows.append((office, district, party, cand, precinct, v))
        wv = _ci(r[wi_col] if wi_col < len(r) else 0)
        if wv > 0:
            rows.append((office, district, "", "Write-in", precinct, wv))
        selfcheck.append((precinct, sc,
                          _ci(r[ct_col] if ct_col < len(r) else 0),
                          _ci(r[blank_col] if blank_col < len(r) else 0),
                          _ci(r[void_col] if void_col < len(r) else 0),
                          wv, _ci(r[tb_col] if tb_col < len(r) else 0)))
    return office, district, rows, page_totals, selfcheck


def main():
    pdf = npdf.PDF(PDF_PATH)
    all_rows = []
    page_totals = {}  # (office,district,party,candidate) -> sum of page subtotals
    selfcheck = []
    pages_seen = []
    for i, page in enumerate(pdf.pages):
        res = parse_page(page)
        if res is None:
            continue
        office, district, rows, pt, sc = res
        all_rows.extend(rows)
        for k, v in pt.items():
            page_totals[k] = page_totals.get(k, 0) + v
        pages_seen.append((i + 1, office, district))
        for t in sc:
            selfcheck.append((office, district) + t)

    # ---- Verification -------------------------------------------------------
    hard = []
    for office, district, precinct, *rest in selfcheck:
        if office == "President":
            # rest = [sc, sw, tvc, tb, extras]
            sc, sw, tvc, tb, extras = rest
            if sc + sw != tvc:
                hard.append(f"President {precinct}: cand({sc})+wi({sw})={sc+sw} "
                            f"!= TotalVotesCast({tvc})")
            elif tvc + extras != tb:
                hard.append(f"President {precinct}: TVC({tvc})+void/over/under"
                            f"({extras})={tvc+extras} != ballots({tb})")
        else:
            # rest = [sc, ct, blank, void, wi, tb]
            sc, ct, blank, void, wi, tb = rest
            if sc != ct:
                hard.append(f"{office}/{district} {precinct}: cand-sum({sc}) "
                            f"!= cand_total({ct})")
            elif ct + blank + void + wi != tb:
                hard.append(f"{office}/{district} {precinct}: "
                            f"{ct}+{blank}+{void}+{wi}={ct+blank+void+wi} "
                            f"!= ballots({tb})")

    # Soft: precinct sums == sum of page TOTAL subtotals (== county total).
    soft = []
    sums = {}
    for office, district, party, cand, precinct, votes in all_rows:
        k = (office, district, party, cand)
        sums[k] = sums.get(k, 0) + votes
    for k, tv in page_totals.items():
        sv = sums.get(k, 0)
        if sv != tv:
            soft.append(f"county-sum mismatch {k}: precinct-sum={sv} "
                        f"pdf-subtotal-sum={tv}")
    for k in sorted(set(sums) - set(page_totals)):
        soft.append(f"{k}: emitted votes but no page TOTAL row found")

    # ---- Write CSV ---------------------------------------------------------
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for office, district, party, cand, precinct, votes in all_rows:
            w.writerow(["Putnam", precinct, office, district, party, cand, votes])

    precincts = {r[4] for r in all_rows}
    offices = []
    for r in all_rows:
        od = (r[0], r[1])
        if od not in offices:
            offices.append(od)
    print(f"Pages parsed: {len(pages_seen)}")
    for p, o, d in pages_seen[:14]:
        print(f"  p{p}: {o} {d}")
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"office-districts={offices} -> {OUT_PATH}")
    n_h = len(selfcheck) - len(hard)
    print(f"Self-consistency: {n_h}/{len(selfcheck)} precincts OK.")
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        if len(hard) > 60:
            print(f"  ... and {len(hard) - 60} more", file=sys.stderr)
    if soft:
        print(f"--- {len(soft)} county-sum mismatch(es) (non-fatal) ---",
              file=sys.stderr)
        for p in soft[:60]:
            print("  " + p, file=sys.stderr)
    if hard:
        return 1
    print(f"Verification OK: {n_h}/{len(selfcheck)} per-precinct self-consistent; "
          f"{len(sums) - len(soft)}/{len(sums)} party-line sums == county "
          f"subtotal-sum ({len(soft)} mismatch).")
    return 0


if __name__ == "__main__":
    sys.exit(main())