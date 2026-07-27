#!/usr/bin/env python3
"""Regenerate the 2020 Cattaraugus precinct CSV from the source PDF (issue #118).

Root cause (verified with cattaraugus_2020_verify.py / _align.py): the existing
CSV's per-candidate `votes` (machine) column is a faithful extraction of the PDF,
but the `absentee` column is corrupted for many precincts (e.g. Red House: CSV
absentee sums to 63 against only 21 machine ballots). The PDF is the source of
truth.

OpenElections convention: `votes` = TOTAL (machine + absentee); `absentee` =
the absentee subset. This parser keeps the CSV as a scaffold (county, precinct,
office, district, candidate, party are correct and preserved) and replaces
only `votes` and `absentee` from the PDF:

  votes    = PDF machine per-line + PDF absentee per-line
  absentee = PDF absentee per-line

PDF row layout per precinct/office (a machine row, then an "Absentees &
Affidavits" row with the same column layout):

  [Total Votes Cast][candidate-total cols][per-line votes in party order]
  [write-ins][voids][blanks][occasional stray trailing value]

Column mapping is by X-COORDINATE, not by counting columns, because rows are
not uniformly sized: some machine rows carry a stray trailing value, and some
absentee rows omit zero columns (e.g. Otto). Crucially, each precinct's machine
row and its absentee row share the same column grid, so we derive the per-line
column x0 positions from the precinct's OWN (complete) machine row and match
that precinct's absentee digits to those same x0 positions (value 0 when a
column is absent). The per-line columns are the machine data columns
[1+ntotals : 1+ntotals+plc]; ntotals (candidate-total column count) is constant
per office and is detected by best-match of PDF machine per-line vs the CSV's
existing (correct) machine values.

"Ballots Cast" is a turnout row not printed as its own PDF office; the existing
file derives it from the President "Total Votes Cast" figures, so we do too:
  Ballots Cast votes    = President machine total + President absentee total
  Ballots Cast absentee = President absentee total
"""
import csv
import sys
import pdfplumber

PDF = "/Users/dwillis/code/openelections-sources-ny/2020/Cattaraugus NY 2020 GENERAL ELECTION OFFICAL RESULTS.pdf"
CSV = "2020/counties/20201103__ny__general__cattaraugus__precinct.csv"

OFFICE_PAGES = {
    "President": [1, 2],
    "U.S. House": [5, 6],
    "State Senate": [7, 8],
    "State Assembly": [9, 10],
}

SKIP_FIRST = {
    "PAGE", "VOTE", "TOTAL", "PRESIDENTIAL", "ELECTORS", "FOR", "PRESIDENT",
    "AND", "VICE", "ONE", "STATE", "SENATOR", "ASSEMBLY", "MEMBER",
    "REPRESENTATIVE", "CONGRESS", "TOM", "TRACY", "JOSEPH", "DONALD", "HOWIE",
    "JO", "BROCK", "ANDREW", "FRANK", "GEORGE", "W.",
}

# Nearest-x0 tolerance for matching an absentee row's digits to the precinct's
# own machine-row column x0. Machine and absentee rows share the same grid, so
# the alignment is near-exact; 6px is comfortable and well below the ~17px
# spacing between adjacent columns.
TOL = 6.0


def toi(s):
    try:
        return int(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def is_num(tok):
    return tok.replace(",", "").isdigit()


def cluster_rows(pg, gap=4):
    """Group words into visual rows (a precinct label and its numbers share a
    near-equal `top`)."""
    words = sorted(pg.extract_words(use_text_flow=False, keep_blank_chars=False),
                  key=lambda w: (w["top"], w["x0"]))
    out, cur, prev = [], [], None
    for w in words:
        if prev is None or abs(w["top"] - prev) <= gap:
            cur.append(w)
        else:
            out.append(cur)
            cur = [w]
        prev = w["top"]
    if cur:
        out.append(cur)
    return [sorted(c, key=lambda w: w["x0"]) for c in out]


def name_and_data(cl):
    """Split a machine row into (precinct_name, data_digits) using the largest
    x0 gap as the name/data boundary. Machine rows are complete (no internal
    gap larger than the name/data gap), so the largest gap is the name/data
    boundary. data_digits = (x0, value) for numeric tokens right of it."""
    s = sorted(cl, key=lambda w: w["x0"])
    xs = [w["x0"] for w in s]
    if len(xs) < 2:
        return " ".join(w["text"] for w in s).strip(), []
    best, idx = -1.0, len(xs)
    for i in range(1, len(xs)):
        g = xs[i] - xs[i - 1]
        if g > best:
            best, idx = g, i
    boundary = xs[idx]
    name = " ".join(w["text"] for w in s if w["x0"] < boundary).strip()
    # data columns are right-aligned: use x1 (right edge) as the stable column
    # key, since x0 (left edge) shifts with the number of digits.
    data = [(w["x1"], toi(w["text"])) for w in s
            if w["x0"] >= boundary and is_num(w["text"])]
    return name, data


def digits_of(cl):
    return [(w["x1"], toi(w["text"])) for w in cl if is_num(w["text"])]


def match_to_cols(digits, col_x0):
    """Return [value for each col_x0] by nearest x0 (within TOL), else 0."""
    out = []
    for cx in col_x0:
        val = 0
        best = TOL
        for x, v in digits:
            d = abs(x - cx)
            if d <= best:
                best = d
                val = v
        out.append(val)
    return out


def extract_office(pdf_path, pages):
    """Return {precinct: (mach_data_digits, abs_digits|None)} where
    mach_data_digits is the sorted (x0,value) list for that precinct's machine
    row (name already excluded), and abs_digits is its absentee row's digits."""
    out = {}
    with pdfplumber.open(pdf_path) as pdoc:
        for pno in pages:
            seq = []
            for cl in cluster_rows(pdoc.pages[pno - 1]):
                full = " ".join(w["text"] for w in cl)
                low = full.lower()
                if "absent" in low or "affidavit" in low:
                    seq.append(("abs", None, digits_of(cl)))
                    continue
                name, data = name_and_data(cl)
                if not name or not name[0].isalpha():
                    continue
                if name.split()[0].upper() in SKIP_FIRST or name.upper().startswith("CATTARAUGUS"):
                    continue
                seq.append(("mach", name, data))
            i = 0
            while i < len(seq):
                kind, name, data = seq[i]
                if kind == "mach":
                    ab = None
                    if i + 1 < len(seq) and seq[i + 1][0] == "abs":
                        ab = seq[i + 1][2]
                        i += 2
                    else:
                        i += 1
                    out[name] = (data, ab)
                else:
                    i += 1
    return out


def per_line_columns(mach_data, ntotals, plc):
    """The per-line column x0 = mach data x0[1+ntotals : 1+ntotals+plc]."""
    xs = sorted(x for x, _ in mach_data)
    return xs[1 + ntotals:1 + ntotals + plc], (xs[0] if xs else None)


def detect_ntotals(records, csv_machine_by_prec, plc):
    """Pick ntotals in [0..6] maximizing exact machine per-line matches."""
    best, best_score = 0, -1
    for nt in range(0, 7):
        score = 0
        for name, (mach, _ab) in records.items():
            cm = csv_machine_by_prec.get(name)
            if cm is None or len(cm) != plc:
                continue
            col_x0, _tot = per_line_columns(mach, nt, plc)
            if len(col_x0) != plc:
                continue
            # machine per-line values: exact (the precinct's own columns)
            xs_val = {x: v for x, v in mach}
            per = [xs_val.get(cx, 0) for cx in col_x0]
            if per == cm:
                score += 1
        if score > best_score:
            best, best_score = nt, score
    return best, best_score


def main():
    verify_only = "--verify" in sys.argv

    scaffold = {}
    with open(CSV, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            scaffold.setdefault(r["office"], {}).setdefault(r["precinct"], []).append(r)

    pdf = {}
    ntotals = {}
    for office, pages in OFFICE_PAGES.items():
        recs = extract_office(PDF, pages)
        pdf[office] = recs
        csv_mach = {p: [int(r["votes"]) for r in rows] for p, rows in scaffold[office].items()}
        plc = len(next(iter(csv_mach.values()))) if csv_mach else 0
        nt, score = detect_ntotals(recs, csv_mach, plc)
        ntotals[office] = nt
        print(f"{office}: ntotals={nt} (matched {score}/{len(csv_mach)}), "
              f"PDF precincts={len(recs)}, plc={plc}")

    corrected = {}
    problems = 0
    for office in OFFICE_PAGES:
        nt = ntotals[office]
        for prec, rows in scaffold[office].items():
            plc = len(rows)
            rec = pdf[office].get(prec)
            if rec is None:
                print(f"  MISSING in PDF: {office} / {prec!r}")
                problems += 1
                continue
            mach, ab = rec
            col_x0, tot_x0 = per_line_columns(mach, nt, plc)
            if len(col_x0) != plc:
                print(f"  FEW COLS: {office} / {prec!r}: mach data len {len(mach)} (need {1+nt+plc})")
                problems += 1
                continue
            xs_val = {x: v for x, v in mach}
            mach_per = [xs_val.get(cx, 0) for cx in col_x0]
            csv_mach = [int(r["votes"]) for r in rows]
            if mach_per != csv_mach:
                print(f"  MACHINE MISMATCH {office} / {prec!r}: pdf={mach_per} csv={csv_mach}")
                problems += 1
                continue
            abs_per = match_to_cols(ab, col_x0) if ab else [0] * plc
            # invariant: sum of absentee per-line == absentee row's Total Votes Cast
            if ab is not None:
                ab_tot = next((v for x, v in ab if abs(x - tot_x0) <= TOL), 0)
                if sum(abs_per) != ab_tot:
                    print(f"  ABSENTEE SUM MISMATCH {office} / {prec!r}: "
                          f"sum={sum(abs_per)} pdf_total={ab_tot} per={abs_per}")
                    problems += 1
                    continue
            corrected[(office, prec)] = [(m + a, a) for m, a in zip(mach_per, abs_per)]

    # Ballots Cast from President totals.
    pres = pdf["President"]
    for prec, rows in scaffold.get("Ballots Cast", {}).items():
        if prec not in pres:
            print(f"  MISSING President for Ballots Cast / {prec!r}")
            problems += 1
            continue
        mach, ab = pres[prec]
        tot_x0 = sorted(x for x, _ in mach)[0]
        m_tot = next((v for x, v in mach if abs(x - tot_x0) <= TOL), 0)
        a_tot = 0
        if ab:
            a_tot = next((v for x, v in ab if abs(x - tot_x0) <= TOL), 0)
        corrected[("Ballots Cast", prec)] = [(m_tot + a_tot, a_tot)]

    print(f"\nAlignment problems: {problems}")

    changed = 0
    bad = 0
    for office in list(OFFICE_PAGES) + ["Ballots Cast"]:
        for prec, rows in scaffold.get(office, {}).items():
            key = (office, prec)
            if key not in corrected:
                continue
            for r, (v, a) in zip(rows, corrected[key]):
                old_a = int(r["absentee"]) if r["absentee"] else 0
                if old_a != a:
                    changed += 1
                if a > v:
                    bad += 1
    print(f"Rows with changed absentee: {changed}")
    print(f"Rows with absentee > votes (must be 0): {bad}")

    if verify_only or problems or bad:
        return 1 if (problems or bad) else 0

    # Build a per-row lookup keyed by (office, precinct, candidate, party), then
    # iterate the ORIGINAL file in order so only votes/absentee change and the row
    # order (office/precinct/candidate) is preserved exactly — minimal diff.
    lookup = {}
    for office in OFFICE_PAGES:
        for prec, rows in scaffold[office].items():
            key = (office, prec)
            if key not in corrected:
                continue
            for r, (v, a) in zip(rows, corrected[key]):
                lookup[(r["office"], r["precinct"], r["candidate"], r["party"])] = (v, a)
    for prec, rows in scaffold.get("Ballots Cast", {}).items():
        key = ("Ballots Cast", prec)
        if key not in corrected:
            continue
        for r, (v, a) in zip(rows, corrected[key]):
            lookup[(r["office"], r["precinct"], r["candidate"], r["party"])] = (v, a)

    header = ["county", "precinct", "office", "district", "candidate", "party", "votes", "absentee"]
    with open(CSV, newline="", encoding="utf-8-sig") as inf:
        rows_in = list(csv.DictReader(inf))
    written = 0
    with open(CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows_in:
            v, a = lookup.get((r["office"], r["precinct"], r["candidate"], r["party"]),
                              (r["votes"], r["absentee"]))
            w.writerow([r["county"], r["precinct"], r["office"], r["district"],
                        r["candidate"], r["party"], v, a])
            written += 1
    print(f"wrote {written} rows to {CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())