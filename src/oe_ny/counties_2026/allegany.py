from ._common import pdf_table_config

# Allegany's district PE26 PDF puts the office in each table's col-0 header
# ("State Comptroller", "Representative in Congress District 23", "County
# Judge", town "Justice" / "Committee Member TFV") with the party embedded in
# the candidate header cells.  Town-primary tables put the party on the row
# below the header; the reader merges that row in.  No counting-group repeats,
# so no All-only filter.  Offices canonicalize from the header: Comptroller,
# "Representative in Congress District 23" -> ("U.S. House","23"); county/town
# offices (County Judge, Justice, Committee Member TFV) pass through unchanged.

CONFIG = pdf_table_config(
    county="Allegany",
    slug="allegany",
    source_name="Allegany NY 2026 Primary PE26-Official-Results-District.pdf",
    office_source="col0",
    counting_group_all_only=False,
    town_precinct_fallback=True,
)