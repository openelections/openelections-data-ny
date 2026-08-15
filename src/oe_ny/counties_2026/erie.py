from ._common import canvass_config

CONFIG = canvass_config(
    county="Erie",
    slug="erie",
    # resolve_source points at the Democratic workbook; the reader globs both
    # Dem + Rep canvass books from the same source directory.
    source_name="Erie NY 2026 Primary Democratic Canvass Book1.xlsx",
    canvass_glob="Erie NY 2026 Primary *Canvass Book*.xlsx",
)