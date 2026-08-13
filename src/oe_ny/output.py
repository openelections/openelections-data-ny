"""Sort + emit the standard 7-column OpenElections precinct CSV.

Ported once from the identical sort/emit tail every per-county script carried.
"""
from __future__ import annotations

import csv
import io

from .common import party_rank
from .model import CountyConfig, ParseResult, Row

HEADER = ["county", "precinct", "office", "district", "party", "candidate", "votes"]


def sort_rows(cfg: CountyConfig, rows: list[Row], prec_order: list[str]) -> list[Row]:
    prank = party_rank(cfg.extra_parties)
    orank = {od: i for i, od in enumerate(cfg.office_order)}

    def key(r: Row):
        prec, office, district, party, cand, _ = r
        return (
            prec_order.index(prec) if prec in prec_order else 999,
            orank.get((office, district), 99),
            prank.get(party, 9),
            cand,
        )

    return sorted(rows, key=key)


def rows_to_csv_text(cfg: CountyConfig, rows: list[Row]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    for prec, office, district, party, cand, votes in rows:
        w.writerow([cfg.county, prec, office, district, party, cand, votes])
    return buf.getvalue()


def write_csv(cfg: CountyConfig, res: ParseResult) -> str:
    """Sort, write the CSV to cfg.out_path(), and return the CSV text."""
    ordered = sort_rows(cfg, res.rows, res.prec_order)
    text = rows_to_csv_text(cfg, ordered)
    out = cfg.out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, newline="")
    return text


def report(cfg: CountyConfig, res: ParseResult, out_path: str) -> None:
    precincts = {r[0] for r in res.rows}
    print(f"Wrote {len(res.rows)} rows, {len(precincts)} precincts, "
          f"{len(res.od_seen)} office-districts -> {out_path}")
    for od in cfg.office_order:
        office, district = od
        parts = []
        for p in ("DEM", "REP", "CON", "WOR", "LAR"):
            if (office, district, p) in cfg.cand:
                parts.append(f"{p}={res.psum.get((office, district, p), 0)}")
        parts.append(f"Write-in={res.wisum.get(od, 0)}")
        print(f"  {office} {district}: {', '.join(parts)}")
    for n in res.notes:
        print(f"  note: {n}")
