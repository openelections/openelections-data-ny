from ._common import pdf_table_config

# "State Senator" has no district in its office line (the district lives in the
# page's "District: 51st Senatorial District" line), so map it explicitly.  The
# other offices canonicalize from the office line: Comptroller -> Comptroller,
# "United State Representative in Congress District 19" -> ("U.S. House","19"),
# and "Town Supervisor" passes through as a local office.
_OFFICE_MAP = {
    "State Senator": ("State Senate", "51"),
}

CONFIG = pdf_table_config(
    county="Chenango",
    slug="chenango",
    source_name="Chenango NY 2026 Primary Official Primary Results by District.pdf",
    office_source="office_line",
    counting_group_all_only=True,
    office_map=_OFFICE_MAP,
)