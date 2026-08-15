from ._common import pdf_stlaw_config

# St. Lawrence's PE26 PDF uses rotated candidate-column headers whose text layer
# is unusable (single vertical chars), so the reader consumes the PaddleOCR
# markdown cache (run ``python convert_pdfs_paddleocr.py`` on the PDF first).
# Each page is one contest: a table with the office/party/"Vote for N" title in
# leading colspan rows, precincts (Town + ED) as rows, candidates as columns,
# TOTAL TURNOUT / VOTER REGISTRATION / % TURNOUT / WRITE IN / TOTAL VOTES CAST
# columns.  Over/under are not broken out -- the gap is emitted as Under Votes.
# St. Lawrence County is wholly within NY-21, so the "Representative in
# Congress" contest is forced to district 21 (OCR drops the "21" on some pages).
CONFIG = pdf_stlaw_config(
    county="St. Lawrence",
    slug="st_lawrence",
    source_name="St. Lawrence NY 2026 Primary PE26 Official Results_0.pdf",
    office_map={"Representative in Congress": ("U.S. House", "21")},
)