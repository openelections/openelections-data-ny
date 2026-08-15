"""Cattaraugus County 2026 primary (Democracy Suite wide XLSX, all contests).

Source: ``Precinct-District Results by Contest Table Excel.xlsx`` -- single
``Results`` sheet, no county summary, so verification is per-precinct
arithmetic only (advisory).  Contest titles embed the reporting district
(``"Comptroller for CD 23 (DEM), Cattaraugus County"``).
"""
from ._common import wide_config

CONFIG = wide_config(
    county="Cattaraugus",
    slug="cattaraugus",
    source_name="Cattaraugus NY 2026 Primary Precinct-District Results by Contest Table Excel.xlsx",
)