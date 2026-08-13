"""Data model shared by the generic NY parsers.

``CountyConfig`` is the per-county description an engine consumes.  ``ParseResult``
is what every engine returns: the final output rows plus enough accounting for
the shared three-way verification in :mod:`oe_ny.verify`.
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# A single output row: (precinct, office, district, party, candidate, votes).
Row = tuple[str, str, str, str, str, int]

# Key into cand / psum / name_seen maps.
ODP = tuple[str, str, str]   # (office, district, party)
OD = tuple[str, str]         # (office, district)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = Path(
    os.environ.get(
        "OE_NY_SOURCE_DIR",
        "/Users/dwillis/code/openelections-sources-ny",
    )
)


@dataclass
class CountyConfig:
    """Everything an engine needs to parse one county for one election."""

    county: str                      # display name, e.g. "Franklin"
    slug: str                        # output slug, e.g. "st_lawrence"
    engine: str                      # engine registry key
    office_order: list[OD]           # canonical (office, district) sort/report order
    cand: dict[ODP, str]             # (office,district,party) -> candidate name
    anchors: dict[tuple, int] = field(default_factory=dict)  # ..+("_WI",) allowed

    # source file: explicit path, or resolved from source_name under the
    # sources repo (env override via <SLUG>_SRC or per-engine convention).
    source_name: str | None = None   # e.g. "Franklin.xlsx"
    source: Path | None = None

    # semantics
    fusion: str = "split"            # "split" | "primary-only"
    counting_groups: str = "none"    # none|select-all|sum-subrows|band|grand-total-col
    writeins: str = "fold"           # "fold" (one Write-in row) | "named" (keep names)
    precinct_name: object = "verbatim"   # strategy key or Callable[[str], str]
    extra_parties: tuple[str, ...] = ()

    # election identity (for output filename); defaults = 2024 general
    date: str = "20241105"
    state: str = "ny"
    election: str = "general"

    # engine-specific knobs (header style, column maps, per-county quirks)
    engine_opts: dict = field(default_factory=dict)

    # optional per-county parse override (escape hatch); when set the registry
    # calls this instead of the named engine.
    parse: Callable[["CountyConfig"], "ParseResult"] | None = None

    def resolve_source(self) -> Path:
        if self.source is not None:
            return Path(self.source)
        env = os.environ.get(f"{self.slug.upper()}_SRC")
        if env:
            return Path(env)
        if self.source_name:
            return DEFAULT_SOURCE_DIR / self.date_dir() / self.source_name
        raise ValueError(f"{self.slug}: no source configured")

    def date_dir(self) -> str:
        # sources repo layout: <root>/<year>/<election>/<File>
        return f"{self.date[:4]}/{self.election}"

    def out_path(self) -> Path:
        fn = f"{self.date}__{self.state}__{self.election}__{self.slug}__precinct.csv"
        return REPO_ROOT / self.date[:4] / "counties" / fn


@dataclass
class ParseResult:
    """Engine output + accounting for verification."""

    rows: list[Row]                              # final output rows
    prec_order: list[str]                        # precinct names, source order
    od_seen: list[OD] = field(default_factory=list)

    # county-wide sums computed from precinct rows
    psum: dict = field(default_factory=lambda: defaultdict(int))    # ODP -> votes
    wisum: dict = field(default_factory=lambda: defaultdict(int))   # OD -> votes

    # source-embedded TOTAL row (optional; empty if the source has none)
    col_total: dict = field(default_factory=dict)   # ODP -> votes
    wi_total: dict = field(default_factory=dict)     # OD -> votes

    # per-(precinct, office, district) arithmetic (optional)
    ed_cand: dict = field(default_factory=lambda: defaultdict(int))
    ed_wi: dict = field(default_factory=lambda: defaultdict(int))
    ed_over: dict = field(default_factory=lambda: defaultdict(int))
    ed_under: dict = field(default_factory=lambda: defaultdict(int))
    ed_total: dict = field(default_factory=lambda: defaultdict(int))  # Total Votes/Ballots Cast

    # candidate-name cross-check: ODP -> set of source names
    name_seen: dict = field(default_factory=lambda: defaultdict(set))

    # free-form notes an engine wants surfaced in the report
    notes: list[str] = field(default_factory=list)
