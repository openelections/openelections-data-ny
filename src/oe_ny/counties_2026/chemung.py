from ._common import enhancedvoting_config

# Chemung County 2026 primary comes from the enhancedvoting.com public-results
# API (https://app.enhancedvoting.com/results/public/chemung-county-ny/elections
# /PE26), cached as a local consolidated JSON source file.  The API's contest
# names carry the district inline; office_map forces them to (office, district)
# so the shared parse_office_title does not mis-map "Representative in Congress -
# District 23" or the four County Legislator districts.  All seven contests are
# vote-for-1, so none are excluded from precinct Ballots Cast.
_OFFICE_MAP = {
    "State Comptroller": ("Comptroller", ""),
    "Representative in Congress - District 23": ("U.S. House", "23"),
    "County Executive": ("County Executive", ""),
    "County Legislator - District 1": ("County Legislator", "1"),
    "County Legislator - District 3": ("County Legislator", "3"),
    "County Legislator - District 5": ("County Legislator", "5"),
    "County Legislator - District 6": ("County Legislator", "6"),
}

CONFIG = enhancedvoting_config(
    county="Chemung",
    slug="chemung",
    source_name="Chemung PE26 enhancedvoting.json",
    office_map=_OFFICE_MAP,
)