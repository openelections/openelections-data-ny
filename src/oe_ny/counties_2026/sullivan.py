"""Sullivan County 2026 primary (Democracy Suite wide XLSX, all contests).

Source: ``Precinct-District Results by Contest Table Excel.xlsx``.  Contest
titles use a dash-separated party suffix ("Comptroller - Democratic",
"Supervisor - Town of Cochecton - Republican").
"""
from ._common import wide_config

CONFIG = wide_config(
    county="Sullivan",
    slug="sullivan",
    source_name="Sullivan NY 2026 Primary Precinct-District Results by Contest Table Excel.xlsx",
)