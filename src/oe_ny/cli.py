"""Command-line entry point.

    python -m oe_ny [--year 2024] [--election general] [--check|--write] [slug ...]

Default (no flag) parses each county, writes its CSV, prints the report, and
runs verification (exit 1 on any HARD failure).  ``--check`` is the migration
gate: it parses, verifies, and diffs the produced rows against the committed CSV
WITHOUT overwriting it, reporting byte-identical / row-set-equal / differs.
With no slugs, acts on every registered county.
"""
from __future__ import annotations

import argparse
import sys

from . import counties_2024
from .engines import run
from .output import report, rows_to_csv_text, sort_rows, write_csv
from .verify import verify


def _committed_rows(text: str) -> list[tuple]:
    import csv
    import io
    rows = list(csv.reader(io.StringIO(text)))
    return [tuple(r) for r in rows[1:]] if rows else []


def _check(cfg) -> int:
    res = run(cfg)
    hard = verify(cfg, res)
    ordered = sort_rows(cfg, res.rows, res.prec_order)
    produced = rows_to_csv_text(cfg, ordered)
    out = cfg.out_path()
    status = []
    if hard:
        status.append(f"{len(hard)} HARD verify failures")
    if not out.exists():
        print(f"[{cfg.slug}] NO committed CSV at {out}", file=sys.stderr)
        return 1
    # preserve CRLF: the CSVs are written with csv.writer's \r\n terminator, so
    # read without newline translation to get a faithful byte comparison.
    with open(out, newline="") as fh:
        committed = fh.read()
    if produced == committed:
        verdict = "BYTE-IDENTICAL"
        rc = 0
    else:
        prod_rows = _committed_rows(produced)
        comm_rows = _committed_rows(committed)
        if sorted(prod_rows) == sorted(comm_rows):
            verdict = "ROW-SET-EQUAL (ordering differs)"
            rc = 0
        else:
            only_prod = set(prod_rows) - set(comm_rows)
            only_comm = set(comm_rows) - set(prod_rows)
            verdict = (f"DIFFERS (+{len(only_prod)} / -{len(only_comm)} rows; "
                       f"produced {len(prod_rows)}, committed {len(comm_rows)})")
            rc = 1
            for r in list(only_prod)[:8]:
                print(f"    +{r}", file=sys.stderr)
            for r in list(only_comm)[:8]:
                print(f"    -{r}", file=sys.stderr)
    tag = f" [{'; '.join(status)}]" if status else ""
    stream = sys.stderr if (rc or status) else sys.stdout
    print(f"[{cfg.slug}] {verdict}{tag}", file=stream)
    return rc or (1 if hard else 0)


def _build(cfg) -> int:
    res = run(cfg)
    hard = verify(cfg, res)
    write_csv(cfg, res)
    report(cfg, res, str(cfg.out_path()))
    if hard:
        print(f"=== {len(hard)} HARD VERIFICATION PROBLEMS ===", file=sys.stderr)
        for p in hard[:60]:
            print("  " + p, file=sys.stderr)
        return 1
    print("Verification OK: 0 hard failures.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="oe_ny")
    ap.add_argument("--year", default="2024")
    ap.add_argument("--election", default="general")
    ap.add_argument("--check", action="store_true", help="diff vs committed CSV")
    ap.add_argument("slugs", nargs="*", help="county slugs (default: all)")
    args = ap.parse_args(argv)

    cfgs = counties_2024.all_configs()
    slugs = args.slugs or sorted(cfgs)
    rc = 0
    for slug in slugs:
        if slug not in cfgs:
            print(f"[{slug}] no config registered", file=sys.stderr)
            rc = 1
            continue
        cfg = cfgs[slug]
        rc |= (_check(cfg) if args.check else _build(cfg))
    return rc


if __name__ == "__main__":
    sys.exit(main())
