"""NYC Board of Elections ``EDLevel.csv`` reader for the oe_ny framework.

The NYC BoE publishes one ``EDLevel.csv`` per contest (one party + office +
district).  The 2026 file format prepends the 11 column-header names to every
row, so each line is 22 fields = 11 headers + 11 values (there is no separate
header row).  Only ``IN-PLAY`` rows are emitted -- rows whose EDAD Status is
e.g. ``"COMBINED INTO 027/85"`` are precincts merged into another ED whose
votes roll into the receiving precinct, so they are skipped.

A config selects its files via ``engine_opts["borough_prefix"]`` (e.g.
``"Bronx NY"``) and reads every ``<prefix>*EDLevel.csv`` under the source
directory.  Only the **borough-prefixed** files are read; the
``NYC NY ... Crossover/Citywide ...`` files duplicate the borough files
precinct-for-precinct and are excluded to avoid double-counting.  Rows are
kept only when their County field matches ``cfg.county`` (a no-op in practice
-- a borough file's rows all carry that borough -- but defensive against any
cross-borough stray).

The engine returns rows already sorted by (precinct, office, district, party,
candidate), the order the standalone ``nyc_parser.py`` writes, so configs set
``sort_output=False`` and the shared writer emits them verbatim.  Tally
categories (Public Counter, Absentee / Military, Federal, Affidavit, Scattered,
Manually Counted Emergency, ...) are emitted as ordinary candidate rows --
Public Counter is the precinct's ballots cast -- matching the repo's NYC
convention (see the 2022 NYC general files).  No Ballots Cast/Registered Voters
pseudo-offices are synthesized (the source carries no over/under breakdown).
"""
from __future__ import annotations

import csv
import glob
import os
import re
from collections import defaultdict

from ..model import DEFAULT_SOURCE_DIR, CountyConfig, ParseResult

# Source office title -> canonical OpenElections office name (matches the
# primary engine's _canonical_office output for the statewide/federal offices).
OFFICE_MAP = {
    "United States Senator": "U.S. Senate",
    "Representative in Congress": "U.S. House",
    "State Senator": "State Senate",
    "Member of the Assembly": "State Assembly",
    "State Comptroller": "Comptroller",
    "President/Vice President": "President",
}

# Statewide/citywide offices with no real district -- the source's district key
# is a marker like "NYC", not a district number, so it is blanked.
DISTRICTLESS_OFFICES = {"Comptroller", "President", "U.S. Senate"}

# NYC party name -> OpenElections code (matches oe_ny common.party_code).
PARTY_MAP = {
    "Democratic": "DEM", "Republican": "REP", "Conservative": "CON",
    "Working Families": "WOR", "Independence": "IND", "Green": "GRN",
    "Libertarian": "LAR", "Reform": "REF", "SAM": "SAM",
    "Rent Is Too Damn High": "RIT", "Independent": "IND",
}

# Value-field indices (after dropping the 11 prepended header names).
(AD, ED, COUNTY, STATUS, EVENT, PARTY, OFFICE,
 DISTRICT, VOTEFOR, UNIT, TALLY) = range(11)

_CAND_PAREN = re.compile(r"^(.*) \((.*)\)\s*$")


def _norm_district(office: str, d: str) -> str:
    """Strip leading zeros for numeric districts; blank the marker for
    districtless (statewide/citywide) offices; otherwise keep the raw code
    (e.g. District Leader '35B')."""
    d = (d or "").strip()
    if office in DISTRICTLESS_OFFICES:
        return ""
    if d.isdigit():
        return str(int(d))
    return d


def _party_code(party: str, unit: str) -> str:
    """Party column -> code, falling back to a trailing '(Party)' on the unit
    name when the column is blank."""
    p = (party or "").strip()
    if p in PARTY_MAP:
        return PARTY_MAP[p]
    m = _CAND_PAREN.match(unit or "")
    if m and m.group(2) in PARTY_MAP:
        return PARTY_MAP[m.group(2)]
    return p


def _candidate(unit: str) -> str:
    """Unit Name -> candidate, stripping a trailing '(Party)' parenthetical."""
    name = (unit or "").strip()
    m = _CAND_PAREN.match(name)
    if m:
        return m.group(1).strip()
    return name


def parse_file(path):
    """Yield ``(precinct, office, district, party, candidate, votes)`` for each
    IN-PLAY row in one EDLevel.csv file (handles the 22-field 2026 format and
    the legacy 11-field format)."""
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            # 2026 format: 22 fields = 11 header names + 11 values.  Older
            # files: a single 11-field header row, then 11-field rows.
            if len(row) == 22 and row[0].strip() == "AD":
                row = row[11:]
            if len(row) != 11:
                continue
            if row[0].strip() == "AD":  # stray header row (old format)
                continue
            if row[STATUS].strip() != "IN-PLAY":
                continue
            county = row[COUNTY].strip()
            office = OFFICE_MAP.get(row[OFFICE].strip(), row[OFFICE].strip())
            prec = "%s/%s" % (row[ED].strip(), row[AD].strip())
            district = _norm_district(office, row[DISTRICT])
            party = _party_code(row[PARTY], row[UNIT])
            candidate = _candidate(row[UNIT])
            tally = row[TALLY].strip().replace(",", "")
            votes = int(tally) if tally.isdigit() else 0
            yield (county, prec, office, district, party, candidate, votes)


def parse(cfg: CountyConfig) -> ParseResult:
    """Read every ``<borough_prefix>*EDLevel.csv`` under the source directory,
    keep rows whose County matches ``cfg.county``, and return them sorted as
    the standalone nyc_parser.py writes them."""
    prefix = cfg.engine_opts["borough_prefix"]
    # An explicit ``source_dir`` engine opt (set by nyc_parser.py and tests)
    # overrides the default ``<DEFAULT_SOURCE_DIR>/<date_dir>`` location.
    src_dir = cfg.engine_opts.get("source_dir") or (DEFAULT_SOURCE_DIR / cfg.date_dir())
    rows = []
    od_seen = []
    seen_od = set()
    for path in sorted(glob.glob(os.path.join(str(src_dir), prefix + "*EDLevel.csv"))):
        for county, prec, office, district, party, candidate, votes in parse_file(path):
            if county != cfg.county:
                continue
            rows.append((prec, office, district, party, candidate, votes))
            od = (office, district)
            if od not in seen_od:
                seen_od.add(od)
                od_seen.append(od)
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
    return ParseResult(rows=rows, prec_order=[], od_seen=od_seen, notes=[])