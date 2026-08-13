"""oe_ny: generic New York OpenElections precinct parsers.

A small set of format-family engines driven by per-county Python configs,
replacing the ~36 standalone src/2024/<county>_2024_parse.py scripts.  See
README.md for the family taxonomy and how to add a county.
"""
from __future__ import annotations

from .model import CountyConfig, ParseResult, Row  # noqa: F401
