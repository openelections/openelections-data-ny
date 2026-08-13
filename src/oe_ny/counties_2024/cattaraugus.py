"""Cattaraugus County 2024 general (rotated-SOVC PDF, x-anchor geometry).

The hardest rotated SOVC: candidate names are printed at ~60deg and the upright
party-code row is shifted right of the rotated anchors, so columns are matched
by x-coordinate ("rightmost rotated anchor with anchor_x < number x1").  Each
precinct = a main row + four counting-group sub-rows summed.  This reuses the
shared ny2024_rpp_parser (P) rotated-diagonal helpers and emits the reassembled
anchor names verbatim (no CAND map), including 0-vote rows, in source order.
Config-level parse override.
"""
import sys

import pdfplumber

from ..model import REPO_ROOT, CountyConfig, ParseResult

sys.path.insert(0, str(REPO_ROOT))
import ny2024_rpp_parser as P  # noqa: E402

_SRC = REPO_ROOT / "2024" / "pdf_src" / "Cattaraugus.pdf"

CONTESTS = [
    ("President", "", range(1, 5)),
    ("U.S. Senate", "", range(5, 9)),
    ("U.S. House", "23", range(15, 20)),
    ("State Senate", "57", range(20, 23)),
    ("State Assembly", "148", range(23, 28)),
]
_ORDER = [(o, d) for o, d, _ in CONTESTS]

SUBROW_PREFIXES = ("ABS/EVBM", "Early Voting", "Unscanned")
VOTE_X_MIN = 120
PARTY_NEAR = 15
PARTY_OVERRIDES = {"LRC": "LAR"}

HEADER_FIRST = {
    "VOTE", "FOR", "ONE", "DEM", "REP", "CON", "WOR", "LRC", "IND", "WF",
    "SAM", "LIB", "GRE", "CMN", "Cattaraugus", "Representative", "State",
    "Member", "United", "Electors", "President", "Vice", "Senator",
    "Congress", "District", "County", "Official", "Election", "Results",
    "NOVEMBER", "November", "Total", "TOTAL",
}


def is_num(t):
    return t.replace(",", "").isdigit()


def toi(t):
    return int(t.replace(",", ""))


def party_of(tok):
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
    return {"kind": "skip", "party": ""}


def match_number_to_anchor(x1, anchors):
    chosen = None
    for a in anchors:
        if a["anchor_x"] < x1:
            chosen = a
        else:
            break
    return chosen


def vote_numbers(line, xmin):
    vnums = [(toi(w["text"]), w["x1"]) for w in line
             if is_num(w["text"]) and w["x1"] >= xmin]
    vnums.sort(key=lambda v: v[1])
    return vnums


def precinct_name(line, xmin):
    toks = []
    for w in line:
        if is_num(w["text"]) and w["x1"] >= xmin:
            break
        toks.append(w["text"])
    return " ".join(toks).strip()


def _add_block(block, vnums, anchors, cls):
    if not vnums:
        return
    for votes, x1 in vnums[1:]:
        a = match_number_to_anchor(x1, anchors)
        if a is None:
            continue
        block["cols"][a["anchor_x"]] = block["cols"].get(a["anchor_x"], 0) + votes


def parse_contest(doc, office, district, pages):
    anchors, tvc_xmin = contest_anchors(doc, pages)
    party_codes = contest_party_codes(doc, pages)
    cls = [classify_anchor(a, party_codes) for a in anchors]
    xmin = tvc_xmin - 5
    blocks = []
    cur = None
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
            if txt.startswith("TOTAL") or txt.startswith("Total"):
                cur = None
                continue
            if any(txt.startswith(p) for p in SUBROW_PREFIXES):
                if cur is not None and vnums:
                    _add_block(cur, vnums, anchors, cls)
                continue
            if len(vnums) < 3:
                continue
            if first in HEADER_FIRST or is_num(first):
                continue
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
                rows.append((b["name"], office, district, c["party"], a["name"], v))
            elif c["kind"] == "writein":
                rows.append((b["name"], office, district, "", "Write-in", v))
    return rows


def _parse(cfg: CountyConfig) -> ParseResult:
    rows, prec_order, seen = [], [], set()
    with pdfplumber.open(cfg.resolve_source()) as doc:
        for office, district, pages in CONTESTS:
            for r in parse_contest(doc, office, district, pages):
                if r[0] not in seen:
                    seen.add(r[0])
                    prec_order.append(r[0])
                rows.append(r)
    return ParseResult(rows=rows, prec_order=prec_order, od_seen=list(_ORDER))


CONFIG = CountyConfig(
    county="Cattaraugus",
    slug="cattaraugus",
    engine="sovc_table",
    source=_SRC,
    office_order=_ORDER,
    cand={},
    anchors={},
    sort_output=False,
    parse=_parse,
)
