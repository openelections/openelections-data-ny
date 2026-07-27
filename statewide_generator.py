import os
import glob
import csv
import argparse

# Canonical statewide offices to keep in the consolidated file. Mirrors the
# `validOffices` set in src/verifier.py, plus 'U.S. House - Unexpired Term'
# (a distinct special-election contest that is intentionally kept on its own
# label rather than folded into 'U.S. House', which would duplicate rows).
CANONICAL_OFFICES = frozenset([
    'President', 'U.S. Senate', 'U.S. House', 'Governor', 'State Senate',
    'State Assembly', 'Attorney General', 'Secretary of State',
    'State Treasurer', 'Comptroller', 'U.S. House - Unexpired Term',
])

# County files use a handful of non-canonical spellings for statewide offices.
# Map them to the canonical name. Case-insensitive matching against the
# canonical set (below) handles the rest (e.g. 'ATTORNEY GENERAL', 'COMPTROLLER').
OFFICE_VARIANTS = {
    'Assembly': 'State Assembly',
    'State House': 'State Assembly',
    'U.S.House': 'U.S. House',
}

# Core columns always present, written in this canonical order.
CORE_COLUMNS = ['county', 'precinct', 'office', 'district', 'candidate', 'party', 'votes']

# Source columns renamed on output so a given year's statewide header stays
# stable regardless of which county introduced the column.
COLUMN_REMAP = {
    'machine': 'machine_votes',
}


def normalize_office(raw):
    """Return the canonical office name for `raw`, or `raw` unchanged if it is
    not a recognized statewide office (so callers can filter it out)."""
    o = (raw or '').strip()
    if o in CANONICAL_OFFICES:
        return o
    if o in OFFICE_VARIANTS:
        return OFFICE_VARIANTS[o]
    lowered = o.lower()
    for canonical in CANONICAL_OFFICES:
        if canonical.lower() == lowered:
            return canonical
    return o


def remap_column(name):
    return COLUMN_REMAP.get(name, name)


def county_from_filename(fname):
    return os.path.basename(fname).split('__')[3]


def generate_headers(year, election):
    """Print the non-core columns each county file contributes (debug aid)."""
    path = f'{year}/counties/{election}__*__precinct.csv'
    for fname in sorted(glob.glob(path)):
        with open(fname, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            extras = [remap_column(h) for h in headers if h not in CORE_COLUMNS and h != 'notes']
            print(os.path.basename(fname) + ': ' + str(extras))


def generate_offices(year, election):
    """Print the distinct office strings found across county files."""
    path = f'{year}/counties/{election}__*__precinct.csv'
    offices = []
    for fname in sorted(glob.glob(path)):
        with open(fname, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                o = (row.get('office') or '').strip()
                if o and o not in offices:
                    offices.append(o)
    for o in offices:
        print(o)


def generate_consolidated_file(year, election, output_file):
    """Concatenate county precinct files into one statewide precinct file.

    - Keeps only rows whose office normalizes to a canonical statewide office.
    - Drops rows with a blank precinct (county-wide candidate subtotals), which
      do not belong in a precinct-level file. Dropped counts are logged per
      county so anomalies (e.g. a county file with unfixed merged-cell blanks)
      are visible.
    - Writes core columns in canonical order plus the union of every extra
      vote-breakdown column found across the inputs, in stable first-seen order.
    """
    path = f'{year}/counties/{election}__*__precinct.csv'
    files = sorted(glob.glob(path))
    if not files:
        raise SystemExit(f'no county files matched {path}')

    # First pass: discover the union of extra output columns, first-seen order.
    extras = []
    extras_seen = set()
    for fname in files:
        with open(fname, 'r', newline='', encoding='utf-8-sig') as csvfile:
            headers = next(csv.reader(csvfile))
        for h in headers:
            out = remap_column(h)
            if h in CORE_COLUMNS or h == 'notes':
                continue
            if out not in extras_seen:
                extras_seen.add(out)
                extras.append(out)

    header = CORE_COLUMNS + extras
    results = []
    dropped = {}

    for fname in files:
        county = county_from_filename(fname)
        with open(fname, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            # Map each output extra name back to this file's source column, if present.
            src_of_out = {}
            for src in reader.fieldnames:
                src_of_out[remap_column(src)] = src
            for row in reader:
                office = normalize_office(row.get('office', ''))
                if office not in CANONICAL_OFFICES:
                    continue
                precinct = (row.get('precinct') or '').strip()
                if not precinct:
                    dropped[county] = dropped.get(county, 0) + 1
                    continue
                out_row = [
                    row.get('county', ''),
                    precinct,
                    office,
                    row.get('district', ''),
                    row.get('candidate', ''),
                    row.get('party', ''),
                    row.get('votes', ''),
                ]
                for out_name in extras:
                    src = src_of_out.get(out_name)
                    out_row.append(row.get(src, '') if src else '')
                results.append(out_row)

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
    with open(output_file, 'w', newline='', encoding='utf-8') as csv_outfile:
        writer = csv.writer(csv_outfile)
        writer.writerow(header)
        writer.writerows(results)

    total_dropped = sum(dropped.values())
    if dropped:
        detail = ', '.join(f'{c} {n}' for c, n in sorted(dropped.items()))
        print(f'dropped {total_dropped} blank-precinct subtotal rows: {detail}')
    else:
        print('dropped 0 blank-precinct subtotal rows')
    print(f'wrote {len(results)} rows to {output_file} ({len(header)} columns)')


def main():
    parser = argparse.ArgumentParser(description='Generate a statewide NY precinct CSV from county precinct files.')
    parser.add_argument('--year', required=True, help='e.g. 2018')
    parser.add_argument('--election', required=True, help='e.g. 20181106')
    parser.add_argument('--output', help='output path (default: {year}/{election}__ny__general__precinct.csv)')
    parser.add_argument('--headers', action='store_true', help='print per-file extra columns and exit')
    parser.add_argument('--offices', action='store_true', help='print distinct office strings and exit')
    args = parser.parse_args()

    if args.headers:
        generate_headers(args.year, args.election)
        return
    if args.offices:
        generate_offices(args.year, args.election)
        return

    output_file = args.output or f'{args.year}/{args.election}__ny__general__precinct.csv'
    generate_consolidated_file(args.year, args.election, output_file)


if __name__ == '__main__':
    main()