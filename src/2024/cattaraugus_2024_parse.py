#!/usr/bin/env python3
"""Dedicated parser for Cattaraugus County 2024 general SOVC PDF.

The Cattaraugus 2024 "Results per Precinct" PDF (2024/pdf_src/Cattaraugus.pdf)
uses a rotated-text SOVC layout the shared ny2024_rpp_parser.py does not handle
cleanly:

  * Candidate names are printed rotated ~60deg; the upright party-code header
    row (DEM/REP/CON/WOR/LRC) is shifted right of the rotated candidate anchors,
    so the shared parser's upright-party-row path would map parties to the
    wrong candidate columns.
  * Each precinct is split into a main (Election Day) row plus four
    counting-group sub-rows (ABS/EVBM pre-ED, Early Voting, ABS/EVBM/Affidavitt
    post-ED, Unscanned/manual entry). The precinct total = main + all four
    sub-rows (disjoint counting groups); main != sum-of-subs, so neither max
    nor the main row alone is correct.
  * Interleaved "TOTAL VOTES CAST" and per-candidate subtotal columns sit
    between the party-line columns. A candidate with N party lines has N+1
    rotated anchors: one subtotal (no party code) + N party-line anchors.
  * The WRITE-INS aggregate column already contains every named write-in
    (verified county-wide: WRITE-INS == sum of individual write-in candidate
    columns), so the individual write-in candidate columns are skipped.

This parser extracts the five state/federal offices (President, U.S. Senate,
U.S. House, State Senate, State Assembly) -- the PDF interleaves non-target
county offices (Supreme Court Justice, County Treasurer/Sheriff/Coroner,
Proposal, and town/city local offices) which are ignored by page range.

Column matching uses the "rightmost rotated anchor with anchor_x < number x1"
rule: the rotated anchor (bottom char center) sits to the LEFT of its number,
and this rule is robust both to the per-region offset exceeding half the column
spacing (President, where plain nearest-distance matching flips columns) and
to extra write-in-detail anchors that sit beyond the last real column (State
Senate). Each contest's per-candidate county total is verified against the
PDF's own TOTAL row (== certified AP canvas) before the CSV is written.

Standalone (precedent: cattaraugus_2020_parse.py) so it imposes zero regression
risk on the shared parser and the committed counties.
"""
import os
import sys
import csv
import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ny2024_rpp_parser as P

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(HERE, "..", "..", "2024", "pdf_src", "Cattaraugus.pdf")
OUT_PATH = os.path.join(HERE, "..", "..", "2024", "counties",
                       "20241105__ny__general__cattaraugus__precinct.csv")

# Contest page ranges (1-indexed) -> (canonical office, district).
# Non-target county offices interleaved in the PDF are excluded by range:
#   p9-14  State Supreme Court Justice
#   p28-30 County Treasurer, p31-34 Sheriff, p35-38 Coroner, p39-43 Proposal
#   p44+   city/town local offices (Alderman, Mayor, Town Justice, ...)
CONTESTS = [
    ("President", "", range(1, 5)),
    ("U.S. Senate", "", range(5, 9)),
    ("U.S. House", "23", range(15, 20)),
    ("State Senate", "57", range(20, 23)),
    ("State Assembly", "148", range(23, 28)),
]

# Counting-group sub-row labels (a precinct block = main row + these four).
SUBROW_PREFIXES = ("ABS/EVBM", "Early Voting", "Unscanned")

# Numbers left of this x1 belong to the precinct *name* (e.g. the "1" in
# "Allegany District 1"); the leftmost number at/above it is TOTAL VOTES CAST.
VOTE_X_MIN = 120
# Max px between a rotated candidate anchor and an upright party-code x0 for
# the anchor to count as that party's line. Party-line anchors land within
# ~8px; subtotals and individual write-in anchors are >=28px from any code.
PARTY_NEAR = 15


def is_num(t):
    return t.replace(",", "").isdigit()


def toi(t):
    return int(t.replace(",", ""))


# NY SOVC party-code labels the shared parser's party_of() does not recognize.
# Cattaraugus labels the LaRouche line "LRC"; all committed 2024 counties use
# "LAR" for Diane Sare, so map LRC -> LAR. Add more here if another contest's
# upright header carries an unrecognized code.
PARTY_OVERRIDES = {"LRC": "LAR"}


def party_of(tok):
    """Local party_of: apply Cattaraugus-specific overrides, then defer to the
    shared parser's P.party_of."""
    if tok:
        bare = tok.strip().strip("()[]{}:,.;").upper()
        if bare in PARTY_OVERRIDES:
            return PARTY_OVERRIDES[bare]
    return P.party_of(tok)


def _is_tvc_name(nm):
    u = nm.upper().replace(" ", "")
    return ("TOTALVOTES" in u) or ("CAST" in u)


def _is_voidblank_name(nm):
    u = nm.upper().replace(" ", "")
    return u in ("VOIDS", "BLANKS", "SCATTER", "VOID", "BLANK")


def _is_writein_name(nm):
    return "WRITE" in nm.upper().replace(" ", "").replace("-", "")


def contest_anchors(doc, pages):
    """Rotated column anchors for a contest, as [{'name','anchor_x'}] sorted by
    anchor_x. Picks the page with the most non-TVC, non-party-label diagonals
    (the header page). Extra write-in-detail anchors beyond the last real
    column are harmless: the rightmost-below matching rule never reaches them.

    Also returns tvc_xmin: the leftmost 'TOTAL VOTES CAST' rotated anchor x,
    used as the name/vote boundary -- the precinct *name* number (e.g. the
    '1' in 'Ward 1') always sits left of the TVC anchor, and the TVC number
    sits within the anchor span. A fixed x1 threshold cannot separate them
    (State Senate TVC x1=138 vs Assembly ward-number x1=136), but the TVC
    anchor x can: it tracks the table's left edge per contest.
    """
    best = []
    tvc_min = None
    for pi in pages:
        dg = P._rotated_diagonals(doc.pages[pi - 1])
        cand = [d for d in dg if d["name"].strip()
                and not _is_tvc_name(d["name"])
                and not P._is_party_label_name(d["name"])]
        if len(cand) > len(best):
            best = cand
        for d in dg:
            if _is_tvc_name(d["name"]):
                tvc_min = d["anchor_x"] if tvc_min is None else min(tvc_min, d["anchor_x"])
    best.sort(key=lambda d: d["anchor_x"])
    return best, (tvc_min if tvc_min is not None else VOTE_X_MIN)


def contest_party_codes(doc, pages):
    """Upright party-code header -> [(party, x0)] for party lines (excl
    WRITEIN). The first page carrying >=2 party-code tokens wins."""
    for pi in pages:
        page = doc.pages[pi - 1]
        ws = [dict(w, page=pi) for w in
              page.filter(P._is_upright_obj).extract_words(use_text_flow=False)]
        for line in P.cluster_lines(ws, gap=4):
            codes = []
            for w in line:
                if is_num(w["text"]):
                    continue
                pc = party_of(w["text"])
                if pc and pc != "WRITEIN":
                    codes.append((pc, round(w["x0"])))
            if len(codes) >= 2:
                return codes
    return []


def classify_anchor(anchor, party_codes):
    """Classify one rotated anchor -> {'kind','party'}.
    kind: 'writein' (the WRITE-INS aggregate), 'skip' (subtotal / individual
    write-in / void / blank), or 'party' (a candidate party-line column)."""
    nm = anchor["name"]
    if _is_writein_name(nm):
        return {"kind": "writein", "party": ""}
    if _is_voidblank_name(nm):
        return {"kind": "skip", "party": ""}
    if party_codes:
        pc, dist = min(((pc, abs(anchor["anchor_x"] - x0))
                        for pc, x0 in party_codes), key=lambda t: t[1])
    else:
        pc, dist = (None, 9999)
    if dist <= PARTY_NEAR:
        return {"kind": "party", "party": pc}
    # No party code near: a per-candidate subtotal or an individual write-in
    # breakdown column -- both skipped (WRITE-INS already aggregates them).
    return {"kind": "skip", "party": ""}


def match_number_to_anchor(x1, anchors):
    """Rightmost rotated anchor with anchor_x < x1 (the anchor sits left of its
    number). Returns the anchor dict or None."""
    chosen = None
    for a in anchors:
        if a["anchor_x"] < x1:
            chosen = a  # anchors sorted by x; keep the rightmost below x1
        else:
            break
    return chosen


# Header/title words that begin a non-precinct line (skip even if it has
# numbers, e.g. a party-code header line that pdfplumber glues to a row).
HEADER_FIRST = {
    "VOTE", "FOR", "ONE", "DEM", "REP", "CON", "WOR", "LRC", "IND", "WF",
    "SAM", "LIB", "GRE", "CMN", "Cattaraugus", "Representative", "State",
    "Member", "United", "Electors", "President", "Vice", "Senator",
    "Congress", "District", "County", "Official", "Election", "Results",
    "NOVEMBER", "November", "Total", "TOTAL",
}


def vote_numbers(line, xmin):
    """[(votes, x1)] for number tokens at/above the TVC column start, sorted
    by x1. The leftmost is TOTAL VOTES CAST; the precinct-name number (e.g.
    the '1' in 'Ward 1') sits below xmin and is excluded."""
    vnums = [(toi(w["text"]), w["x1"]) for w in line
             if is_num(w["text"]) and w["x1"] >= xmin]
    vnums.sort(key=lambda v: v[1])
    return vnums


def precinct_name(line, xmin):
    """Tokens before the first vote number (at/above xmin), joined. The
    precinct number is part of the name (e.g. 'Allegany District 1')."""
    toks = []
    for w in line:
        if is_num(w["text"]) and w["x1"] >= xmin:
            break
        toks.append(w["text"])
    return " ".join(toks).strip()


def parse_contest(doc, office, district, pages):
    """Return (rows, totals) for one contest.
    rows: [{'precinct','office','district','party','candidate','votes'}]
    totals: {(candidate, party): county_total} from the PDF TOTAL row, for
    verification.
    """
    anchors, tvc_xmin = contest_anchors(doc, pages)
    party_codes = contest_party_codes(doc, pages)
    cls = [classify_anchor(a, party_codes) for a in anchors]
    xmin = tvc_xmin - 5  # name/vote boundary: leftmost TVC anchor, minus slack

    blocks = []  # [{'name', 'cols': {anchor_x: votes}}]
    cur = None
    total_row = None  # {(candidate,party): votes} from the PDF TOTAL line

    for pi in pages:
        page = doc.pages[pi - 1]
        ws = [dict(w, page=pi) for w in
              page.filter(P._is_upright_obj).extract_words(use_text_flow=False)]
        for line in P.cluster_lines(ws, gap=4):
            if not line:
                continue
            first = line[0]["text"]
            txt = P.line_text(line).strip()
            vnums = vote_numbers(line, xmin)
            # TOTAL row: capture for verification, end the current block.
            if txt.startswith("TOTAL") or txt.startswith("Total"):
                if vnums and total_row is None:
                    total_row = _total_row_map(vnums, anchors, cls)
                cur = None
                continue
            # Sub-row: add into the current precinct block.
            if any(txt.startswith(p) for p in SUBROW_PREFIXES):
                if cur is not None and vnums:
                    _add_block(cur, vnums, anchors, cls)
                continue
            if len(vnums) < 3:
                continue
            if first in HEADER_FIRST or is_num(first):
                continue
            # Precinct main row.
            name = precinct_name(line, xmin)
            if not name:
                continue
            cur = {"name": name, "cols": {}}
            blocks.append(cur)
            _add_block(cur, vnums, anchors, cls)

    rows = []
    for b in blocks:
        for a, c in zip(anchors, cls):
            v = b["cols"].get(a["anchor_x"], 0)
            if c["kind"] == "party":
                rows.append({"precinct": b["name"], "office": office,
                             "district": district, "party": c["party"],
                             "candidate": a["name"], "votes": v})
            elif c["kind"] == "writein":
                rows.append({"precinct": b["name"], "office": office,
                             "district": district, "party": "",
                             "candidate": "Write-in", "votes": v})
    return rows, total_row


def _add_block(block, vnums, anchors, cls):
    """Sum this line's vote columns (drop TVC = leftmost) into the block,
    matching each number to its anchor via the rightmost-below rule."""
    if not vnums:
        return
    nums = vnums[1:]  # drop TOTAL VOTES CAST (leftmost vote column)
    for votes, x1 in nums:
        a = match_number_to_anchor(x1, anchors)
        if a is None:
            continue
        block["cols"][a["anchor_x"]] = block["cols"].get(a["anchor_x"], 0) + votes


def _total_row_map(vnums, anchors, cls):
    """Map a TOTAL row's numbers to {(candidate, party): votes} for the
    party-line + write-in columns (skip TVC, subtotals, void, blank)."""
    out = {}
    nums = vnums[1:]  # drop TVC
    for votes, x1 in nums:
        a = match_number_to_anchor(x1, anchors)
        if a is None:
            continue
        c = cls[anchors.index(a)]
        if c["kind"] == "party":
            out[(a["name"], c["party"])] = out.get((a["name"], c["party"]), 0) + votes
        elif c["kind"] == "writein":
            out[("Write-in", "")] = out.get(("Write-in", ""), 0) + votes
    return out


def main():
    with pdfplumber.open(PDF_PATH) as doc:
        all_rows = []
        problems = []
        for office, district, pages in CONTESTS:
            rows, total_row = parse_contest(doc, office, district, pages)
            all_rows.extend(rows)
            # Verify per-(candidate,party) county totals against the TOTAL row.
            if total_row is None:
                problems.append(f"{office}: no TOTAL row found")
                continue
            summed = {}
            for r in rows:
                k = (r["candidate"], r["party"])
                summed[k] = summed.get(k, 0) + r["votes"]
            for k, tv in sorted(total_row.items()):
                sv = summed.get(k, 0)
                if sv != tv:
                    problems.append(f"{office}: {k} summed={sv} total_row={tv}")
            for k in sorted(set(summed) - set(total_row)):
                problems.append(f"{office}: {k} summed={summed[k]} not in TOTAL row")

    if problems:
        print("=== VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)

    with open(OUT_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district",
                    "party", "candidate", "votes"])
        for r in all_rows:
            w.writerow(["Cattaraugus", r["precinct"], r["office"], r["district"],
                        r["party"], r["candidate"], r["votes"]])

    precincts = {r["precinct"] for r in all_rows}
    offices = []
    for r in all_rows:
        if r["office"] not in offices:
            offices.append(r["office"])
    print(f"Wrote {len(all_rows)} rows, {len(precincts)} precincts, "
          f"offices={offices} -> {OUT_PATH}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())