"""Tabular / wide-SOVC engine (G1).

Consumes sources with one header row and one row per precinct, where each
candidate is a column whose header encodes the candidate name and party.  Covers
per-sheet-per-office XLSX SOVCs (Franklin, Greene, ...), and — via the same
column classifier — HTML tables and CSV blocks.

Header cell styles (``engine_opts['header_style']``):
    name_newline_party   "Kamala D. Harris\\nDEM"      (party = last line)
    name_paren_party     "Kamala D. Harris (DEM)"
    name_dash_party      "Kamala D. Harris - WOR"
    trailing_party_token "Paul D. Tonko DEM"           (party = last token)

Control columns are matched by ``engine_opts`` prefix sets: ``writein_prefixes``,
``over_prefixes``, ``under_prefixes``, ``tv_labels``, and ``ed_label`` (the col0
value marking the header row).  A header cell that is a bare name (no encoded
party) becomes a write-in column when ``bare_name_role == 'writein'`` (named
write-in columns), else skipped.

Office is taken per sheet from ``engine_opts['sheets']`` = list of
(sheet_name, office, district).

``tv_mode``: 'sum_all' requires Total Votes == cand+wi+under+over;
'either' also accepts cand+wi (sources with an inconsistent TV definition).
"""
from __future__ import annotations

import re

from ..common import party_code, strip_vp, to_int
from ..model import CountyConfig, ParseResult
from .base import Accumulator


def _hdr_name_party(cell, style):
    """Return (name, party_code) or (name, None) or (None, None) for a header."""
    if cell is None:
        return (None, None)
    s = str(cell)
    if style == "name_newline_party":
        if "\n" not in s:
            return (s.strip(), None)
        parts = s.split("\n")
        return ("\n".join(parts[:-1]).strip(), party_code(parts[-1].strip()))
    if style == "name_paren_party":
        m = re.search(r"\(([^)]+)\)\s*$", s.strip())
        if m:
            return (s.strip()[:m.start()].strip(), party_code(m.group(1)))
        return (s.strip(), None)
    if style == "name_dash_party":
        if " - " in s:
            name, _, code = s.rpartition(" - ")
            return (name.strip(), party_code(code.strip()))
        return (s.strip(), None)
    if style == "trailing_party_token":
        toks = s.strip().split()
        if len(toks) >= 2 and party_code(toks[-1]):
            return (" ".join(toks[:-1]).strip(), party_code(toks[-1]))
        return (s.strip(), None)
    raise ValueError(f"unknown header_style: {style!r}")


def _classify(cell, opts, style):
    low = str(cell or "").strip().lower()
    if not low:
        return ("skip", None)
    if low == opts.get("ed_label", "ed").lower():
        return ("ed", None)
    for lab in opts.get("tv_labels", ("total votes",)):
        if low == lab.lower():
            return ("tv", None)
    for pre in opts.get("over_prefixes", ()):
        if low.startswith(pre.lower()):
            return ("over", None)
    for pre in opts.get("under_prefixes", ()):
        if low.startswith(pre.lower()):
            return ("under", None)
    for pre in opts.get("writein_prefixes", ()):
        if low.startswith(pre.lower()):
            return ("writein", None)
    name, code = _hdr_name_party(cell, style)
    if code is not None:
        return ("cand", (name, code))
    # bare name: named write-in column, or a skip header
    skip_pre = tuple(p.lower() for p in opts.get("skip_prefixes", ()))
    if opts.get("bare_name_role") == "writein" and name and not low.startswith(skip_pre):
        return ("writein", None)
    return ("skip", None)


def parse(cfg: CountyConfig) -> ParseResult:
    opts = cfg.engine_opts
    style = opts.get("header_style", "name_newline_party")
    import openpyxl
    wb = openpyxl.load_workbook(cfg.resolve_source(), data_only=True)
    acc = Accumulator(cfg)

    for sheet_name, office, district in opts["sheets"]:
        rows = [list(r) for r in wb[sheet_name].iter_rows(values_only=True)]
        hdr_idx = _find_header(rows, opts)
        if hdr_idx is None:
            continue
        acc.see_od((office, district))
        hdr = rows[hdr_idx]
        cand_cols, wi_cols = [], []
        over_idx = under_idx = tv_idx = None
        for j, cell in enumerate(hdr):
            kind, extra = _classify(cell, opts, style)
            if kind == "cand":
                cand_cols.append((j, extra[0], extra[1]))
            elif kind == "writein":
                wi_cols.append(j)
            elif kind == "over":
                over_idx = j
            elif kind == "under":
                under_idx = j
            elif kind == "tv":
                tv_idx = j

        for r in rows[hdr_idx + 1:]:
            c0 = r[0] if r else None
            if c0 is None:
                continue
            label = re.sub(r"\s+", " ", str(c0)).strip()
            if not label:
                continue
            if label.lower() in opts.get("total_labels", ("total", "totals")):
                for j, name, party in cand_cols:
                    acc.set_col_total(office, district, party,
                                      acc.col_total.get((office, district, party), 0)
                                      + to_int(_cell(r, j)))
                acc.set_wi_total(office, district,
                                 sum(to_int(_cell(r, j)) for j in wi_cols))
                break
            # a precinct row has a nonzero candidate cell (numbers may be
            # string-formatted) or any native-numeric data cell (all-zero rows).
            has_cand = any(to_int(_cell(r, j)) for j, _, _ in cand_cols)
            has_native = any(isinstance(_cell(r, j), (int, float))
                             for j in range(1, len(r)))
            if not (has_cand or has_native):
                continue
            prec = acc.precinct(label)
            for j, name, party in cand_cols:
                v = to_int(_cell(r, j))
                src = strip_vp(name) if office == "President" else name
                acc.candidate(prec, office, district, party, v, src_name=src)
            wv = sum(to_int(_cell(r, j)) for j in wi_cols)
            acc.writein(prec, office, district, wv)
            if over_idx is not None:
                acc.over(prec, office, district, to_int(_cell(r, over_idx)))
            if under_idx is not None:
                acc.under(prec, office, district, to_int(_cell(r, under_idx)))
            if tv_idx is not None and opts.get("tv_mode", "sum_all") == "sum_all":
                acc.total(prec, office, district, to_int(_cell(r, tv_idx)))
            # tv_mode 'either' -> skip the per-precinct total check (source's TV
            # column is defined inconsistently across contests)

    return acc.result()


def _find_header(rows, opts):
    marker = opts.get("ed_label", "ED")
    for i, r in enumerate(rows):
        if r and r[0] is not None and str(r[0]).strip() == marker:
            return i
    return None


def _cell(row, i):
    return row[i] if i is not None and i < len(row) else None
