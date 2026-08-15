from ._common import json_config

# Niagara County 2026 primary comes from the NY ENR "VIC" API
# (getdistrictresultsbyparty), cached as a local JSON source file.  The API's
# contest names are mapped explicitly to (office, district): the federal/state
# offices canonicalize (Comptroller, U.S. House 23/24, County Legislator 13) and
# the town-scoped offices keep their town in the office name so same-office
# different-party primaries (Lewiston Supervisor REP vs CON) are distinguished by
# party.  Committee Member contests are vote-for-2 (pos=2) so the engine's
# multi-vote exclusion drops them from precinct Ballots Cast.
_OFFICE_MAP = {
    "State Comptroller": ("Comptroller", ""),
    "Representative in Congress District 23": ("U.S. House", "23"),
    "Representative in Congress District 24": ("U.S. House", "24"),
    "13th Legislative District": ("County Legislator", "13"),
    "Supervisor - Lewiston - Rep": ("Lewiston Supervisor", ""),
    "Supervisor - Lewiston - Con": ("Lewiston Supervisor", ""),
    "Supervisor - Wilson": ("Wilson Supervisor", ""),
    "Committee Member - Hartland 1": ("Committee Member - Hartland 1", ""),
    "Committee Member - Hartland 2": ("Committee Member - Hartland 2", ""),
    "Committee Member - Lewiston 8": ("Committee Member - Lewiston 8", ""),
}

CONFIG = json_config(
    county="Niagara",
    slug="niagara",
    source_name="Niagara NY 2026 Primary.json",
    office_map=_OFFICE_MAP,
)