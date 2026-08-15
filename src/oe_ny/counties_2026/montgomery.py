from ._common import html_wide_config

# Montgomery's HTML titles use "State Assembly" / "United States Representative
# to Congress" phrasings the canonicalizer doesn't match (it expects "Member of
# Assembly" / "Representative in Congress"), so map them explicitly.
_OFFICE_MAP = {
    "United States Representative to Congress 21st District": ("U.S. House", "21"),
    "State Assembly 118th District": ("State Assembly", "118"),
}

CONFIG = html_wide_config(
    county="Montgomery",
    slug="montgomery",
    source_name="Montgomery NY 2026 Primary 202606Primary.html",
    office_map=_OFFICE_MAP,
)