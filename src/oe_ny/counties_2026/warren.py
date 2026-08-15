from ._common import pdf_table_config

# Warren's "atomiclevelresults" PE26 PDF: each contest page has a precinct-row
# table with a 'Ballots' column (Ballots Cast), candidate columns (no party in
# the cells), and Write-ins/Blanks(=Under)/Voids(=Over)/Total columns.  The
# office is on its own text line above the table ("New York State Comptroller
# (Democratic Nominee)") with "Vote for N" on the next line; the contest party
# comes from the "(Democratic/Republican Nominee)" parenthetical.  Contest
# header repeats on each page of a multi-page contest (no page-spanning
# continuation), and some pages are title-only with no table.
CONFIG = pdf_table_config(
    county="Warren",
    slug="warren",
    source_name="Warren NY 2026 Primary PE 26 atomiclevelresults.pdf",
    office_source="text_above",
    counting_group_all_only=False,
)