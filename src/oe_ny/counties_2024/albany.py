"""Albany County 2024 general (text SOVC PDF, natural_pdf; named write-ins kept).

Per-precinct multi-page report.  Party-line rows '<CODE> <name> <total> <pct%>
...' and individual 'Write-In: <name> ...' rows are emitted with the source name
verbatim (no CAND map); Albany uniquely keeps individual named write-ins
(party '').  0-vote rows and aggregate/total rows are omitted.  Output in source
order.  Config-level parse override.
"""
import re

from ..model import CountyConfig, ParseResult

_ORDER = [("President", ""), ("U.S. Senate", ""), ("U.S. House", ""),
          ("State Senate", ""), ("State Assembly", "")]

_OFFICE_RULES = [
    (re.compile(r"^Electors for President and Vice President$"), "President", ""),
    (re.compile(r"^United States Senator$"), "U.S. Senate", ""),
    (re.compile(r"^Representative in Congress (\d+)(?:st|nd|rd|th)? District$"),
     "U.S. House", None),
    (re.compile(r"^State Senator (\d+)(?:st|nd|rd|th)? District$"),
     "State Senate", None),
    (re.compile(r"^Member of Assembly (\d+)(?:st|nd|rd|th)? District$"),
     "State Assembly", None),
]

_PARTY_MAP = {"DEM": "DEM", "REP": "REP", "WFP": "WOR", "CON": "CON", "LAR": "LAR",
              "IND": "IND", "GRE": "GRE", "LIB": "LIB", "SAM": "SAM",
              "CMN": "CMN", "WOR": "WOR"}
_ALT = "|".join(_PARTY_MAP)
_NUM = r"[\d,]+"
_PARTY_ROW = re.compile(rf"^(?P<party>{_ALT})\s+(?P<name>.+?)\s+(?P<votes>{_NUM})\s+\d+\.\d+%")
_WRITEIN_ROW = re.compile(rf"^Write-In:\s+(?P<name>.+?)\s+(?P<votes>{_NUM})\s+\d+\.\d+%")
_TOTALS_BY_CAND = "Totals by Candidate"
_SKIP = ("Vote For", "TOTAL VOTE", "Day Voting", "Write-In Totals", "Not Assigned",
         "Overvotes", "Undervotes", "Contest Totals", "Ballots Cast",
         "Statistics", "Precinct Summary")


def _i(s):
    return int(s.replace(",", ""))


def _classify(title):
    for rx, office, tmpl in _OFFICE_RULES:
        m = rx.match(title)
        if m:
            return office, (tmpl if tmpl is not None else m.group(1))
    return None


def _precinct(lines):
    for i, l in enumerate(lines):
        if "November 5, 2024" in l:
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    return lines[j].strip()
            break
    return lines[3].strip() if len(lines) > 3 else ""


def _parse(cfg: CountyConfig) -> ParseResult:
    import natural_pdf as npdf
    pdf = npdf.PDF(str(cfg.resolve_source()))
    out, prec_order, seen, od_seen = [], [], set(), []

    for page in pdf.pages:
        lines = (page.extract_text() or "").splitlines()
        precinct = _precinct(lines)
        office = district = None
        past_cand_totals = False
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("Precinct Summary"):
                break
            cls = _classify(s)
            if cls is not None:
                office, district = cls
                if (office, district) not in od_seen:
                    od_seen.append((office, district))
                past_cand_totals = False
                continue
            if office is None:
                continue
            if s == _TOTALS_BY_CAND:
                past_cand_totals = True
                continue
            if any(s.startswith(p) for p in _SKIP) and not s.startswith("Not Assigned"):
                continue
            wm = _WRITEIN_ROW.match(s)
            if wm:
                v = _i(wm.group("votes"))
                if v > 0:
                    if precinct not in seen:
                        seen.add(precinct)
                        prec_order.append(precinct)
                    out.append((precinct, office, district, "",
                                wm.group("name").strip(), v))
                continue
            if not past_cand_totals:
                pm = _PARTY_ROW.match(s)
                if pm:
                    v = _i(pm.group("votes"))
                    if v > 0:
                        if precinct not in seen:
                            seen.add(precinct)
                            prec_order.append(precinct)
                        out.append((precinct, office, district,
                                    _PARTY_MAP[pm.group("party")],
                                    pm.group("name").strip(), v))
                    continue

    return ParseResult(rows=out, prec_order=prec_order, od_seen=od_seen or _ORDER)


CONFIG = CountyConfig(
    county="Albany",
    slug="albany",
    engine="text_report",
    source_name="Albany.pdf",
    office_order=_ORDER,
    cand={},
    anchors={},
    writeins="named",
    sort_output=False,
    parse=_parse,
)
