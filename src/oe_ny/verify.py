"""Shared three-way verification for the NY generic parsers.

Ported once from the per-county scripts, where it was copy-pasted ~36 times:

  1. per (precinct, office): candidate + write-in + over + under == the source's
     Total Votes / Ballots Cast row (only when the source provides that total).
  2. per (office, district, party): precinct-sum == source TOTAL row == the
     hardcoded ANCHOR (whichever of the three the source/config provides).
  3. candidate-name cross-check: each (office,district,party)'s source name(s)
     normalize to the configured canonical name.

Returns a list of human-readable HARD failures; empty means clean.
"""
from __future__ import annotations

from .common import norm
from .model import CountyConfig, ParseResult

PARTY_LINES = ("DEM", "REP", "CON", "WOR", "LAR", "PFP", "POP", "RSF", "ECO",
               "IND", "Local 607")


def verify(cfg: CountyConfig, res: ParseResult) -> list[str]:
    hard: list[str] = []
    cand = cfg.cand
    anchors = cfg.anchors
    aliases = cfg.engine_opts.get("name_aliases", {})

    # 1. per (precinct, office): arithmetic vs Total row -----------------------
    keys = set(res.ed_total) | set(res.ed_cand) | set(res.ed_wi)
    for key in keys:
        tot = res.ed_total.get(key, 0)
        if not tot:
            continue  # source gave no per-precinct total to check against
        c = res.ed_cand.get(key, 0)
        w = res.ed_wi.get(key, 0)
        o = res.ed_over.get(key, 0)
        u = res.ed_under.get(key, 0)
        if c + w + o + u != tot:
            hard.append(f"{key}: cand({c})+wi({w})+over({o})+under({u})"
                        f"={c + w + o + u} != Total={tot}")

    # 2. per (office, district, party): psum == TOTAL == ANCHOR ----------------
    for od in res.od_seen or cfg.office_order:
        office, district = od
        for p in PARTY_LINES:
            odp = (office, district, p)
            if odp not in cand:
                continue
            s = res.psum.get(odp, 0)
            tr = res.col_total.get(odp)
            an = anchors.get(odp)
            if tr is not None and s != tr:
                hard.append(f"{office}/{district} {p}: precinct-sum={s} "
                            f"!= TOTAL={tr}")
            if an is not None and tr is not None and tr != an:
                hard.append(f"{office}/{district} {p}: TOTAL={tr} != ANCHOR={an}")
            if an is not None and s != an:
                hard.append(f"{office}/{district} {p}: precinct-sum={s} "
                            f"!= ANCHOR={an}")
        # write-in aggregate
        ws = res.wisum.get(od, 0)
        wt = res.wi_total.get(od)
        aw = anchors.get((office, district, "_WI"))
        if wt is not None and ws != wt:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws} "
                        f"!= TOTAL={wt}")
        if aw is not None and wt is not None and wt != aw:
            hard.append(f"{office}/{district} write-in: TOTAL={wt} != ANCHOR={aw}")
        if aw is not None and ws != aw:
            hard.append(f"{office}/{district} write-in: precinct-sum={ws} "
                        f"!= ANCHOR={aw}")

    # 3. candidate-name cross-check -------------------------------------------
    for odp, names in res.name_seen.items():
        expected = cand.get(odp)
        if expected is None:
            continue
        exp = norm(expected)
        for nm in names:
            src = aliases.get(nm, nm)
            if src and norm(src) != exp:
                hard.append(f"{odp[0]}/{odp[1]} {odp[2]}: source {nm!r} "
                            f"!= expected {expected!r}")
    return hard
