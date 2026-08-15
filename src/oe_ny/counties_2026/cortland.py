from ._common import pdf_cortland_config

# Cortland's canvass PDF prints each contest as "<office> (<party>) - Early
# Voting ... Total Votes" with the district folded into the office title.  The
# shared parse_office_title would mis-map "Rep. in Congress - 19th CD", so
# office_map forces it to ("U.S. House", "19").  "State Comptroller" -> a
# clean ("Comptroller", "") and "County Committee" passes through (DEM and REP
# primaries distinguished by party; the vote-for-2 contests carry va=2 in the
# reader so the engine drops them from precinct Ballots Cast).
_OFFICE_MAP = {
    "State Comptroller": ("Comptroller", ""),
    "Rep. in Congress - 19th CD": ("U.S. House", "19"),
    "County Committee": ("County Committee", ""),
}

CONFIG = pdf_cortland_config(
    county="Cortland",
    slug="cortland",
    source_name="Cortland PRIMARY ELECTION 2026_202607070912478058.pdf",
    office_map=_OFFICE_MAP,
)