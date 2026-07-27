#!/usr/bin/env python3
"""Parser for the NY BOE "Results per Precinct" / "Results per ED" PDF format
(2024 general). Each office is a section: an office-title line, a column header
whose vote columns are labeled `Candidate - PARTY`, precinct rows, and a final
`Total` row. Vote columns are mapped to precinct numbers by x-coordinate (the
numbers are right-aligned, so we match by right edge x1).

Output: 20241105__ny__general__{county}__precinct.csv with columns
county,precinct,office,district,party,candidate,votes  (+ optional methods).

Usage:
  python3 ny2024_rpp_parser.py <county> <pdf_path> [--write <out_csv>] [--verify]
"""
import csv
import re
import sys
from collections import defaultdict

import pdfplumber

PARTY_CODES = {
    "DEM", "REP", "CON", "WOR", "WF", "WFP", "LAR", "IND", "GRE", "SAM",
    "LIB", "WEP", "LBT", "ALN", "NLP", "SCP", "RFG", "UPN", "SAO", "PSL",
    "SWP", "WAP", "MRT", "IGP",
}
WRITEIN = {"Write-in", "Write‐in", "Write-ins", "Write‐ins", "WriteIn"}

# Office-title patterns -> (canonical office, district-group-regex)
OFFICE_PATTERNS = [
    (re.compile(r"Presidential Electors for President|Electors for President and Vice|President of the United States|President and Vice President", re.I), "President", None),
    (re.compile(r"United States Senator", re.I), "U.S. Senate", None),
    (re.compile(r"Representative in Congress,?\s*(\d+)\D", re.I), "U.S. House", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"Representative in Congress", re.I), "U.S. House", None),
    (re.compile(r"State Senator,?\s*(\d+)", re.I), "State Senate", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"New York State Senator", re.I), "State Senate", re.compile(r"(\d+)", re.I)),
    (re.compile(r"Member of (the )?Assembly,?\s*(\d+)", re.I), "State Assembly", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"New York State Assembly", re.I), "State Assembly", re.compile(r"(\d+)", re.I)),
]

# Normalize candidate surnames/fragments to full names for top-of-ticket.
CAND_NORMALIZE = {
    "harris": "Kamala D. Harris",
    "walz": "Kamala D. Harris",
    "trump": "Donald J. Trump",
    "vance": "Donald J. Trump",
    "gillibrand": "Kirsten E. Gillibrand",
    "sapraicone": "Michael D. Sapraicone",
    "sare": "Diane Sare",
    "stein": "Jill Stein",
    "oliver": "Chase Oliver",
    "de la cruz": "Claudia De la Cruz",
    "west": "Cornel West",
    "sonski": "Peter Sonski",
    # NY 58th SD 2024: Thomas F. O'Mara ran unopposed on REP/CON. pdfplumber
    # mangles his name into a "Thomas Fellers" artifact on the name row in some
    # county PDFs; the party row carries "O'Mara". Normalize both to full name.
    "omara": "Thomas F. O'Mara",
    "fellers": "Thomas F. O'Mara",
}


def is_num(t):
    return t.replace(",", "").isdigit()


def toi(t):
    return int(t.replace(",", ""))


def cluster_lines(words, gap=4):
    """Group words into visual lines by page+top (single-linkage)."""
    ws = sorted(words, key=lambda w: (w["page"], w["top"], w["x0"]))
    out, cur, prev = [], [], None
    for w in ws:
        key = (w["page"], w["top"])
        if prev is None or (w["page"] == prev[0] and abs(w["top"] - prev[1]) <= gap):
            cur.append(w)
        else:
            out.append(cur)
            cur = [w]
        prev = (w["page"], w["top"])
    if cur:
        out.append(cur)
    return [sorted(c, key=lambda w: w["x0"]) for c in out]


def line_text(ws):
    return " ".join(w["text"] for w in ws)


def match_office(line):
    """Return (canonical_office, district_str_or_'') if line is a requested
    office title, else None."""
    s = line
    for pat, office, distre in OFFICE_PATTERNS:
        if pat.search(s):
            d = ""
            if distre:
                m = distre.search(s)
                if m:
                    d = m.group(1)
            return office, d
    return None


VOTE_FOR_RE = re.compile(r"vote\s*for", re.I)
# Labels that head the ROW-NAME field (the precinct/ED label), not a vote
# column. These must NOT become skip columns, or they drag the name/data cutoff
# leftward and split the precinct name.
NAME_LABELS = {"Precinct", "ED", "Election", "District", "Precincts"}
HEADER_LABELS = {"Precinct", "ED", "Election", "District", "Whole", "Total",
                 "Blank", "Void", "Write-in", "Write‐in", "Over", "Under",
                 "Scatter", "Scatterings", "Ballots", "Registered", "Voters",
                 "Eligible", "Valid", "Votes", "Choice", "Party", "Absentee",
                 "Affidavit", "Number", "Turnout", "%"}


def is_section_start(line):
    """True if a line starts a new office/table section (requested or not)."""
    if match_office(line) is not None:
        return True
    if VOTE_FOR_RE.search(line):
        return True
    return False


def parse_pdf(pdf_path):
    """Return list of sections: each {office, district, columns, rows, total_row}.

    columns: list of dicts {x1, party, candidate, kind}  kind in {party, writein}
    rows: list of (precinct_name, {col_index: votes})
    total_row: dict {col_index: votes} from the 'Total' summary row, for verification
    """
    with pdfplumber.open(pdf_path) as doc:
        all_words = []
        for pi, pg in enumerate(doc.pages):
            for w in pg.extract_words(use_text_flow=False, keep_blank_chars=False):
                ww = dict(w)
                ww["page"] = pi + 1
                all_words.append(ww)
    lines = cluster_lines(all_words, gap=4)

    # Tag each line: section start (any office/table header) or not. Split into
    # sections at EVERY section start, then keep only requested offices.
    sections = []
    cur = None
    for ws in lines:
        txt = line_text(ws)
        if is_section_start(txt):
            if cur:
                sections.append(cur)
            m = match_office(txt)
            if m:
                office, district = m
            else:
                office, district = None, ""  # non-requested office
            cur = {"office": office, "district": district, "lines": [], "title": txt}
        elif cur is not None:
            cur["lines"].append(ws)
    if cur:
        sections.append(cur)

    results = []
    for sec in sections:
        if sec["office"] is None:
            continue  # drop non-requested offices (Supreme Court, proposals, etc.)
        parsed = parse_section(sec)
        if parsed:
            results.append(parsed)
    return results


def parse_section(sec):
    office, district = sec["office"], sec["district"]
    lines = sec["lines"]
    if not lines:
        return None

    # Find the party-code header line: the line with the most party-code tokens.
    # (Lines before the first data line are header lines.)
    # A data line: first token is alpha, contains >=1 number, and isn't a header.
    def first_word(ws):
        for w in ws:
            t = w["text"]
            if t not in ("-", "–", "—"):
                return t
        return ""

    # Identify header lines = leading lines that are NOT data rows.
    header_lines = []
    data_start = 0
    for i, ws in enumerate(lines):
        fw = first_word(ws)
        nums = [w for w in ws if is_num(w["text"])]
        # Precinct/ED header keyword lines are headers
        if fw.lower() in ("precinct", "ed", "election district") or fw.upper() in PARTY_CODES:
            header_lines.append(ws)
            continue
        # office-title lines already split out; treat lines with no numbers as header
        if not nums:
            header_lines.append(ws)
            continue
        # has numbers -> data row
        data_start = i
        break
    # include any remaining header-like lines just before data (e.g. party row
    # that might have numbers? unlikely)
    # Actually the party-code row has no numbers, so it's already in header_lines.

    # Collect party-code and write-in tokens across ALL header lines. Some
    # formats split party codes across two lines (e.g. Fulton: "- CON - REP LAR"
    # on one line, "- WOR - DEM" on the next). Each such token at a distinct x
    # is one vote column. Keep the source line + token for candidate-name walk.
    columns = []
    for ws in header_lines:
        for w in ws:
            t = w["text"]
            if t.upper() in PARTY_CODES:
                columns.append({"x1": w["x1"], "x0": w["x0"], "party": t.upper(),
                                "candidate": "", "kind": "party",
                                "src_line": ws, "tok": w})
            elif t in WRITEIN or t.replace("-", "").replace("‐", "").lower().startswith("write"):
                columns.append({"x1": w["x1"], "x0": w["x0"], "party": "",
                                "candidate": "Write-in", "kind": "writein",
                                "src_line": ws, "tok": w})
    # Dedup columns at near-identical x0 (a code re-printed on a second header
    # line at the same x). Adjacent real columns are ~50px apart, so a 5px merge
    # is safe.
    columns.sort(key=lambda c: c["x0"])
    dedup = []
    for c in columns:
        if dedup and abs(c["x0"] - dedup[-1]["x0"]) < 5:
            continue
        dedup.append(c)
    columns = dedup
    if not any(c["kind"] == "party" for c in columns):
        return None  # no party columns -> not a candidate results table

    # Build SKIP columns from header labels (Whole #, Total, Blank, Void,
    # Undervotes, Overvotes, Scatterings, Ballots, etc.) so numbers under them
    # are not misassigned to the nearest party column. Scan all header lines.
    skip_x1 = []
    for ws in header_lines:
        for w in ws:
            t = w["text"]
            tl = t.lower()
            if t in NAME_LABELS:
                continue  # row-name header, not a vote column
            if t == "#" or tl in {h.lower() for h in HEADER_LABELS}:
                if t.upper() in PARTY_CODES:
                    continue
                # avoid duplicating a party/write-in column already captured
                if any(abs(c["x1"] - w["x1"]) < 5 for c in columns):
                    continue
                skip_x1.append(w["x1"])
    # dedup nearby skip x1s: "Whole" and "#" (or a multi-word header) can yield
    # two tokens for one column ~8px apart — merge any within 20px into one.
    skip_sorted = sorted(set(skip_x1))
    skip_x1 = []
    for x in skip_sorted:
        if skip_x1 and x - skip_x1[-1] <= 20:
            skip_x1[-1] = (skip_x1[-1] + x) / 2  # merge into the previous column
        else:
            skip_x1.append(x)

    # Candidate name per party column.
    # Strategy 1 (single-line "Surname - PARTY"): walk left on the party-code
    # token's OWN line, skipping dashes, stopping at another party code / header
    # label / "#".
    # Strategy 2 (stacked names, e.g. Fulton: first/middle/surname on separate
    # lines all aligned to the column's left edge x0): collect aligned non-party,
    # non-label, non-dash tokens from ALL header lines whose x0 is within 15px of
    # the column's x0, in top-to-bottom reading order.
    for col in columns:
        if col["kind"] != "party":
            continue
        line = col["src_line"]
        ptok = col["tok"]
        idx = line.index(ptok)
        toks = []
        for j in range(idx - 1, -1, -1):
            tw = line[j]["text"]
            if tw in ("-", "–", "—"):
                continue  # skip dash within "Surname - PARTY"
            if tw == "#" or tw.upper() in PARTY_CODES or tw in HEADER_LABELS:
                break
            toks.append(tw)
        toks.reverse()
        frag = " ".join(toks).strip()
        if not frag:
            cx0 = col["x0"]
            stacked = []
            for ws in header_lines:
                if ws is line:
                    continue
                for w in ws:
                    wt = w["text"]
                    if wt.upper() in PARTY_CODES or wt in ("-", "–", "—"):
                        continue
                    if wt == "#" or wt in HEADER_LABELS:
                        continue
                    if abs(w["x0"] - cx0) <= 15:
                        stacked.append((w["top"], w["x0"], wt))
            stacked.sort()
            frag = " ".join(s[2] for s in stacked).strip()
        col["cand_frag"] = frag

    # Normalize candidate name (party columns only; writein columns keep their
    # "Write-in" label).
    for col in columns:
        if col["kind"] != "party":
            continue
        frag = col.get("cand_frag", "")
        col["candidate"] = normalize_candidate(frag, col["party"])

    # X-position cutoff separating the precinct-name field (left) from the vote
    # columns (right). The precinct name may itself end in a number (the ED
    # number, e.g. "Town of Covert 1"), so we cannot split name/data by
    # "first numeric token". Instead: name = all tokens whose right edge (x1) is
    # left of the leftmost vote column; votes = numeric tokens at/after that
    # cutoff. Vote numbers are right-aligned at column x1s, so a 30px margin
    # below the leftmost column x1 safely holds the name field (incl. ED number)
    # while keeping every vote number (whose x0 is within ~20px of its column
    # x1) on the vote side.
    all_cols = columns + [{"x1": x, "kind": "skip"} for x in skip_x1]
    col_x1s = [c["x1"] for c in all_cols]
    name_cutoff = (min(col_x1s) - 30) if col_x1s else 0

    # The party-code LABEL x1 can be offset from the actual vote numbers' x1
    # (e.g. Genesee House: "Surname - DEM" has DEM at x1=290 but the numbers
    # right-align at x1~252, under the surname). Re-fit each column's x1 to the
    # data numbers: cluster every data-row number by x1, then assign clusters to
    # columns by left-to-right order (both sorted by x). This is robust as long
    # as every column has numbers (zeros count) so cluster count == column count.
    data_nums = []
    for ws in lines[data_start:]:
        for w in ws:
            if is_num(w["text"]) and w["x0"] >= name_cutoff:
                data_nums.append(w["x1"])
    if data_nums:
        sn = sorted(data_nums)
        clusters = []
        cur = [sn[0]]
        for x in sn[1:]:
            if x - cur[-1] <= 20:
                cur.append(x)
            else:
                clusters.append(sum(cur) / len(cur))
                cur = [x]
        clusters.append(sum(cur) / len(cur))
        if len(clusters) == len(all_cols):
            ordered_cols = sorted(all_cols, key=lambda c: c["x1"])
            for col, ctr in zip(ordered_cols, sorted(clusters)):
                col["x1"] = ctr
        # else: leave label x1s in place (nearest_col with tol handles small
        # offsets; a count mismatch usually means a wholly-empty column).

    # Parse data rows: lines from data_start onward. "Total" rows are captured
    # for verification; other rows are precinct data.
    rows = []
    total_row = {}
    for ws in lines[data_start:]:
        name_toks = [w["text"] for w in ws if w["x1"] < name_cutoff]
        num_toks = [w for w in ws if is_num(w["text"]) and w["x0"] >= name_cutoff]
        name = " ".join(name_toks).strip()
        if not name:
            continue
        nmlow = name.lower()
        if nmlow == "total":
            for w in num_toks:
                ci = nearest_col(w["x1"], all_cols)
                if ci is not None and ci < len(columns):
                    total_row[ci] = toi(w["text"])
            continue
        # Other summary rows ("Grand Total", "Totals", "Total Votes Cast", etc.)
        # are not precincts — skip them entirely.
        if "total" in nmlow:
            continue
        if not num_toks:
            continue
        row = {"precinct": name, "votes": {}}
        for w in num_toks:
            ci = nearest_col(w["x1"], all_cols)
            if ci is not None and ci < len(columns):
                # ci >= len(columns) -> a skip column (Whole#/Total/Blank/Void):
                # drop the number rather than misassigning it to a party column.
                row["votes"][ci] = row["votes"].get(ci, 0) + toi(w["text"])
        rows.append(row)

    return {
        "office": office, "district": district, "columns": columns,
        "rows": rows, "total_row": total_row, "title": sec["title"],
    }


def nearest_col(x1, columns, tol=40):
    best, bestd = None, tol
    for i, c in enumerate(columns):
        d = abs(c["x1"] - x1)
        if d <= bestd:
            bestd = d
            best = i
    return best


def normalize_candidate(frag, party):
    if not frag:
        return ""
    low = frag.lower().replace("'", "").replace(".", " ")
    for key, full in CAND_NORMALIZE.items():
        if key in low:
            return full
    # strip common header words
    words = [w for w in frag.split() if w.lower() not in ("and", "the", "for", "of", "tim", "jd", "j.", "d.") and w not in ("-",)]
    # If fragment contains a party code, drop it
    words = [w for w in words if w.upper() not in PARTY_CODES]
    return " ".join(words).strip() or frag


def write_csv(sections, county, out_path):
    # county column is Title Case per repo convention ("Seneca"); the filename
    # (out_path) is lowercase per the issue spec.
    county_title = county.title()
    header = ["county", "precinct", "office", "district", "party", "candidate", "votes"]
    n = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for s in sections:
            office = s["office"]
            district = s["district"]
            for r in s["rows"]:
                prec = r["precinct"]
                for i, c in enumerate(s["columns"]):
                    if c["kind"] not in ("party", "writein"):
                        continue
                    v = r["votes"].get(i, 0)
                    w.writerow([county_title, prec, office, district, c["party"],
                                c["candidate"], v])
                    n += 1
    print(f"wrote {n} rows to {out_path}")
    return n


def main():
    args = sys.argv[1:]
    verify = "--verify" in args
    write = None
    if "--write" in args:
        write = args[args.index("--write") + 1]
    county = args[0]
    pdf = args[1]

    sections = parse_pdf(pdf)
    print(f"Parsed {len(sections)} office sections for {county}")
    all_ok = True
    for s in sections:
        cols = s["columns"]
        print(f"\n== {s['office']} (district={s['district']!r}) {len(s['rows'])} precincts ==")
        for i, c in enumerate(cols):
            print(f"   col{i}: party={c['party']!r:6} cand={c['candidate']!r}  (frag={c.get('cand_frag','')!r})")
        if s["total_row"]:
            for i, c in enumerate(cols):
                tot = s["total_row"].get(i)
                if tot is None:
                    continue
                sump = sum(r["votes"].get(i, 0) for r in s["rows"])
                ok = sump == tot
                if not ok:
                    all_ok = False
                print(f"     total col{i} {c['party']} {c['candidate']}: "
                      f"{'OK' if ok else f'MISMATCH pdf={tot} parsed={sump}'}")
        else:
            print("     (no Total row to verify)")
    if write and all_ok:
        write_csv(sections, county, write)
    elif write and not all_ok:
        print("\nNOT writing CSV: total mismatches present.")


if __name__ == "__main__":
    main()