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

# Full party names and variant spellings -> canonical 3-letter code. NY county
# PDFs spell party headers many ways: 3-letter codes (DEM), parenthesized codes
# ("(DEM)"), full names ("Democratic", "Working Families"), reversed tokens
# ("MED" -> DEM, from right-justified PDFs), and per-county variants ("LaRouc",
# "LRP" -> LaRouche = LAR). party_of() normalizes any of these to a code.
PARTY_FULL = {
    "DEMOCRATIC": "DEM", "DEM": "DEM", "DEMOCRAT": "DEM",
    "REPUBLICAN": "REP", "REP": "REP",
    "CONSERVATIVE": "CON", "CON": "CON",
    "WORKING": "WOR", "FAMILIES": None, "WFP": "WOR", "WF": "WOR",
    "WOR": "WOR", "WORKINGFAMILIES": "WOR",
    "INDEPENDENT": "IND", "INDEPENDENCE": "IND", "IND": "IND",
    "LIBERAL": "LIB", "LIB": "LIB",
    "GREEN": "GRE", "GRE": "GRE",
    "SAM": "SAM",
    "LIBERTARIAN": "LBT", "LBT": "LBT", "LIB": "LIB",
    "LAROUCHE": "LAR", "LAROUC": "LAR", "LAROUCHEPARTY": "LAR", "LRP": "LAR",
    "LAR": "LAR",
    "SAVE": "SAO", "SERVEAMERICA": "SAO", "SAO": "SAO",
    "SOCIALIST": "SWP", "SOCIALISTWORKERS": "SWP", "SWP": "SWP",
    "MARIJUANA": "MRT", "MRT": "MRT",
    "WRITE": None, "WRITEIN": None, "WRITEINS": None,
}


def party_of(tok):
    """Map a header token to a canonical party code (str), 'WRITEIN' for a
    write-in label, or None if it isn't a party/write-in token. Handles
    parenthesized, reversed, full-name, and variant spellings."""
    if not tok:
        return None
    s = tok.strip().strip("()[]{}:,.;")
    if not s:
        return None
    su = s.upper().replace("‐", "-")
    # write-in labels (handle reversed "ni-etirW" too)
    bare = su.replace("-", "").replace(" ", "")
    if bare in {"WRITEIN", "WRITEINS"} or su in WRITEIN or bare[::-1] in {"WRITEIN", "WRITEINS"}:
        return "WRITEIN"
    # direct code
    if su in PARTY_CODES:
        return su
    # reversed token ("MED" -> "DEM")
    if su[::-1] in PARTY_CODES:
        return su[::-1]
    # variant / full-name map
    if su in PARTY_FULL:
        return PARTY_FULL[su]
    # reversed full name ("MEDOCIRP" -> "DEMOCRATIC")
    if su[::-1] in PARTY_FULL:
        return PARTY_FULL[su[::-1]]
    return None

# Office-title patterns -> (canonical office, district-group-regex)
OFFICE_PATTERNS = [
    (re.compile(r"Presidential Electors for President|Electors for President and Vice|Electors for President|President of the United States|President and Vice President|President/Vice President", re.I), "President", None),
    (re.compile(r"\bUS\s+Senator\b", re.I), "U.S. Senate", None),
    (re.compile(r"\bUS\s+Senate\b", re.I), "U.S. Senate", None),
    (re.compile(r"United States Senator", re.I), "U.S. Senate", None),
    (re.compile(r"\bUS\s+Rep\b.*?Congress", re.I), "U.S. House", re.compile(r"(\d+)")),
    (re.compile(r"Representative in Congress,?\s*(\d+)\D", re.I), "U.S. House", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"Representative in Congress", re.I), "U.S. House", None),
    (re.compile(r"State\s+Senator\b.*?Dist", re.I), "State Senate", re.compile(r"(\d+)")),
    (re.compile(r"State Senator,?\s*(\d+)", re.I), "State Senate", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"New York State Senator", re.I), "State Senate", re.compile(r"(\d+)", re.I)),
    (re.compile(r"Member\s+of\s+(?:the\s+)?Assembly\b.*?Dist", re.I), "State Assembly", re.compile(r"(\d+)")),
    (re.compile(r"Member of (the )?Assembly,?\s*(\d+)", re.I), "State Assembly", re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I)),
    (re.compile(r"New York State Assembly", re.I), "State Assembly", re.compile(r"(\d+)", re.I)),
]

# Normalize candidate surnames/fragments to full names for top-of-ticket.
CAND_NORMALIZE = {
    "harris": "Kamala D. Harris",
    "kamala": "Kamala D. Harris",
    "walz": "Kamala D. Harris",
    "trump": "Donald J. Trump",
    "donald": "Donald J. Trump",
    "vance": "Donald J. Trump",
    "gillibrand": "Kirsten E. Gillibrand",
    "kirsten": "Kirsten E. Gillibrand",
    "sapraicone": "Michael D. Sapraicone",
    "sare": "Diane Sare",
    "diane": "Diane Sare",
    "stein": "Jill Stein",
    "jill": "Jill Stein",
    "oliver": "Chase Oliver",
    "chase": "Chase Oliver",
    "de la cruz": "Claudia De la Cruz",
    "claudia": "Claudia De la Cruz",
    "west": "Cornel West",
    "cornel": "Cornel West",
    "sonski": "Peter Sonski",
    "peter sonski": "Peter Sonski",
    # NY 58th SD 2024: Thomas F. O'Mara ran unopposed on REP/CON. pdfplumber
    # mangles his name into a "Thomas Fellers" artifact on the name row in some
    # county PDFs; the party row carries "O'Mara". Normalize both to full name.
    "omara": "Thomas F. O'Mara",
    "fellers": "Thomas F. O'Mara",
}

# Vice-presidential running-mate tokens that appear after "&" on the
# President candidate line (e.g. "Kamala D. Harris & Tim Walz"). These are NOT
# part of any candidate name group: skipping them opens the gap between the
# two presidential candidates so they cluster separately, instead of the VP
# tokens bridging them into one merged group.
VP_TOKENS = {"walz", "vance", "tim", "jd", "j.d."}


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
                 "Totals", "Blank", "Void", "Voids", "Write-in", "Write‐in", "Over",
                 "Under", "Undervotes", "Overvotes", "Undervote", "Overvote",
                 "Scatter", "Scatterings", "Scaterrings", "Scattering",
                 "Ballots", "Registered", "Voters", "Eligible", "Valid",
                 "Votes", "Choice", "Party", "Absentee", "Affidavit",
                 "Number", "Turnout", "%", "Candidates", "Subtotal", "Subtotals",
                 "Continued"}


def is_section_start(line):
    """True if a line starts a new office/table section (requested or not)."""
    if match_office(line) is not None:
        return True
    if VOTE_FOR_RE.search(line):
        # A bare "VOTE FOR ONE" / "(Vote for 1)" sub-header is NOT a new
        # contest — only treat vote-for lines as section starts when they carry
        # other contest-title words (e.g. "State Supreme Court Justice (Vote
        # for 1)"), so a split office title ("Electors for President" / "and
        # Vice President" / "VOTE FOR ONE") stays one section.
        words = re.findall(r"[A-Za-z]{3,}", line)
        content_words = [w for w in words if w.lower() not in ("vote", "for", "one")]
        if content_words:
            return True
    return False


# Row-name header words (the precinct/ED label column, e.g.
# "Town/Ward/District"). These sit left of all party columns; name extraction
# must drop them or they become a fake candidate name.
ROW_LABEL_WORDS = {"town", "ward", "city", "village", "county", "of", "the",
                   "number", "ed", "election", "district", "precinct", "#"}

OFFICE_TITLE_WORDS = {
    "senator", "representative", "assembly", "electors", "president",
    "member", "congress", "senate", "states", "united", "vote", "for",
    "one", "new", "york", "state", "justice", "clerk", "judge", "court",
}


def _is_label_garbage(frag):
    """True if frag is row-label/office header residue rather than a candidate
    name (e.g. 'Town/Ward/District', 'United States Senator')."""
    if not frag:
        return True
    toks = [t for t in frag.replace("/", " ").split() if t not in ("-", "–", "—")]
    if not toks:
        return True
    return all(t.lower() in ROW_LABEL_WORDS or t.lower() in OFFICE_TITLE_WORDS
               or party_of(t) is not None for t in toks)


def _name_tokens(frag):
    """Lowercased alpha token set of a candidate fragment, for subset checks."""
    out = set()
    for t in (frag or "").replace("/", " ").split():
        t = t.strip(".,'").lower()
        if t and t not in ("-", "–", "—", "&", "and"):
            out.add(t)
    return out


def assign_name_groups(header_lines, columns):
    """Cluster candidate-name tokens across header lines into name groups (by
    x-position) and assign each party column a candidate-name fragment by
    nearest positional coverage. Handles fusion, where one candidate name is
    printed once and serves several adjacent party columns (e.g. Gillibrand
    on DEM+WOR): the name group's x-range covers each of those columns.

    Returns {column_index: name_fragment} for party columns only. Only the
    caller decides whether to use this fragment (it is a fallback for when
    walk-left/stacked extraction yields garbage or nothing).
    """
    party_cols = [c for c in columns if c["kind"] == "party"]
    if not party_cols:
        return {}
    leftmost = min(c["x0"] for c in party_cols)
    party_line_ids = {id(c["src_line"]) for c in columns}

    cand = []  # (top, x0, text)
    for ws in header_lines:
        if id(ws) in party_line_ids:
            continue  # the party-code line itself
        txt = line_text(ws)
        if match_office(txt) is not None:
            continue  # office title line
        if VOTE_FOR_RE.search(txt):
            continue  # "(Vote for one)" sub-header
        # row-label line: leading token is a row-name keyword
        ft = ""
        for w in ws:
            if w["text"] not in ("-", "–", "—"):
                ft = w["text"]
                break
        if ft and ft.lower() in ROW_LABEL_WORDS:
            continue
        for w in ws:
            wt = w["text"]
            if wt in ("-", "–", "—"):
                continue
            if party_of(wt) is not None:
                break  # reached a party code -> rest of line is the party header
            if wt in ("&", "and") or wt.lower() in VP_TOKENS:
                continue  # VP running-mate / "&" separator, not a name token
            if w["x0"] < leftmost - 30:
                continue  # row-label column, left of the data area
            if wt.lower() in OFFICE_TITLE_WORDS or wt in HEADER_LABELS:
                continue
            cand.append((w["top"], w["x0"], wt))
    if not cand:
        return {}

    # Cluster by x0 proximity: tokens within 45px horizontally form one candidate.
    # This alone separates candidates in the "one printed name per fusion pair"
    # layout (Ulster: candidates ~100px apart, within-name ~35px). But in the
    # "one printed name per party column" layout (Tioga: fusion columns RE-PRINT
    # the name, so adjacent candidates are only ~30px apart — no x-gap signal at
    # all), clustering merges everyone into one giant group. We recover those by
    # SPLITTING a group at any party column that has a name token anchored at its
    # x0: that anchor marks where the next candidate's name starts.
    party_x0 = [c["x0"] for c in columns if c["kind"] == "party"]
    cand.sort(key=lambda t: t[1])
    groups = [[cand[0]]]
    for t in cand[1:]:
        if t[1] - groups[-1][-1][1] <= 45:
            groups[-1].append(t)
        else:
            groups.append([t])

    def _anchor_col(x0):
        """Party column index whose x0 is within 15px of token x0, else None."""
        for ci, c in enumerate(columns):
            if c["kind"] == "party" and abs(c["x0"] - x0) <= 15:
                return ci
        return None

    # Build final (sub)groups with an optional anchor column. Two header
    # conventions exist:
    #  - "reprint": each fusion column re-prints the candidate's name at its own
    #    x0 (Tioga: Nicholas@173 AND Nicholas@231 for REP+CON; Tompkins: Josh@169
    #    AND Josh@221 for DEM+WOR). A name TOKEN TEXT repeats at >=2 distinct x0
    #    positions. Clustering merges these (candidates sit ~30px apart, no x-gap
    #    signal), so we SPLIT the cluster at every party-column anchor.
    #  - "spanning": one name is printed once across a fusion pair (Ulster:
    #    "Kirsten E. Gillibrand" sits at x198-243 covering DEM@170 + WOR@234).
    #    Each token text appears ONCE, and candidates are ~100px apart so
    #    clustering already separated them — do NOT split, let fusion columns
    #    share the whole group.
    # The token-repeat test reliably tells them apart; splitting a spanning
    # group would fragment a single candidate's name across its fusion columns.
    final = []  # (lo, hi, tokens, anchor_ci_or_None)
    for g in groups:
        xs = [t[1] for t in g]
        lo, hi = min(xs), max(xs)
        anch = {}  # ci -> leftmost in-range token x0
        for t in sorted(g, key=lambda t: (t[1], t[0])):
            ac = _anchor_col(t[1])
            if ac is not None and ac not in anch:
                anch[ac] = t[1]
        text_x0s = {}
        for t in g:
            text_x0s.setdefault(t[2].lower(), set()).add(round(t[1] / 2))
        reprint = any(len(s) >= 2 for s in text_x0s.values())
        if reprint and len(anch) >= 2:
            order = sorted(anch.items(), key=lambda kv: kv[1])
            strong = [ci for ci, _ in order]
            cut_x = [x0 for _, x0 in order]
            sub = [[] for _ in strong]
            for t in g:
                k = 0
                for i, cx in enumerate(cut_x):
                    if t[1] >= cx - 0.5:
                        k = i
                sub[k].append(t)
            for ac, s in zip(strong, sub):
                if s:
                    sxs = [t[1] for t in s]
                    final.append((min(sxs), max(sxs), s, ac))
        else:
            final.append((lo, hi, g, None))

    # Dedup tokens reprinted across sub-tables (same text on a later page's
    # header, possibly at a slightly shifted x0) — keep the first (lowest top)
    # occurrence of each lowercased token text. This collapses e.g.
    # "Michael J. Michael J. Sigler Sigler" -> "Michael J. Sigler". Safe for a
    # single candidate's name (no repeated token text); a merged two-candidate
    # group would not be deduped by this (distinct texts), but that is the
    # split step's job, not dedup's.
    def _dedup(toks):
        seen = set()
        out = []
        for t in sorted(toks, key=lambda t: (t[0], t[1])):
            key = t[2].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    # Map anchor column -> its dedicated subgroup; remaining (fusion, un-anchored)
    # groups assign to columns by nearest x-range.
    anchored_map = {}
    fusion = []
    for lo, hi, g, ac in final:
        g = _dedup(g)
        if ac is not None:
            anchored_map[ac] = g
        else:
            fusion.append((lo, hi, g))

    result = {}
    for ci, col in enumerate(columns):
        if col["kind"] != "party":
            continue
        if ci in anchored_map:
            toks = sorted(anchored_map[ci], key=lambda t: (t[0], t[1]))
            result[ci] = " ".join(t[2] for t in toks).strip()
            continue
        cx0 = col["x0"]
        best, bestd = None, 10 ** 9
        for lo, hi, g in fusion:
            d = 0 if lo <= cx0 <= hi else (lo - cx0 if cx0 < lo else cx0 - hi)
            if d < bestd:
                bestd, best = d, g
        if best is not None:
            toks = sorted(best, key=lambda t: (t[0], t[1]))
            result[ci] = " ".join(t[2] for t in toks).strip()
    return result


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

    # Split into sections. A section starts at a contest title (office match, or
    # a "vote for N" contest line) and ENDS at its trailing "Total" summary row.
    # Closing at the Total row is what prevents a following local office (e.g.
    # "Member of Water Board", "Town Justice") — whose title does not match a
    # requested office and whose "(Vote for 1)" is a bare sub-header — from
    # folding its rows into the previous requested office.
    sections = []
    cur = None
    for ws in lines:
        txt = line_text(ws)
        first = ws[0]["text"].lower() if ws else ""
        second = ws[1]["text"].lower() if len(ws) > 1 else ""
        # A Total/Grand Total row ends the current section (it stays in the
        # section for verification), then the next line begins a new section.
        # "Grand Total" must close too: these tables end with "Grand Total"
        # (first word "Grand"), not bare "Total", so without this the section
        # runs past its table and absorbs the following contest's rows (e.g.
        # a Proposal's Yes/No numbers mis-assigned to the prior office's party
        # columns). Mid-table subtotals like "Lloyd Total" start with the
        # precinct name, so they don't match and don't close here.
        if cur is not None and (first == "total" or (first == "grand" and second == "total")):
            cur["lines"].append(ws)
            sections.append(cur)
            cur = None
            continue
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
        if fw.lower() in ("precinct", "ed", "election district") or party_of(fw) is not None:
            header_lines.append(ws)
            continue
        # office-title lines already split out; treat lines with no numbers as header
        if len(nums) < 2:
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
            p = party_of(t)
            if p is not None and p != "WRITEIN":
                columns.append({"x1": w["x1"], "x0": w["x0"], "party": p,
                                "candidate": "", "kind": "party",
                                "src_line": ws, "tok": w})
            elif p == "WRITEIN" or t in WRITEIN or t.replace("-", "").replace("‐", "").lower().startswith("write"):
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
                if party_of(t) is not None:
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

    # Candidate name per party column, via two strategies:
    #   walk-left: on the party-code token's OWN line, collect tokens left of it
    #     skipping dashes, stopping at another party code / header label / "#".
    #     Correct for "Surname - PARTY" single-line headers (Seneca, Genesee).
    #   stacked: from ALL other header lines, collect non-party/non-label tokens
    #     whose x0 is within 25px of the column's party-code x0, top-to-bottom,
    #     then cut at the first standalone "and" — that drops a running-mate VP
    #     line ("Kamala D. Harris / Tim Walz" -> "Kamala D. Harris"). The 25px
    #     window catches the first token of each candidate name even when it sits
    #     a few px left of the party label (Steuben: "Kamala" at x0=164 vs
    #     "Democratic" at 181). Office-title tokens that fall in the window are
    #     later stripped by normalize_candidate (they are office words like
    #     "president"/"for"). Correct for column-aligned headers where the name
    #     and party label share an x0 (Tioga two-line first+surname headers,
    #     Steuben/Dutchess/Oneida) and for stacked-name headers (Fulton).
    # Prefer the stacked frag when it normalizes to a known top-of-ticket
    # candidate; else prefer a walk-left that does; else prefer whichever is
    # non-empty (stacked first).
    known = set(CAND_NORMALIZE.values())
    # Fallback name fragments from positional candidate-name grouping (handles
    # fusion headers where one name serves adjacent party columns).
    group_frags = assign_name_groups(header_lines, columns)
    for ci, col in enumerate(columns):
        if col["kind"] != "party":
            continue
        line = col["src_line"]
        ptok = col["tok"]
        pidx = line.index(ptok)
        toks = []
        collected = 0
        for j in range(pidx - 1, -1, -1):
            tw = line[j]["text"]
            if tw in ("-", "–", "—"):
                # The dash immediately left of the party code separates
                # "Surname - PARTY"; a dash AFTER we've collected the surname is
                # a column separator (next column's text) — stop there.
                if collected > 0:
                    break
                continue
            if tw == "#" or party_of(tw) is not None or tw in HEADER_LABELS:
                break
            toks.append(tw)
            collected += 1
        toks.reverse()
        wl_frag = " ".join(toks).strip()
        cx0 = col["x0"]
        stacked = []
        for ws in header_lines:
            if ws is line:
                continue
            for w in ws:
                wt = w["text"]
                if party_of(wt) is not None or wt in ("-", "–", "—"):
                    continue
                if wt == "#" or wt in HEADER_LABELS:
                    continue
                if wt in ("&", "and") or wt.lower() in VP_TOKENS:
                    continue  # VP running-mate / "&" separator, not a name token
                if abs(w["x0"] - cx0) <= 25:
                    stacked.append((w["top"], w["x0"], wt))
        stacked.sort()
        parts = [s[2] for s in stacked]
        frag_toks = []
        for t in parts:
            if t.lower() == "and":
                break  # cut running-mate VP line
            frag_toks.append(t)
        st_frag = " ".join(frag_toks).strip()
        wl_norm = normalize_candidate(wl_frag, col["party"])
        st_norm = normalize_candidate(st_frag, col["party"])
        gp_frag = group_frags.get(ci, "")
        gp_norm = normalize_candidate(gp_frag, col["party"])
        # Group fragment completes a partial stacked fragment when it is a
        # strict superset (e.g. stacked caught only the surname "Hinchey" but
        # the name group holds the full "Michelle Hinchey").
        st_toks = _name_tokens(st_frag)
        gp_toks = _name_tokens(gp_frag)
        gp_superset = (gp_toks and (not st_toks or st_toks <= gp_toks)
                       and len(gp_toks) > len(st_toks)
                       and not _is_label_garbage(gp_frag))
        if st_norm in known:
            frag = st_frag
        elif wl_norm in known:
            frag = wl_frag
        elif gp_norm in known:
            frag = gp_frag
        elif gp_superset:
            frag = gp_frag
        elif st_frag and not _is_label_garbage(st_frag):
            frag = st_frag
        elif gp_frag and not _is_label_garbage(gp_frag):
            frag = gp_frag
        elif st_frag:
            frag = st_frag
        elif gp_frag:
            frag = gp_frag
        else:
            frag = wl_frag
        col["cand_frag"] = frag

    # Normalize candidate name (party columns only; writein columns keep their
    # "Write-in" label).
    for col in columns:
        if col["kind"] != "party":
            continue
        frag = col.get("cand_frag", "")
        col["candidate"] = normalize_candidate(frag, col["party"])

    all_cols = columns + [{"x1": x, "kind": "skip"} for x in skip_x1]

    # Split each data row into (precinct_name, vote_numbers) by ADJACENCY, not by
    # a fixed x cutoff. The precinct name may itself end in a number (the ED/ward
    # number, e.g. "Town of Covert 1", "East Bloomfield 2"): such a number sits
    # immediately after the preceding name token (gap <= 10px), whereas the first
    # vote number is separated from the name by a large gap (the vote-column
    # area). So we walk tokens left-to-right: alpha tokens and any number
    # adjacent to the running name go into the name; the first number that is NOT
    # adjacent ends the name and begins the votes. This avoids depending on a
    # name/data x-cutoff derived from (possibly offset) column labels.
    raw_rows = []  # (name, [num_words], is_total)
    for ws in lines[data_start:]:
        name_toks = []
        num_words = []
        name_done = False
        prev_end = None  # x1 of the last token added to the name
        for w in ws:  # ws is sorted by x0
            t = w["text"]
            if is_num(t):
                if name_done:
                    num_words.append(w)
                elif prev_end is not None and (w["x0"] - prev_end) <= 10:
                    name_toks.append(t)  # ED/ward number, part of the name
                    prev_end = w["x1"]
                else:
                    name_done = True
                    num_words.append(w)
            else:
                if not name_done:
                    name_toks.append(t)
                    prev_end = w["x1"]
                # trailing alpha after votes (e.g. write-in detail) ignored
        name = " ".join(name_toks).strip()
        if not name:
            continue
        nmlow = name.lower()
        if nmlow == "total":
            raw_rows.append((name, num_words, True))
            continue
        if "total" in nmlow:
            continue  # "Grand Total" / "Lloyd Total" / "Totals" — subtotal or non-precinct
        if not num_words:
            continue
        raw_rows.append((name, num_words, False))

    # Re-fit each column's x1 to the actual vote-number clusters (the party-code
    # LABEL x1 can be offset from the numbers, e.g. "Surname - DEM" with DEM at
    # x1=290 but numbers at x1~252). Cluster the vote numbers (ED numbers are
    # already excluded by the adjacency split, so cluster count matches the
    # column count when every column has numbers).
    vote_nums = [w["x1"] for _, nws, _ in raw_rows for w in nws]
    if vote_nums:
        sn = sorted(vote_nums)
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
            for col, ctr in zip(sorted(all_cols, key=lambda c: c["x1"]),
                                sorted(clusters)):
                col["x1"] = ctr
        # else: leave label x1s in place (nearest_col tol handles small offsets).

    # Assign each vote number to its nearest column. Numbers mapping to a skip
    # column (ci >= len(columns): Whole#/Total/Blank/Void/etc.) are dropped.
    rows = []
    total_row = {}
    for name, nws, is_total in raw_rows:
        if is_total:
            for w in nws:
                ci = nearest_col(w["x1"], all_cols)
                if ci is not None and ci < len(columns):
                    total_row[ci] = toi(w["text"])
            continue
        row = {"precinct": name, "votes": {}}
        for w in nws:
            ci = nearest_col(w["x1"], all_cols)
            if ci is not None and ci < len(columns):
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
    # some county PDFs reverse every header token ("zlaW" -> "Walz"); try the
    # per-token reverse before giving up on a known top-of-ticket candidate.
    rlow = " ".join(t[::-1] for t in low.split())
    for key, full in CAND_NORMALIZE.items():
        if key in rlow:
            return full
    # strip common header/context words
    strip_words = {"and", "the", "for", "of", "tim", "jd", "j.", "d.", "town",
                   "city", "village", "county", "vote", "one", "candidates",
                   "candidate", "official", "results"}
    # office words that bleed into candidate-name headers
    strip_words |= {"senator", "senate", "assembly", "assemblyman",
                    "assemblywoman", "representative", "member", "councilman",
                    "councilwoman", "council", "justice", "judge", "clerk",
                    "treasurer", "comptroller", "sheriff", "coroner",
                    "supervisor", "mayor", "executive", "attorney", "district",
                    "court", "legislator", "president", "electors", "congress",
                    "united", "states"}
    words = [w for w in frag.split() if w.lower() not in strip_words and w not in ("-",)]
    # drop district ordinals that bleed in from the title ("124th", "3rd")
    words = [w for w in words if not re.fullmatch(r"\d+(st|nd|rd|th)", w, re.I)]
    # If fragment contains a party code, drop it
    words = [w for w in words if party_of(w) is None]
    out = " ".join(words).strip() or frag
    # County PDFs that right-justify headers reverse every token
    # ("snilloC" -> "Collins"). If the stripped result reads lower-first while
    # its per-token reverse reads upper-first, un-reverse it so down-ballot
    # names are right-reading.
    rout = " ".join(t[::-1] for t in out.split())
    fa = next((c for c in out if c.isalpha()), "")
    rfa = next((c for c in rout if c.isalpha()), "")
    if rfa and rfa.isupper() and fa and not fa.isupper():
        out = rout
    return out


# --- All-offices parser -----------------------------------------------------
# parse_pdf() captures only the six issue-listed offices. parse_pdf_all()
# captures EVERY contest in the PDF (using the contest's actual title as the
# office name) by anchoring sections on party-header lines rather than on
# recognized office titles. Reuses parse_section() for column/row parsing.

BOILERPLATE_RE = re.compile(
    r"Detailed Results by Contest|Board of Elections|Statement of Votes? Cast|"
    r"Results per ED|Canvass of|Last Updated|Official Election Results|"
    r"Official Results for|Official Tabulation|Election Book|"
    r"Precinct Results Report|Counting group|Subtot?als by|"
    r"General Election|November\s+\d", re.I)

DISTRICT_RES = [
    re.compile(r"(\d+)\s*(?:st|nd|rd|th)?\s*District", re.I),
    re.compile(r"Congressional\s+District\s*(\d+)", re.I),
    re.compile(r"Senate\s+District\s*(\d+)", re.I),
    re.compile(r"Assembly\s+District\s*(\d+)", re.I),
    re.compile(r"Member\s+of\s+(?:the\s+)?Assembly,?\s*(\d+)", re.I),
    re.compile(r"Senator,?\s*(\d+)", re.I),
    re.compile(r"Representative\s+in\s+Congress,?\s*(\d+)", re.I),
]


def office_from_title(txt):
    """Return (office, district) for a contest title. Known offices get the
    canonical name; everything else keeps a cleaned version of its real title
    so local offices (Town Justice, County Clerk, ...) are preserved."""
    m = match_office(txt)
    if m:
        return m
    t = re.sub(r"\(?\s*Vote\s*for\s*\d*\s*\)?", "", txt, flags=re.I).strip(" -,")
    if not t:
        return None, ""
    district = ""
    for dr in DISTRICT_RES:
        mm = dr.search(t)
        if mm:
            district = mm.group(1)
            break
    office = re.sub(r",?\s*\d+\s*(?:st|nd|rd|th)?\s*District.*$", "", t,
                    flags=re.I).strip(" -,")
    office = re.sub(r",?\s*\d+\s*(?:st|nd|rd|th)?\s*$", "", office).strip(" -,")
    if not office:
        return None, ""
    return office, district


def _is_data_line(ws):
    return sum(1 for w in ws if is_num(w["text"])) >= 2


def first_word(ws):
    for w in ws:
        t = w["text"]
        if t not in ("-", "–", "—"):
            return t
    return ""


def _is_noise_line(ws):
    txt = line_text(ws)
    if re.search(r"Last Updated|Page\s+\d|of\s+\d+|Continued on|^\d+$", txt, re.I):
        return True
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", txt) and re.search(r"\d{1,2}:\d{2}", txt):
        return True
    return False


def _is_pure_votefor(ws):
    txt = line_text(ws).strip().lower()
    return txt.startswith("vote for") or txt.startswith("(vote for")


OFFICE_KEYWORDS = re.compile(
    r"\b(senator|representative|assembly|electors|president|justice|clerk|"
    r"legislator|council|member|supervisor|mayor|sheriff|treasurer|comptroller|"
    r"executive|attorney|judge|court|trustee|assessor|highway|collector|receiver|"
    r"alderman|proposition|proposal|question|amendment|delegate|constable|coroner|"
    r"congress|senate|district attorney)\b", re.I)


def _is_title_like(txt):
    if match_office(txt) is not None:
        return True
    return bool(OFFICE_KEYWORDS.search(txt))


def parse_pdf_all(pdf_path):
    """Capture every contest in the PDF. Sections are anchored on party-header
    lines; the contest title is the office-title line preceding the header
    (often carrying appended candidate totals, e.g. 'United States Senator
    9755 14036 86'). Returns parsed sections with office set to the real title."""
    with pdfplumber.open(pdf_path) as doc:
        all_words = []
        for pi, pg in enumerate(doc.pages):
            for w in pg.extract_words(use_text_flow=False, keep_blank_chars=False):
                ww = dict(w)
                ww["page"] = pi + 1
                all_words.append(ww)
    lines = cluster_lines(all_words, gap=4)
    n = len(lines)
    secs = []
    i = 0
    guard = 0
    while i < n and guard < n + 5:
        guard += 1
        # next party-header line at/after i
        ph = None
        for j in range(i, n):
            if any(party_of(w["text"]) is not None for w in lines[j]):
                ph = j
                break
        if ph is None:
            break
        # title lines (non-data) between i and the party header -- these carry
        # candidate names, '(Vote for one)', 'Candidates', etc. parse_section
        # uses them as header lines for candidate-name extraction.
        title_lines = []
        for k in range(i, ph):
            ws = lines[k]
            if _is_data_line(ws) or _is_noise_line(ws) or _is_pure_votefor(ws):
                continue
            txt = line_text(ws)
            if BOILERPLATE_RE.search(txt) and match_office(txt) is None:
                continue
            title_lines.append(ws)
        # Office title: some PDFs append candidate totals to the title line,
        # making it a *data* line (>=2 numbers) that title_lines skips. Scan
        # [i, ph) for the last title-like data line; fall back to the first
        # title-like non-data title line; else ''.
        title_txt = ""
        for k in range(ph - 1, i - 1, -1):
            ws = lines[k]
            if _is_noise_line(ws):
                continue
            txt = line_text(ws)
            if BOILERPLATE_RE.search(txt) and match_office(txt) is None:
                continue
            if _is_title_like(txt):
                title_txt = txt
                break
        if not title_txt:
            for ws in title_lines:
                if _is_title_like(line_text(ws)):
                    title_txt = line_text(ws)
                    break
        if not title_txt and title_lines:
            # last non-boilerplate title line (drop running-header noise)
            for ws in reversed(title_lines):
                t = line_text(ws)
                if not BOILERPLATE_RE.search(t):
                    title_txt = t
                    break
        # header block: the party-header line itself (+ any non-data lines
        # after it, normally none) until first data row
        header_block = []
        k = ph
        while k < n and not _is_data_line(lines[k]) and not _is_noise_line(lines[k]):
            if _is_pure_votefor(lines[k]):
                k += 1
                continue
            header_block.append(lines[k])
            k += 1
        # data rows until a non-data line (next title) or a Total row
        data = []
        total_line = None
        while k < n:
            ws = lines[k]
            if _is_data_line(ws) and not _is_noise_line(ws):
                data.append(ws)
                k += 1
                continue
            if first_word(ws).lower() == "total" and _is_data_line(ws):
                total_line = ws
                k += 1
                break
            break
        sec_lines = title_lines + header_block + data + ([total_line] if total_line else [])
        office, district = office_from_title(title_txt)
        secs.append({"office": office, "district": district,
                     "lines": sec_lines, "title": title_txt})
        i = k if k > i else i + 1
    results = []
    for sec in secs:
        if sec["office"] is None:
            continue
        parsed = parse_section(sec)
        if parsed and parsed["rows"]:
            results.append(parsed)
    return results


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
    use_all = "--all" in args
    force = "--force" in args
    write = None
    if "--write" in args:
        write = args[args.index("--write") + 1]
    county = args[0]
    pdf = args[1]

    sections = parse_pdf_all(pdf) if use_all else parse_pdf(pdf)
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
    if write and (all_ok or force):
        write_csv(sections, county, write)
    elif write and not all_ok:
        print("\nNOT writing CSV: total mismatches present. (use --force to write anyway)")


if __name__ == "__main__":
    main()