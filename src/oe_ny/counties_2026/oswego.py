from ._common import block_wide_config

# The .xls labels county-legislature and state-committee contests with
# abbreviated text and no district, so map them to canonical office + district
# (the assembly contest confirms Oswego is AD 120, which the state-committee
# contest shares).  Other label text canonicalizes directly: "Comptroller",
# "Representative in Congress 24th" -> U.S. House/24, "Member of Assembly 120th"
# -> State Assembly/120.  Judicial-delegate contests have no canonical office, so
# their cleaned titles pass through as local offices.
_OFFICE_MAP = {
    "Oswego County Leg District 17": ("County Legislator", "17"),
    "Oswego County Leg District 9": ("County Legislator", "9"),
    "State Committee": ("State Committee", "120"),
}

# Votes-allowed for the multi-vote contests (the .xls has no votes-allowed
# column).  These are excluded from precinct Ballots Cast so their N*ballots
# totals do not inflate turnout; candidate vote rows are still emitted.
_VA_MAP = {
    "State Committee": 2,
    "5th Judicial Delegates": 7,
    "5th Judicial Alternates": 7,
}

CONFIG = block_wide_config(
    county="Oswego",
    slug="oswego",
    source_name="Oswego NY 2026 Primary Official Results PE26.xls",
    office_map=_OFFICE_MAP,
    va_map=_VA_MAP,
)