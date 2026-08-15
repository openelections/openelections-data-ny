from ._common import pdf_transposed_config

# Tioga's amended PE26 PDF is transposed: candidates are rows, precincts are
# rotated columns.  Two pages -- the Democratic primary (Comptroller,
# Representative in Congress 23) and the Republican primary (Town Justice for
# Town of Spencer, Representative in Congress 23).  The rotated precinct labels
# extract reversed (e.g. "1 - yellaV kraweN"); the reader groups chars by x and
# reverses them to recover "Newark Valley - 1" precinct names (the 2024 Tioga
# convention).  A separate "manual-recount-summary" PDF exists but the amended
# official results already incorporate that recount ("Results did not change"),
# so only the amended official-results PDF is the source.  No Registered Voters.
CONFIG = pdf_transposed_config(
    county="Tioga",
    slug="tioga",
    source_name="Tioga NY 2026 Primary official-results_pe26_amended-7-9-26.pdf",
)