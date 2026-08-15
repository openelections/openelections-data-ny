from ._common import pdf_config

# "Representative to Congress 24th District" is not recognized by the shared
# parse_office_title (it matches "representative in congress" / "congressional
# district", not "to congress"), so map it explicitly to the canonical office.
# The other Orleans offices canonicalize cleanly: "Comptroller" -> Comptroller,
# and the town-scoped locals ("Clarendon Supervisor", "Shelby Member of County
# Committee") pass through unchanged with the town name preserved.
_OFFICE_MAP = {
    "Representative to Congress 24th District": ("U.S. House", "24"),
}

CONFIG = pdf_config(
    county="Orleans",
    slug="orleans",
    source_name="Orleans NY 2026 Primary PE26 OFFICIAL RESULTS.pdf",
    office_map=_OFFICE_MAP,
)