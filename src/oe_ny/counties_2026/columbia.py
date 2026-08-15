"""Columbia County 2026 primary (Democracy Suite wide XLSX, all contests).

Source: ``Precinct-District Results by Contest Table Excel.xlsx``.  Contest
titles here omit the party (it lives in the Party column) and use compact
district forms ("Member of Assembly for 106th").
"""
from ._common import wide_config

CONFIG = wide_config(
    county="Columbia",
    slug="columbia",
    source_name="Columbia NY 2026 Primary Precinct-District Results by Contest Table Excel.xlsx",
)