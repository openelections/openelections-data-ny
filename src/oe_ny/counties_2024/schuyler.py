"""Schuyler County 2024 general (NYS SOVC PDF, counting groups + non-CC/CC merge).

The most involved text report: each contest is printed per counting group; only
'All' is the grand total (House 24 has no 'All' page, so its sub-groups are
summed).  Within a group each precinct has a non-CC and a CC row that are merged.
Lines are walked in document order tracking office + counting group; Assembly's
'All' page is read via extract_tables (its CC rows carry an extra column).
Candidate columns/names are hardcoded per office.  Output in source order.
Config-level parse override.
"""
import re
from collections import defaultdict

from ..model import CountyConfig, ParseResult

_TOWNS = {"Catharine", "Cayuta", "Dix", "Hector", "Montour", "Orange",
          "Reading", "Tyrone"}

OFFICES = {
    ("President", ""): {"N": 14, "candidates": [
        (0, "DEM", "Kamala D. Harris"), (1, "REP", "Donald J. Trump"),
        (2, "CON", "Donald J. Trump"), (3, "WOR", "Kamala D. Harris")],
        "writein_cols": [4, 5, 6, 7, 8, 11], "tv": 13},
    ("U.S. Senate", ""): {"N": 10, "candidates": [
        (0, "DEM", "Kirsten E. Gillibrand"), (1, "REP", "Michael D. Sapraicone"),
        (2, "CON", "Michael D. Sapraicone"), (3, "WOR", "Kirsten E. Gillibrand"),
        (4, "LAR", "Diane Sare")], "writein_cols": [7], "tv": 9},
    ("U.S. House", "23"): {"N": 8, "candidates": [
        (0, "DEM", "Thomas A. Carle"), (1, "REP", "Nicholas A. Langworthy"),
        (2, "CON", "Nicholas A. Langworthy")], "writein_cols": [5], "tv": 7},
    ("U.S. House", "24"): {"N": 8, "candidates": [
        (0, "DEM", "David Wagenhauser"), (1, "REP", "Claudia Tenney"),
        (2, "CON", "Claudia Tenney")], "writein_cols": [5], "tv": 7},
    ("State Senate", "58"): {"N": 8, "candidates": [
        (0, "REP", "Thomas F. O'Mara"), (1, "CON", "Thomas F. O'Mara")],
        "writein_cols": [2, 5], "tv": 7},
    ("State Assembly", "132"): {"N": 7, "candidates": [
        (0, "REP", "Philip A. Palmesano"), (1, "CON", "Philip A. Palmesano")],
        "writein_cols": [4], "tv": 6},
}
_USES_ALL = {("President", ""), ("U.S. Senate", ""), ("U.S. House", "23"),
             ("State Senate", "58"), ("State Assembly", "132")}
_ORDER = list(OFFICES)

_AFTER_RE = re.compile(r"^(?:\d+ )?Leg \d+$|^\d+$")
_LOCAL_KEYS = ("Council Member", "Town of", "Justice", "Judge", "Clerk",
               "Superintendent", "Proposition", "Question", "Referendum",
               "Member of the County", "Ballot Question")
_NOISE = ("Statement of Vote Cast", "file://", "file:", ".HTML", "vote for",
          "District type:")


def detect_office(s):
    if "Electors for President" in s:
        return ("President", "")
    if "US Senate" in s and "Schuyler" in s:
        return ("U.S. Senate", "")
    if "Representative In Congress" in s:
        m = re.search(r"(\d+)\w*\s*Congressional", s)
        return ("U.S. House", m.group(1) if m else "")
    if "New York State Senator" in s:
        m = re.search(r"(\d+)\w*\s*District", s)
        return ("State Senate", m.group(1) if m else "")
    if "Member of Assembly" in s:
        m = re.search(r"(\d+)\w*\s*District", s)
        return ("State Assembly", m.group(1) if m else "")
    return None


def _ci(s):
    s = (s or "").replace(",", "").strip()
    return int(s) if s.isdigit() else 0


def _is_int(t):
    return bool(t) and t.replace(",", "").isdigit()


def _trailing_ints(tokens, n):
    if len(tokens) < n:
        return None
    tail = tokens[-n:]
    if not all(_is_int(t) for t in tail):
        return None
    return tokens[:-n], [int(t.replace(",", "")) for t in tail]


def _starts_town_or_cc(tokens):
    return bool(tokens) and (tokens[0] in _TOWNS or tokens[0] == "CC")


def _precinct(tokens):
    toks = list(tokens)
    if toks and toks[0] == "CC":
        toks = toks[1:]
    town = next((t for t in toks if t in _TOWNS), None)
    if town is None or "Leg" not in toks:
        return None
    leg_idx = toks.index("Leg")
    if leg_idx + 1 >= len(toks) or not toks[leg_idx + 1].isdigit():
        return None
    leg = toks[leg_idx + 1]
    town_idx = toks.index(town)
    ed = next((et for et in toks[town_idx + 1:leg_idx] if et.isdigit()), "1")
    return f"{town} {ed} Leg {leg}"


def reassemble(lines, n):
    precincts = defaultdict(lambda: [0] * n)
    consumed = set()
    for i, raw in enumerate(lines):
        if i in consumed:
            continue
        line = raw.strip()
        if not line:
            continue
        tokens = line.split()
        head = tokens[0].upper() if tokens else ""
        if head in ("TOTAL", "SUB-TOTAL", "SUBTOTAL", "CUMULATIVE"):
            consumed.add(i)
            continue
        ti = _trailing_ints(tokens, n)
        if ti is None:
            continue
        lead, votes = ti
        if lead and not _starts_town_or_cc(lead):
            continue
        before = []
        if not lead and i - 1 >= 0 and (i - 1) not in consumed:
            btoks = lines[i - 1].strip().split()
            if btoks and _starts_town_or_cc(btoks) and _trailing_ints(btoks, n) is None:
                before = btoks
                consumed.add(i - 1)
        after = []
        if i + 1 < len(lines) and (i + 1) not in consumed:
            ntoks = lines[i + 1].strip().split()
            if (ntoks and not _starts_town_or_cc(ntoks)
                    and _trailing_ints(ntoks, n) is None
                    and _AFTER_RE.match(lines[i + 1].strip())):
                after = ntoks
                consumed.add(i + 1)
        name = _precinct(before + lead + after)
        consumed.add(i)
        if name is None:
            continue
        cur = precincts[name]
        for k in range(n):
            cur[k] += votes[k]
    return precincts


def _is_noise(line):
    return any(k in line for k in _NOISE)


def build_buckets(pdf):
    buckets = defaultdict(list)
    cur_office = cur_district = cur_group = None
    for page in pdf.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            od = detect_office(line)
            if od is not None:
                cur_office, cur_district = od
                cur_group = None
                continue
            if any(k in line for k in _LOCAL_KEYS):
                cur_office = cur_district = cur_group = None
                continue
            if line.startswith("Counting group:"):
                cur_group = line.split(":", 1)[1].strip()
                continue
            if cur_office is None or cur_group is None:
                continue
            if (cur_office, cur_district) in OFFICES and not _is_noise(line):
                buckets[(cur_office, cur_district, cur_group)].append(line)
    return buckets


def parse_table_rows(table, n):
    precincts = defaultdict(lambda: [0] * n)
    for r in table[1:]:
        if not r:
            continue
        name = (r[0] or "").replace("\n", " ").strip()
        if not name:
            continue
        head = name.split()[0].upper()
        if head in ("SCHUYLER", "SUB-TOTAL", "SUBTOTAL", "TOTAL", "CUMULATIVE"):
            continue
        if len(r) < n + 1:
            continue
        pname = _precinct(name.split())
        if pname is None:
            continue
        cur = precincts[pname]
        for k in range(n):
            cur[k] += _ci(r[k + 1])
    return precincts


def find_office_all_table(pdf, surname):
    for page in pdf.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables:
            if not table or not table[0]:
                continue
            header = table[0]
            if (header[0] or "").strip() == "ED" and any(
                    surname in (c or "") for c in header):
                return table
    return None


def _emit(office, district, cfg, name, votes, out):
    for col, party, cand in cfg["candidates"]:
        if votes[col] > 0:
            out.append((name, office, district, party, cand, votes[col]))
    wv = sum(votes[c] for c in cfg["writein_cols"])
    if wv > 0:
        out.append((name, office, district, "", "Write-in", wv))


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    buckets = build_buckets(pdf)
    out = []

    for od, ocfg in OFFICES.items():
        office, district = od
        n = ocfg["N"]
        if od == ("State Assembly", "132"):
            table = find_office_all_table(pdf, "Palmesano")
            if table is None:
                continue
            precincts = parse_table_rows(table, n)
        elif od in _USES_ALL:
            lines = buckets.get((office, district, "All"), [])
            if not lines:
                continue
            precincts = reassemble(lines, n)
        else:
            sub_groups = sorted(g for (o, d, g) in buckets
                                if (o, d) == od and g != "All")
            precincts = defaultdict(lambda: [0] * n)
            for g in sub_groups:
                for name, votes in reassemble(buckets[(office, district, g)], n).items():
                    cur = precincts[name]
                    for k in range(n):
                        cur[k] += votes[k]
        for name, votes in precincts.items():
            _emit(office, district, ocfg, name, votes, out)

    prec_order = []
    seen = set()
    for r in out:
        if r[0] not in seen:
            seen.add(r[0])
            prec_order.append(r[0])
    return ParseResult(rows=out, prec_order=prec_order, od_seen=list(_ORDER))


CONFIG = CountyConfig(
    county="Schuyler",
    slug="schuyler",
    engine="text_report",
    source_name="Schuyler.pdf",
    office_order=_ORDER,
    cand={},
    anchors={},
    sort_output=False,
    parse=_parse,
)
