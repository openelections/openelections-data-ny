"""Engine registry: engine name -> parse(cfg) -> ParseResult."""
from __future__ import annotations

from ..model import CountyConfig, ParseResult


def get_engine(name: str):
    if name == "tidy":
        from . import tidy
        return tidy.parse
    if name == "tabular":
        from . import tabular
        return tabular.parse
    if name == "election_book":
        from . import election_book
        return election_book.parse
    if name == "sovc_table":
        from . import sovc_table
        return sovc_table.parse
    if name == "text_report":
        from . import text_report
        return text_report.parse
    if name == "primary":
        from . import primary
        return primary.parse
    if name == "nyc":
        from . import nyc
        return nyc.parse
    raise ValueError(f"unknown engine: {name!r}")


def run(cfg: CountyConfig) -> ParseResult:
    """Parse a county: a config-level parse override wins over the named engine."""
    if cfg.parse is not None:
        return cfg.parse(cfg)
    return get_engine(cfg.engine)(cfg)
