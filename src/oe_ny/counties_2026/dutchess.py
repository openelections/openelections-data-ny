from ._common import pdf_dutchess_config

# Dutchess County 2026 primary comes from the BoE 'Detailed Results by Contest'
# PDF (text layer): six contests, all Democratic, all vote-for-1.  The rotated
# candidate headers carry the raw office title verbatim, so office_map forces
# the four statewide/legislative titles to (office, district) -- the shared
# parse_office_title does not recognize 'Member of Congress' (it returns None
# for that prefix), and the district must be recovered for the others.  Local
# offices (Rhinebeck Town Supervisor, Amenia Town Board) have no entry and pass
# through as the full cleaned title.
_OFFICE_MAP = {
    "Comptroller": ("Comptroller", ""),
    "Member of Congress District 17": ("U.S. House", "17"),
    "State Senator District 39": ("State Senate", "39"),
    "Member of Assembly District 106": ("State Assembly", "106"),
}

CONFIG = pdf_dutchess_config(
    county="Dutchess",
    slug="dutchess",
    source_name="Dutchess Detailed-Results-by-Contest-Table-7-10.pdf",
    office_map=_OFFICE_MAP,
)