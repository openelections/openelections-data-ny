"""Livingston County 2026 primary (Democracy Suite long XLSX, all contests).

Source: ``All Results Excel.xlsx``.  Office titles carry the party but omit the
district, so federal/state districts are blank here pending an office_map
override.
"""
from ._common import long_config

CONFIG = long_config(
    county="Livingston",
    slug="livingston",
    source_name="Livingston NY 2026 Primary All Results Excel.xlsx",
)