"""Shared bookkeeping for engines.

The ``Accumulator`` collects candidate / write-in / over / under / total tallies
exactly the way every per-county script did (psum, wisum, ed_cand, ed_wi, ...),
folds write-ins into one aggregate row per (precinct, office), drops 0-vote
rows, and produces a :class:`ParseResult` for verification and output.
"""
from __future__ import annotations

from collections import defaultdict

from ..common import resolve_precinct_name, strip_vp
from ..model import CountyConfig, ParseResult


class Accumulator:
    def __init__(self, cfg: CountyConfig):
        self.cfg = cfg
        self._pn = resolve_precinct_name(cfg.precinct_name)
        self.rows: list = []
        self.prec_order: list[str] = []
        self._seen_prec: set[str] = set()
        self.od_seen: list = []
        self.psum = defaultdict(int)
        self.wisum = defaultdict(int)
        self.col_total: dict = {}
        self.wi_total: dict = {}
        self.name_seen = defaultdict(set)
        self.ed_cand = defaultdict(int)
        self.ed_wi = defaultdict(int)
        self.ed_over = defaultdict(int)
        self.ed_under = defaultdict(int)
        self.ed_total = defaultdict(int)
        self.notes: list[str] = []
        # named write-in rows collected verbatim (writeins == "named")
        self._named_wi: list = []

    # -- precinct / office registration --------------------------------------

    def precinct(self, raw_label: str) -> str:
        prec = self._pn(raw_label)
        if prec not in self._seen_prec:
            self._seen_prec.add(prec)
            self.prec_order.append(prec)
        return prec

    def see_od(self, od) -> None:
        if od not in self.od_seen:
            self.od_seen.append(od)

    # -- tallies -------------------------------------------------------------

    def candidate(self, prec, office, district, party, votes, src_name=None,
                  name=None):
        """Record a candidate party-line tally; emits a row when votes>0.

        The output candidate name is ``name`` if given, else
        cfg.cand[(office,district,party)]; ``src_name`` (if given) feeds the
        name cross-check.
        """
        odp = (office, district, party)
        self.psum[odp] += votes
        self.ed_cand[(prec, office, district)] += votes
        if src_name is not None:
            self.name_seen[odp].add(src_name)
        out_name = name if name is not None else self.cfg.cand.get(odp)
        if votes > 0 and out_name is not None:
            self.rows.append((prec, office, district, party, out_name, votes))
        return out_name

    def writein(self, prec, office, district, votes):
        """Accumulate write-in votes for the folded aggregate row."""
        self.wisum[(office, district)] += votes
        self.ed_wi[(prec, office, district)] += votes

    def named_writein(self, prec, office, district, name, votes):
        """Keep an individual named write-in row (writeins == 'named')."""
        self.wisum[(office, district)] += votes
        self.ed_wi[(prec, office, district)] += votes
        if votes > 0:
            self._named_wi.append((prec, office, district, "", name, votes))

    def over(self, prec, office, district, votes):
        self.ed_over[(prec, office, district)] += votes

    def under(self, prec, office, district, votes):
        self.ed_under[(prec, office, district)] += votes

    def total(self, prec, office, district, votes):
        self.ed_total[(prec, office, district)] += votes

    def set_col_total(self, office, district, party, votes):
        self.col_total[(office, district, party)] = votes

    def add_col_total(self, office, district, party, votes):
        k = (office, district, party)
        self.col_total[k] = self.col_total.get(k, 0) + votes

    def add_wi_total(self, office, district, votes):
        k = (office, district)
        self.wi_total[k] = self.wi_total.get(k, 0) + votes

    def set_wi_total(self, office, district, votes):
        self.wi_total[(office, district)] = votes

    def president_name(self, raw: str) -> str:
        return strip_vp(raw)

    # -- finish --------------------------------------------------------------

    def result(self) -> ParseResult:
        rows = list(self.rows)
        if self.cfg.writeins == "named":
            rows.extend(self._named_wi)
        else:
            for (prec, office, district), w in self.ed_wi.items():
                if w > 0:
                    rows.append((prec, office, district, "", "Write-in", w))
        return ParseResult(
            rows=rows,
            prec_order=self.prec_order,
            od_seen=self.od_seen or list(self.cfg.office_order),
            psum=self.psum,
            wisum=self.wisum,
            col_total=self.col_total,
            wi_total=self.wi_total,
            ed_cand=self.ed_cand,
            ed_wi=self.ed_wi,
            ed_over=self.ed_over,
            ed_under=self.ed_under,
            ed_total=self.ed_total,
            name_seen=self.name_seen,
            notes=self.notes,
        )
