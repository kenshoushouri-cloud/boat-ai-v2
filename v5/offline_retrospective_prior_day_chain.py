"""Strict REFERENCE-SHAPED daily Counter chain from already-held V5 projections.

Pure offline research only; never a production baseline, backtest certification,
historical-first-write evidence, or BUY authorization. This follows the legacy
research loop for ONE specific aspect: daily K course history advances only
on a date having at least one model-fit race. A different all-K-day policy
would be a new experiment, not silent reproduction of the frozen baseline.

Every day between the start and target must be supplied, including empty days.
Day D counters become accessible only AFTER date D, never for date D features.
Caller-supplied positive official/incident/refund evidence remains untrusted.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters
from v5.offline_research_two_population_day import SplitDayProjection

LANES = tuple(range(1, 7))
COURSE = frozenset({"cs", "ct", "rcs", "rct"})


@dataclass(frozen=True)
class HeldResearchDailyCheckpoint:
    day: date
    state: PriorDayCounters
    model_fit_count: int
    course_race_count_applied: int
    k_day_skipped_to_match_research: bool
    historical_observation_authenticated: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class HeldResearchCounterChain:
    checkpoints: tuple[HeldResearchDailyCheckpoint, ...]
    day_count: int
    k_only_days_not_used_in_reference: tuple[date, ...]
    exact_real_history_parity_verified: bool = field(default=False, init=False)
    retrospectively_reconstructed_only: bool = field(default=True, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _empty() -> dict:
    out = {key: Counter() for key in MAP_KEYS - NESTED}
    for key in NESTED - {"vc"}:
        out[key] = {lane: Counter() for lane in LANES}
    out["vc"] = {}
    return out


def _check_day(p: object) -> None:
    if (type(p) is not SplitDayProjection
            or type(p.day) is not date
            or type(p.state) is not PriorDayCounters
            or p.state.fitted_through != p.day
            or p.state.history_start > p.day
            or type(p.state.source_ref) is not str
            or not p.state.source_ref.startswith(
                "RETROSPECTIVE_SPLIT_TWO_POPULATIONS_UNVERIFIED_")
            or p.state.source_ref.split("_")[-1] != p.day.isoformat()
            or p.first_observation_verified
            or p.source_state_independently_verified
            or p.forward_eligible or p.buy_eligible
            or type(p.fit_race_ids) is not tuple
            or type(p.course_race_ids) is not tuple
            or len(set(p.fit_race_ids)) != len(p.fit_race_ids)
            or len(set(p.course_race_ids)) != len(p.course_race_ids)
            or not set(p.fit_race_ids).issubset(p.course_race_ids)
            or p.state.completed_races != len(p.fit_race_ids)
            or set(p.state.counters) != MAP_KEYS):
        raise ValueError("DAY_HELD_PROJECTION_INVALID")
    c = p.state.counters
    base = _empty()
    for key in MAP_KEYS:
        got = c[key]
        if key in NESTED:
            if not isinstance(got, dict):
                raise ValueError("DAY_COUNTER_NESTED_MAP_INVALID")
            if key != "vc" and set(got) != set(LANES):
                raise ValueError("DAY_COUNTER_NESTED_LANES_INVALID")
            if not all(type(v) is Counter for v in got.values()):
                raise ValueError("DAY_COUNTER_NESTED_VALUES_INVALID")
            cells = (v for inner in got.values() for v in inner.values())
        else:
            if type(got) is not Counter:
                raise ValueError("DAY_COUNTER_FLAT_MAP_INVALID")
            cells = got.values()
        if any(type(v) is not int or v < 0 for v in cells):
            raise ValueError("DAY_COUNTER_VALUES_INVALID")
    f, h = len(p.fit_race_ids), len(p.course_race_ids)
    totals = {key: sum(sum(n.values()) for n in c[key].values())
              if key in NESTED else sum(c[key].values())
              for key in MAP_KEYS}
    expected = {
        "lw": f, "lcs": 6*f, "lcw": f,
        "rks": 6*f, "rkw": f, "ps": 30*f, "pw": 5*f,
        "vc": f, "vn": f,
        "cs": 6*h, "ct": 3*h, "rcs": 6*h, "rct": 3*h,
    }
    if totals != expected:
        raise ValueError("DAY_COUNTER_TOTALS_NOT_CONSISTENT")


def chain_reference_calendar_days(
    projections: tuple[SplitDayProjection, ...],
) -> HeldResearchCounterChain:
    """Produce held day-by-day historical rehearsal counters, never BUY.

    Require a contiguous supplied calendar; missing days can hide future rows.
    Reproduce the legacy training-day loop's *daily cohort schedule* exactly:
    course counters update on D only when a model-fit race exists for D.
    This is not a guarantee that the actual research query selected same rows.
    """
    if type(projections) is not tuple or not projections:
        raise ValueError("NONEMPTY_CALENDAR_DAYS_REQUIRED")
    counters = _empty()
    out = []
    skipped = []
    history_start = None
    prior_day = None
    cumulative = 0
    for p in projections:
        _check_day(p)
        if prior_day is not None and p.day != prior_day + timedelta(days=1):
            raise ValueError("CONTIGUOUS_PRIOR_CALENDAR_REQUIRED")
        if history_start is None:
            history_start = p.state.history_start
        elif p.state.history_start != history_start:
            raise ValueError("HISTORY_START_MISMATCH")
        if p.day < history_start:
            raise ValueError("PROJECTION_BEFORE_HISTORY_START")
        fits = len(p.fit_race_ids)
        has_fit_day = fits > 0
        course_applied = len(p.course_race_ids) if has_fit_day else 0
        if not has_fit_day and p.course_race_ids:
            skipped.append(p.day)
        for key in MAP_KEYS:
            if not has_fit_day and key in COURSE:
                continue
            value = p.state.counters[key]
            if key in NESTED:
                for subkey, subcounter in value.items():
                    counters[key].setdefault(subkey, Counter()).update(subcounter)
            else:
                counters[key].update(value)
        cumulative += fits
        state = PriorDayCounters(
            fitted_through=p.day,history_start=history_start,
            completed_races=cumulative,counters=deepcopy(counters),
            source_ref="RETROSPECTIVE_CHAIN_REFERENCE_UNVERIFIED_THROUGH_"
                       + p.day.isoformat(),
        )
        out.append(HeldResearchDailyCheckpoint(
            p.day,state,fits,course_applied,
            bool(not has_fit_day and p.course_race_ids),
        ))
        prior_day=p.day
    return HeldResearchCounterChain(
        tuple(out),len(out),tuple(skipped)
    )
