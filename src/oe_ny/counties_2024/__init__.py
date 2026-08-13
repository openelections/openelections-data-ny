"""Registry of 2024 general per-county configs: slug -> CountyConfig.

Each county lives in its own module exposing a module-level ``CONFIG``.  New
counties are added to ``_MODULES`` below.
"""
from __future__ import annotations

import importlib

from ..model import CountyConfig

# slug -> submodule name (module must define CONFIG: CountyConfig)
_MODULES = [
    # tidy (G2)
    "clinton", "livingston", "madison", "sullivan", "niagara", "otsego",
    # tabular (G1)
    "franklin", "greene", "hamilton", "saratoga", "rensselaer", "chautauqua",
    "erie", "cayuga", "wayne", "schoharie", "montgomery", "delaware",
    # election_book (G3)
    "broome", "onondaga", "westchester", "warren", "monroe",
    # sovc_table (G4)
    "orange", "st_lawrence", "putnam", "herkimer", "allegany", "chenango",
    "cortland", "cattaraugus",
    # text_report (G5)
    "albany", "washington", "schenectady", "schuyler",
]


def _load() -> dict[str, CountyConfig]:
    out: dict[str, CountyConfig] = {}
    for name in _MODULES:
        try:
            mod = importlib.import_module(f".{name}", __name__)
        except ModuleNotFoundError:
            continue  # not migrated yet
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
