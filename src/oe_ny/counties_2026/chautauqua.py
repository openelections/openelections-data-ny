"""Chautauqua County 2026 primary (one-sheet-per-contest wide XLSX).

Source: ``2026PrimaryElection_Results.xlsx`` -- one sheet per contest with
candidates as columns (row 0 = office title + candidate names + ``Scatterings``
/ ``Over Votes`` / ``Under Votes``; row 1 = party codes; row 2+ = precinct
rows; trailing ``TOTALS`` row skipped).  The ``wide_per_sheet`` reader
synthesizes long-format rows from this layout.  No summary sheet, so
verification is per-precinct arithmetic only (advisory).
"""
from ._common import wide_per_sheet_config

CONFIG = wide_per_sheet_config(
    county="Chautauqua",
    slug="chautauqua",
    source_name="Chautauqua NY 2026 Primary 2026PrimaryElection_Results.xlsx",
)