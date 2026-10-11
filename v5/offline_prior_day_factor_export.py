"""Export EXACT V5 strong-core historical factor math from prior-day counters.

Pure calculation over caller-supplied counters, NEVER a DB fetch or certification
of immutable historical state. Native research math functions are reused to
avoid drifting away from v5_strong_core_calibration_pg.py. Result cannot justify
Forward/BUY or prove coefficients had been observed before the race.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Mapping

from v5.offline_archived_six_lane_bridge import ArchivedLane

EPS = 1e-12
MAP_KEYS = frozenset((
    "lw", "lcs", "lcw", "rks", "rkw", "cs", "ct", "rcs",
    "rct", "ps", "pw", "vc", "vn",
))
NESTED = frozenset(("lcs", "lcw", "rcs", "rct", "vc"))
FIVE = ("recent_form", "exhibition_rank", "racer_course", "opponent", "venue_lane")


@dataclass(frozen=True)
class PriorDayCounters:
    fitted_through: date
    history_start: date
    completed_races: int
    counters: Mapping[str, object]
    source_ref: str  # Caller assertion; NOT original source authenticity.


@dataclass(frozen=True)
class FactorVectors:
    reason: str
    race_id: str = ""
    fitted_through: date | None = None
    base_probabilities: tuple[float, ...] = ()
    factors: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    source_state_independently_verified: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _counter_values_good(c: Counter) -> bool:
    return all(type(n) is int and n >= 0 for n in c.values())


def export_prior_day_factors(
    race_id: object, six_lanes: object, state: object,
) -> FactorVectors:
    """Recalculate factor vectors without ANY target-day race outcomes.

    State must have been accumulated exclusively from dates strictly BEFORE
    the race. This function checks the declared through-date; it CANNOT prove
    that counts or date declarations are original or independently trustworthy.
    """
    def fail(reason: str) -> FactorVectors:
        return FactorVectors(reason)

    if type(race_id) is not str or len(race_id) != 14:
        return fail("RACE_ID_INVALID")
    try:
        when = datetime.strptime(race_id[:8], "%Y%m%d").date()
        if (race_id[8] != "_" or race_id[11] != "_"
                or int(race_id[9:11]) not in range(1, 25)
                or int(race_id[12:14]) not in range(1, 13)):
            return fail("RACE_ID_INVALID")
    except (ValueError, IndexError):
        return fail("RACE_ID_INVALID")
    if when < date(2025, 7, 1):
        return fail("DATE_BEFORE_V5_START")
    if (type(state) is not PriorDayCounters
            or type(state.fitted_through) is not date
            or type(state.history_start) is not date
            or state.history_start < date(2025, 7, 1)
            or not state.history_start <= state.fitted_through < when
            or type(state.completed_races) is not int
            or state.completed_races < 1
            or type(state.source_ref) is not str
            or not state.source_ref.strip()):
        return fail("PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED")
    if (type(six_lanes) is not tuple or len(six_lanes) != 6
            or any(type(row) is not ArchivedLane for row in six_lanes)):
        return fail("SIX_LANES_REQUIRED")
    ordered = sorted(six_lanes, key=lambda row: row.lane)
    if (tuple(row.lane for row in ordered) != (1, 2, 3, 4, 5, 6)
            or any(type(row.racer_number) is not int
                   or not 1 <= row.racer_number <= 9999
                   or type(row.racer_class) is not str
                   or not row.racer_class.strip()
                   or type(row.exhibition_time_rank) is not int
                   or row.exhibition_time_rank not in range(1, 7)
                   or type(row.recent_form) is not tuple
                   or not 1 <= len(row.recent_form) <= 5
                   for row in ordered)
            or len({r.racer_number for r in ordered}) != 6
            or len({r.exhibition_time_rank for r in ordered}) != 6):
        return fail("SIX_LANE_FIELDS_INVALID")
    for row in ordered:
        for x in row.recent_form:
            if not isinstance(x, Mapping):
                return fail("RECENT_HISTORY_NOT_PRIOR_DAY")
            try:
                prior = date.fromisoformat(str(x["race_date"]))
            except (KeyError, ValueError, TypeError):
                return fail("RECENT_HISTORY_NOT_PRIOR_DAY")
            if prior >= when:
                return fail("RECENT_HISTORY_NOT_PRIOR_DAY")
    if (not isinstance(state.counters, Mapping)
            or set(state.counters) != MAP_KEYS):
        return fail("PRIOR_DAY_COUNTER_KEYS_INVALID")
    c = state.counters
    if any(not isinstance(c[k], Mapping) for k in MAP_KEYS):
        return fail("PRIOR_DAY_COUNTER_SHAPE_INVALID")
    for k in MAP_KEYS - NESTED:
        if not isinstance(c[k], Counter) or not _counter_values_good(c[k]):
            return fail("PRIOR_DAY_COUNTER_SHAPE_INVALID")
    for k in NESTED:
        if (any(not isinstance(v, Counter) or not _counter_values_good(v)
                for v in c[k].values())
                or k != "vc" and any(x not in c[k] for x in range(1, 7))):
            return fail("PRIOR_DAY_COUNTER_SHAPE_INVALID")

    # Original research helper imports do not call main() or the database.
    from research import v5_lc_rf_exrank_rc_plus_opponent_pg as b
    from research import v5_lane_class_plus_venue_residual_pg as vr

    # Make local Counter copies: helper access may create missing keys.
    q = deepcopy(dict(c))
    for k in NESTED:
        q[k] = defaultdict(Counter, q[k])
    classes = {r.lane: r.racer_class.strip().upper() for r in ordered}
    gp = b.lane_probs(q["lw"], state.completed_races)
    lcp = b.lc_probs(classes, gp, q["lcs"], q["lcw"])
    priors = {i: b.rc_prior(i, q["cs"], q["ct"]) for i in range(1, 7)}
    recent = []
    ex = []
    racer_course = []
    for r in ordered:
        strength, _ = b.recent_strength(list(r.recent_form))
        recent.append(max(strength / b.NEUTRAL, EPS))
        rk = str(r.exhibition_time_rank)
        adjusted, _, _ = b.adjusted(
            (r.lane, classes[r.lane], rk), lcp[r.lane-1], q["rks"], q["rkw"])
        ex.append(max(adjusted/max(lcp[r.lane-1], EPS), EPS))
        rq, _, _ = b.rc_adjusted(
            r.racer_number, r.lane, priors[r.lane], q["rcs"], q["rct"])
        racer_course.append(max(rq/max(priors[r.lane], EPS), EPS))
    opp_lc, _, _ = b.opponent_probs(classes, lcp, q["ps"], q["pw"])
    opponent = [max(opp_lc[i]/max(lcp[i], EPS), EPS) for i in range(6)]
    venue = race_id[9:11]
    vp, _ = vr.venue_shrunk(venue, gp, q["vc"], q["vn"])
    venue_lane = [max(vp[i]/max(gp[i], EPS), EPS) for i in range(6)]
    factor_vectors = dict(zip(FIVE, (
        tuple(recent), tuple(ex), tuple(racer_course),
        tuple(opponent), tuple(venue_lane))))
    result_base = tuple(lcp)
    if (not math.isclose(sum(result_base), 1., rel_tol=0., abs_tol=1e-9)
            or any(not math.isfinite(x) or x <= 0 for x in result_base)
            or any(len(vector) != 6
                   or any(not math.isfinite(x) or x <= 0 for x in vector)
                   for vector in factor_vectors.values())):
        return fail("FACTOR_MATH_INVALID")
    return FactorVectors("RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY",
                         race_id, state.fitted_through,
                         result_base, factor_vectors)
