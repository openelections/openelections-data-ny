# oe_ny — generic New York OpenElections precinct parsers

A small set of **format-family engines** driven by **per-county Python configs**,
replacing the ~36 standalone `src/2024/<county>_2024_parse.py` scripts. Each old
script repeated the same ~150–250-line skeleton (int/name helpers, party tables,
VP-name stripping, a three-way verification block, and an identical sort/emit
tail). That shared skeleton now lives in one place; a county is described by a
`CountyConfig`, not a bespoke script.

## Layout

```
src/oe_ny/
  common.py        helpers, party tables, name cleaning, precinct-name strategies
  model.py         CountyConfig + ParseResult dataclasses
  verify.py        shared three-way verification (arithmetic / anchors / names)
  output.py        sort + write the 7-column CSV
  engines/
    base.py        Accumulator: candidate/write-in/over/under bookkeeping + fold
    tidy.py        G2  long records (one row per precinct×contest×choice), XLSX/CSV
    tabular.py     G1  wide SOVC (one header row, one row per precinct):
                       modes sheet_per_office | blocks | blocks_by_surname | html_tables
    election_book.py  G3  upright Election-Book PDFs            (stub — not yet built)
    sovc_table.py     G4  rotated SOVC PDFs via extract_tables  (stub — not yet built)
    text_report.py    G5  line-oriented text reports            (stub — not yet built)
  counties_2024/   slug -> CountyConfig, one module per county
  cli.py           `python -m oe_ny [--check] [slug ...]`
```

`ny2024_rpp_parser.py` at the repo root is effectively **engine G6** — the
already-generic "Results per Precinct" / rotated-SOVC PDF parser covering 15
committed counties (Tioga, Tompkins, Ulster, Yates, Jefferson, Dutchess,
Chemung, Oneida, Columbia, Essex, Lewis, Ontario, ...). It is intentionally left
in place; a later pass can move it under `engines/`.

## Running

```bash
# regenerate a county's CSV (writes to 2024/counties/…, prints report + verify)
PYTHONPATH=src uv run python -m oe_ny franklin

# migration gate: diff produced rows against the committed CSV, no overwrite
PYTHONPATH=src uv run python -m oe_ny --check franklin
# -> "[franklin] BYTE-IDENTICAL"  (or ROW-SET-EQUAL / DIFFERS)

# all registered counties
PYTHONPATH=src uv run python -m oe_ny --check
```

Sources default to `openelections-sources-ny/<year>/<election>/<File>`; override a
single county with the `<SLUG>_SRC` env var, or the whole root with
`OE_NY_SOURCE_DIR`.

## Adding a county

1. Create `counties_2024/<slug>.py` exposing `CONFIG = CountyConfig(...)`: set
   `engine`, `office_order`, the `cand` map (office,district,party -> name), the
   `anchors` (official county totals, `_WI` for write-ins), and `engine_opts`.
2. Lift the `CAND`/`ANCHORS`/office maps and any quirk (precinct-name cleanup,
   name typo fixes via `engine_opts['name_aliases']`) from the old script.
3. `--check <slug>` until **BYTE-IDENTICAL**. Only then delete the old
   `src/2024/<slug>_2024_parse.py`, in the same commit.
4. If the county's quirks would bloat the config past ~⅓ of the old script,
   give the config a `parse=<fn>` override (escape hatch) that still uses the
   shared `Accumulator` / `verify` / `output` — see `counties_2024/otsego.py`.

## Semantic invariants (enforced by the engines)

- Fusion **split** into per-party rows unless `fusion="primary-only"`
  (combined-at-source counties: niagara, otsego).
- One aggregate `Write-in` row (party empty) per (precinct, office), emitted
  after the row loop; `writeins="named"` keeps individual named write-ins.
- Overvotes / undervotes / voids / blanks omitted from output; 0-vote rows
  omitted; only the 5 canonical office families kept.
- Output: `county,precinct,office,district,party,candidate,votes`, CRLF, sorted
  by precinct (source order) → office rank → party rank → candidate.

## Migration status

| Family | Engine | Counties | Status |
|--------|--------|----------|--------|
| G2 tidy | built | clinton, livingston, madison, niagara, sullivan, otsego | ✅ 6/6 byte-identical |
| G1 tabular | built | franklin, greene, hamilton, saratoga, wayne, schoharie, montgomery, delaware, cayuga, chautauqua, erie, rensselaer | ✅ 12/12 byte-identical |
| G3 election_book | done | broome, onondaga, westchester, warren, monroe | ✅ 5/5 byte-identical |
| G4 sovc_table | done | orange, st_lawrence, putnam, herkimer, allegany, chenango, cortland, cattaraugus | ✅ 8/8 byte-identical |
| G5 text_report | done | washington, albany, schenectady, schuyler | ✅ 4/4 byte-identical |

**All 35 counties migrated, every one byte-identical to its committed CSV.**  The
old `src/2024/*_2024_parse.py` scripts have been removed.  The tabular engine
covers four sheet layouts (sheet_per_office / blocks / blocks_by_surname /
html_tables) and all four header styles; delaware, cayuga and chautauqua use
`parse` overrides.  The G3 election-book, G4 rotated-SOVC, and G5 text-report
PDFs are each a `parse` override over the shared Accumulator/verify/output — the
"engine" is the shared pipeline, not a single reader.  Rotated-SOVC / text
counties whose committed CSV is in source order set `sort_output=False`;
cattaraugus reuses `ny2024_rpp_parser`'s rotated-diagonal helpers.

Run `python -m oe_ny --check` (with `PYTHONPATH=src`, under `uv`) to re-verify
all 35 against the committed CSVs.

The PDF/text families (G3–G5) are the bespoke-geometry parsers; most will keep
their geometry logic in a per-county `parse` override that plugs into the shared
Accumulator/verify/output pipeline rather than a single fully-generic engine.
