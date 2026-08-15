from ._common import pdf_table_config

# Fulton's per-precinct PE26 PDF puts the office in a text line just above each
# table ("Comptroller (Vote for 1)", "Representative in Congress 21st REP
# (Vote for 1)", "Member of Assembly 118th (Vote for 1)", town offices).  Tables
# spill across page breaks; the reader carries the office/colspec forward.
# Candidate header cells carry a trailing ballot-line digit ("DEM 1", "REP 2")
# that is NOT votes_allowed, so votes_allowed comes from the office line's
# "(Vote for N)".  The DEM U.S. House page misspells the office "Represenative
# in Congress 21st", which the shared parser does not recognize, so map it.
_OFFICE_MAP = {
    "Represenative in Congress 21st": ("U.S. House", "21"),
}

CONFIG = pdf_table_config(
    county="Fulton",
    slug="fulton",
    source_name="Fulton NY 2026 Primary Official Results per Precinct.pdf",
    office_source="text_above",
    counting_group_all_only=False,
    office_map=_OFFICE_MAP,
)