#!/usr/bin/env python3
"""Per-precinct verification of cattaraugus_2024_parse.py output against the
source PDF. For each contest and precinct, independently re-extract the main
row + four counting-group sub-rows, sum each candidate/party column by the
rightmost-below rule, and compare every value to the CSV. Reports any
mismatch with the source PDF coordinates."""
import os, sys, csv, pdfplumber
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ny2024_rpp_parser as P
import cattaraugus_2024_parse as C

PDF = C.PDF_PATH
CSV = C.OUT_PATH
CONTESTS = C.CONTESTS
SUBROW = C.SUBROW_PREFIXES


def block_values(doc, office, district, pages):
    """Re-derive per-precinct {(candidate,party): votes} from raw PDF rows,
    using the same anchors/cls as the parser but recomputing from scratch."""
    anchors, tvc_xmin = C.contest_anchors(doc, pages)
    party_codes = C.contest_party_codes(doc, pages)
    cls = [C.classify_anchor(a, party_codes) for a in anchors]
    xmin = tvc_xmin - 5
    blocks = []
    cur = None
    for pi in pages:
        page = doc.pages[pi - 1]
        ws = [dict(w, page=pi) for w in
              page.filter(P._is_upright_obj).extract_words(use_text_flow=False)]
        for line in P.cluster_lines(ws, gap=4):
            if not line:
                continue
            first = line[0]["text"]
            txt = P.line_text(line).strip()
            vnums = C.vote_numbers(line, xmin)
            if txt.startswith("TOTAL") or txt.startswith("Total"):
                cur = None
                continue
            if any(txt.startswith(p) for p in SUBROW):
                if cur is not None and vnums:
                    C._add_block(cur, vnums, anchors, cls)
                continue
            if len(vnums) < 3:
                continue
            if first in C.HEADER_FIRST or C.is_num(first):
                continue
            name = C.precinct_name(line, xmin)
            if not name:
                continue
            cur = {"name": name, "cols": {}}
            blocks.append(cur)
            C._add_block(cur, vnums, anchors, cls)
    out = {}
    for b in blocks:
        per = {}
        for a, c in zip(anchors, cls):
            v = b["cols"].get(a["anchor_x"], 0)
            if c["kind"] == "party":
                per[(a["name"], c["party"])] = v
            elif c["kind"] == "writein":
                per[("Write-in", "")] = v
        out[b["name"]] = per
    return out


def main():
    csv_rows = {}
    for r in csv.DictReader(open(CSV)):
        csv_rows.setdefault((r["office"], r["precinct"]), {})[(r["candidate"], r["party"])] = int(r["votes"])

    problems = 0
    checked = 0
    with pdfplumber.open(PDF) as doc:
        for office, district, pages in CONTESTS:
            src = block_values(doc, office, district, pages)
            for precinct, per in src.items():
                ck = (office, precinct)
                if ck not in csv_rows:
                    print(f"MISSING precinct in CSV: {office} / {precinct!r}")
                    problems += 1
                    continue
                csvp = csv_rows[ck]
                # every source (cand,party) must match CSV
                for k, v in per.items():
                    checked += 1
                    cv = csvp.get(k)
                    if cv is None:
                        print(f"MISSING row {office}/{precinct!r}/{k} src={v}")
                        problems += 1
                    elif cv != v:
                        print(f"MISMATCH {office}/{precinct!r}/{k}: csv={cv} src={v}")
                        problems += 1
                # CSV must not have extra (cand,party) not in source
                for k in csvp:
                    if k not in per:
                        print(f"EXTRA csv row {office}/{precinct!r}/{k} csv={csvp[k]}")
                        problems += 1
    print(f"\nChecked {checked} (precinct,candidate) values across {len(CONTESTS)} offices.")
    if problems:
        print(f"{problems} PROBLEMS")
        return 1
    print("ALL PER-PRECINCT VALUES MATCH SOURCE PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())