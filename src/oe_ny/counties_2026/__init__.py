"""Registry of 2026 primary per-county configs: slug -> CountyConfig.

Mirrors ``counties_2024``.  Each county lives in its own module exposing a
module-level ``CONFIG``; new counties are added to ``_MODULES`` below.  All
configs here set ``date="20260623"`` and ``election="primary"`` so sources
resolve under ``<sources>/2026/primary/`` and output goes to
``2026/counties/20260623__ny__primary__<slug>__precinct.csv``.
"""
from __future__ import annotations

import importlib

from ..model import CountyConfig

# slug -> submodule name (module must define CONFIG: CountyConfig)
_MODULES = [
    # primary engine (Democracy Suite XLSX, all contests)
    "livingston", "madison", "putnam", "oneida", "rensselaer", "westchester",
    "cattaraugus", "columbia", "sullivan",
    "chautauqua",  # one-sheet-per-contest wide XLSX
    "otsego",  # one-sheet-per-precinct long XLSX (PE26 report)
    "erie",  # Dem/Rep canvass books, candidates-as-columns
    "monroe",  # zip of one-XLSX-per-contest
    "montgomery",  # one-table-per-contest HTML
    "oswego",  # block-wide BoE .xls (party-labeled, multi-vote va_map)
    "saratoga",  # block-wide BoE .xls (unlabeled, contest_map from PDF)
    "orleans",  # image-only PE26 PDF via PaddleOCR markdown (pdf reader)
    "chenango",  # text-layer PE26 PDF via pdfplumber tables (pdf table reader)
    "allegany",  # text-layer PE26 district PDF, office in col-0 header
    "fulton",  # text-layer PE26 PDF, office in line above table, page-spanning
    "warren",  # text-layer atomiclevelresults PDF, Ballots col, office line above
    "washington",  # text-layer per-precinct PE26 PDF (Family C blocks reader)
    "tioga",  # text-layer transposed PE26 PDF (Family B, rotated precinct cols)
    "st_lawrence",  # PaddleOCR markdown, rotated candidate headers (Family A)
    "essex",  # two-layout canvass PDF (rotated headers + transposed town offices)
    "orange",  # per-contest PE26 PDF set (7 files, rotated candidate columns)
    "niagara",  # NY ENR VIC API JSON (cached), 10 contests
    "cortland",  # canvass PDF, rotated four-block candidate headers
    "chemung",  # enhancedvoting.com public-results API JSON (cached)
    "dutchess",  # text-layer 'Detailed Results by Contest' PDF (rotated 60deg headers)
    # NYC boroughs (nyc engine: EDLevel.csv per contest)
    "new_york",  # New York County (Manhattan)
    "kings",  # Kings County (Brooklyn)
    "queens",  # Queens County
    "bronx",  # Bronx County
    "richmond",  # Richmond County (Staten Island)
]


def _load() -> dict[str, CountyConfig]:
    out: dict[str, CountyConfig] = {}
    for name in _MODULES:
        try:
            mod = importlib.import_module(f".{name}", __name__)
        except ModuleNotFoundError:
            continue
        cfg = getattr(mod, "CONFIG", None)
        if cfg is not None:
            out[cfg.slug] = cfg
    return out


def all_configs() -> dict[str, CountyConfig]:
    return _load()


def get(slug: str) -> CountyConfig:
    cfgs = _load()
    if slug not in cfgs:
        raise KeyError(f"no config for county slug {slug!r}")
    return cfgs[slug]