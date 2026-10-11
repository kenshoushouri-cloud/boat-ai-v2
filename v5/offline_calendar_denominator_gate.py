"""Strict offline gate between seven-day Q1 inventory and period-wide ROI.

An external calendar *claim* is NOT verified official evidence. A Q1-empty
calendar date is NEVER promoted to an official no-race day by this module.
All outputs are scenario-only and never permit Forward/BUY or full-period ROI.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from v5.offline_seven_day_stream_adapter import BatchFeatures
from v5.offline_research_period_batches import ResearchPeriodPlan


@dataclass(frozen=True)
class CalendarDayClaim:
    day: date
    expected_races: int
    source_ref: str  # nonempty declarative reference, NOT verified origin


@dataclass(frozen=True)
class CalendarDayAudit:
    day: date
    q1_races: int
    claimed_expected_races: int | None
    status: str
    independently_verified: bool = field(default=False, init=False)


@dataclass(frozen=True)
class WindowCalendarAudit:
    start: date
    end_exclusive: date
    days: tuple[CalendarDayAudit, ...]
    issues: tuple[str, ...]
    full_window_denominator_verified: bool = field(default=False, init=False)
    hypothetical_roi_authorized: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class PeriodCalendarAudit:
    status: str
    expected_windows: int
    supplied_windows: int
    missing_windows: tuple[tuple[date, date], ...]
    unknown_or_conflicting_days: tuple[date, ...]
    declared_no_race_days_unverified: tuple[date, ...]
    full_period_denominator_verified: bool = field(default=False, init=False)
    hypothetical_roi_authorized: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def audit_window_calendar(start: date, end_exclusive: date, batch: BatchFeatures,
                          claims: tuple[CalendarDayClaim, ...] = ()) -> WindowCalendarAudit:
    """Contrast *claimed* race-day counts with Q1; authenticate neither.

    Do not decide holidays by weekends, missing Q1, or a self-declared source.
    Caller must separately verify every official zero-race day and full roster.
    """
    if (type(start) is not date or type(end_exclusive) is not date
            or start < date(2025, 7, 1)
            or not 1 <= (end_exclusive-start).days <= 7
            or type(batch) is not BatchFeatures or type(claims) is not tuple):
        raise ValueError("WINDOW_OR_BATCH_INVALID")
    expected_days = tuple(start+timedelta(days=i)
                          for i in range((end_exclusive-start).days))
    dayset = set(expected_days)
    ids = batch.inventory_ids
    if (type(ids) is not tuple or not ids or len(ids) > 4000
            or len(set(ids)) != len(ids)):
        raise ValueError("Q1_INVENTORY_INVALID")
    count = Counter()
    for rid in ids:
        if type(rid) is not str or len(rid) < 8 or not rid[:8].isdigit():
            raise ValueError("Q1_RACE_ID_INVALID")
        try:
            d = date.fromisoformat(f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}")
        except ValueError as exc:
            raise ValueError("Q1_RACE_DATE_INVALID") from exc
        if d not in dayset:
            raise ValueError("Q1_RACE_OUTSIDE_WINDOW")
        count[d] += 1
    absent = tuple(day for day in expected_days if not count[day])
    if (type(batch.unrepresented_days) is not tuple
            or batch.unrepresented_days != absent):
        raise ValueError("Q1_UNREPRESENTED_DAYS_INCONSISTENT")
    candidate_ids = tuple(x.race_id for x in batch.candidates)
    pending = batch.pending_ids
    if (type(pending) is not tuple or len(set(candidate_ids+pending))
            != len(ids) or set(candidate_ids+pending) != set(ids)):
        raise ValueError("Q1_CANDIDATE_PENDING_COHORT_INVALID")
    external = {}
    for claim in claims:
        if (type(claim) is not CalendarDayClaim or type(claim.day) is not date
                or claim.day not in dayset or claim.day in external
                or type(claim.expected_races) is not int
                or not 0 <= claim.expected_races <= 288
                or type(claim.source_ref) is not str
                or not claim.source_ref.strip()):
            raise ValueError("CALENDAR_CLAIM_INVALID_OR_DUPLICATE")
        external[claim.day] = claim
    reports=[]
    issues=[]
    for day in expected_days:
        q1 = count[day]
        ext = external.get(day)
        expected = ext.expected_races if ext else None
        if not q1:
            if expected is None:
                status = "HOLD_Q1_EMPTY_UNKNOWN_NOT_PROVEN_HOLIDAY"
            elif expected == 0:
                status = "HOLD_ZERO_RACE_CLAIM_NOT_INDEPENDENTLY_VERIFIED"
            else:
                status = "HOLD_Q1_MISSING_CLAIMED_RACES"
        elif expected is None:
            status = "HOLD_Q1_COUNT_WITHOUT_VERIFIED_SCHEDULE"
        elif expected == 0 or expected < q1:
            status = "HOLD_Q1_EXCEEDS_CALENDAR_CLAIM"
        elif expected > q1:
            status = "HOLD_Q1_FEWER_THAN_CALENDAR_CLAIM"
        else:
            status = "HOLD_MATCHED_CLAIM_NOT_INDEPENDENT_PROOF"
        reports.append(CalendarDayAudit(day,q1,expected,status))
        issues.append(f"{day.isoformat()}:{status}")
    return WindowCalendarAudit(start,end_exclusive,tuple(reports),tuple(issues))


def audit_period_calendar(plan: ResearchPeriodPlan,
                          windows: tuple[WindowCalendarAudit, ...]) -> PeriodCalendarAudit:
    """Preserve missing windows and all unverified no-race dates before ROI.

    Existing rollup_research_period computes only *hypothetical* economics;
    it must not be presented as complete-period ROI without this separate gate.
    """
    if type(plan) is not ResearchPeriodPlan or type(windows) is not tuple:
        raise ValueError("PERIOD_OR_WINDOWS_INVALID")
    planned={(w.start,w.end+timedelta(days=1)) for w in plan.windows}
    seen={}
    for w in windows:
        if type(w) is not WindowCalendarAudit:
            raise ValueError("WINDOW_AUDIT_TYPE_INVALID")
        key=(w.start,w.end_exclusive)
        if key not in planned or key in seen:
            raise ValueError("WINDOW_UNEXPECTED_OR_DUPLICATE")
        expected_days=tuple(w.start+timedelta(days=i)
                            for i in range((w.end_exclusive-w.start).days))
        if tuple(r.day for r in w.days) != expected_days:
            raise ValueError("WINDOW_DAY_COVERAGE_INVALID")
        seen[key]=w
    missing=tuple(sorted(planned-set(seen)))
    days=[r for w in windows for r in w.days]
    unknown=tuple(sorted(r.day for r in days
                         if r.status != "HOLD_MATCHED_CLAIM_NOT_INDEPENDENT_PROOF"
                         and r.status != "HOLD_ZERO_RACE_CLAIM_NOT_INDEPENDENTLY_VERIFIED"))
    claimed_zero=tuple(sorted(r.day for r in days
                              if r.status == "HOLD_ZERO_RACE_CLAIM_NOT_INDEPENDENTLY_VERIFIED"))
    status=("HOLD_MISSING_WINDOW_CALENDAR" if missing else
            "HOLD_OFFICIAL_CALENDAR_ORIGIN_UNVERIFIED")
    return PeriodCalendarAudit(status,len(planned),len(seen),missing,unknown,claimed_zero)
