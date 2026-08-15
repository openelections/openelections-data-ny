from ._common import zip_wide_config

# State Committee contests are split by gender (separate contests in the same
# AD); keep them distinct while collapsing to the canonical office + district.
_OFFICE_MAP = {
    "Member of State Comm - Female 137th Dist": ("State Committee", "137-Female"),
    "Member of State Comm - Male 137th Dist": ("State Committee", "137-Male"),
}

CONFIG = zip_wide_config(
    county="Monroe",
    slug="monroe",
    source_name="Monroe NY 2026 Primary PE26 Official Results Excel Reports.zip",
    office_map=_OFFICE_MAP,
)