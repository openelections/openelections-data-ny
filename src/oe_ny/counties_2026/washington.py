from ._common import pdf_blocks_config

# Washington's per-precinct PE26 PDF: 200 pages, each page one precinct's
# contest block.  Every precinct has four pages -- Democratic machine,
# Republican machine, Democratic absentee ("ABS"), Republican absentee -- which
# the reader sums (it strips trailing "ABS" so absentee votes land under the
# parent precinct).  Offices are only Comptroller (DEM), Representative In
# Congress 21 (DEM + REP), and Easton Highway Superintendent (REP).  Each page
# carries "N of M registered voters" (M=0 on absentee pages), so Registered
# Voters come from the machine pages.  Candidate names span two lines and the
# wanted count is always the final integer (the Total column).
CONFIG = pdf_blocks_config(
    county="Washington",
    slug="washington",
    source_name="Washington NY 2026 Primary PE26-Results-by-District.pdf",
)