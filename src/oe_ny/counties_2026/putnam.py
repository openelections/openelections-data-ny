"""Putnam County 2026 primary (Democracy Suite long XLSX, all contests).

Office titles include the district (e.g. "Representative in Congress, 17th
Congressional District (Democratic)"), so the parser extracts it.
"""
from ._common import long_config

CONFIG = long_config(
    county="Putnam",
    slug="putnam",
    source_name="Putnam NY 2026 Primary All Results Excel.xlsx",
)