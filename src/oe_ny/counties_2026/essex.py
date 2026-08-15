from ._common import pdf_essex_config

# Essex County is wholly within NY-21, so every "Representative in Congress"
# contest (DEM + REP) is district 21; office_map forces it so the shared title
# parser doesn't need the district number.  Comptroller canonicalizes cleanly
# and the town-scoped local offices (Crown Point Superintendent of Highways,
# Crown Point Town Council Member, Elizabethtown Department of Public Works
# Supervisor, Newcomb Superintendent of Highways, Willsboro Town Clerk/Tax
# Collector) pass through unchanged with the town name preserved.
_OFFICE_MAP = {
    "Representative in Congress": ("U.S. House", "21"),
}

CONFIG = pdf_essex_config(
    county="Essex",
    slug="essex",
    source_name="Essex NY 2026 Primary Primary20260623.pdf",
    office_map=_OFFICE_MAP,
)