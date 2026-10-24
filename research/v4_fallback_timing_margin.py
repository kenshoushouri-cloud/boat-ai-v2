# -*- coding: utf-8 -*-
"""Pure counterfactual timing-margin audit for V4 fallback cron candidates.

No Railway/GitHub mutation or network access exists. Observed timestamps are
frozen evidence from 2026-09-23..2026-09-27. Candidate cron times are compared
by shifting the observed cron->freeze-complete latency without changing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SOURCE_CUTOFF = time(8, 15)
PRIMARY_NOMINAL = time(8, 16)
CURRENT_FALLBACK = time(8, 25)
CANDIDATES = (time(8, 18), time(8, 20), time(8, 22), time(8, 25))

MIN_AFTER_CUTOFF_SECONDS = 5 * 60
MIN_AFTER_PRIMARY_SECONDS = 4 * 60
MIN_PROJECTED_WORST_HEADROOM_SECONDS = 5 * 60


@dataclass(frozen=True)
class Observed:
    day: str
    freeze_completed: str
    earliest_feed_deadline: str


OBSERVED = (
    Observed("2026-09-23", "2026-09-23T08:28:46.600474+09:00", "2026-09-23T08:44:00+09:00"),
    Observed("2026-09-24", "2026-09-24T08:30:35.346808+09:00", "2026-09-24T08:32:00+09:00"),
    Observed("2026-09-25", "2026-09-25T08:28:50.233675+09:00", "2026-09-25T08:32:00+09:00"),
    Observed("2026-09-26", "2026-09-26T08:30:39.396115+09:00", "2026-09-26T08:32:00+09:00"),
    Observed("2026-09-27", "2026-09-27T08:29:31.876029+09:00", "2026-09-27T08:32:00+09:00"),
)


def at(day: str, t: time) -> datetime:
    d = datetime.fromisoformat(day).date()
    return datetime.combine(d, t, tzinfo=JST)


def candidate_report(candidate: time) -> dict:
    per_day = []
    for obs in OBSERVED:
        completed = datetime.fromisoformat(obs.freeze_completed)
        feed_deadline = datetime.fromisoformat(obs.earliest_feed_deadline)
        current_sched = at(obs.day, CURRENT_FALLBACK)
        latency = completed - current_sched
        projected = at(obs.day, candidate) + latency
        headroom = feed_deadline - projected
        per_day.append(
            {
                "date": obs.day,
                "observed_cron_to_complete_seconds": round(latency.total_seconds(), 3),
                "projected_complete_jst": projected.isoformat(),
                "projected_feed_headroom_seconds": round(headroom.total_seconds(), 3),
            }
        )

    cutoff_gap = (
        datetime.combine(datetime.today().date(), candidate)
        - datetime.combine(datetime.today().date(), SOURCE_CUTOFF)
    ).total_seconds()
    primary_gap = (
        datetime.combine(datetime.today().date(), candidate)
        - datetime.combine(datetime.today().date(), PRIMARY_NOMINAL)
    ).total_seconds()
    worst = min(x["projected_feed_headroom_seconds"] for x in per_day)

    checks = {
        "after_cutoff_ge_5m": cutoff_gap >= MIN_AFTER_CUTOFF_SECONDS,
        "after_primary_nominal_ge_4m": primary_gap >= MIN_AFTER_PRIMARY_SECONDS,
        "projected_worst_headroom_ge_5m": worst >= MIN_PROJECTED_WORST_HEADROOM_SECONDS,
    }
    return {
        "candidate_jst": candidate.strftime("%H:%M"),
        "cutoff_gap_seconds": int(cutoff_gap),
        "primary_nominal_gap_seconds": int(primary_gap),
        "projected_worst_feed_headroom_seconds": round(worst, 3),
        "checks": checks,
        "passes_all": all(checks.values()),
        "per_day": per_day,
    }


def evaluate() -> dict:
    reports = [candidate_report(x) for x in CANDIDATES]
    passing = [x for x in reports if x["passes_all"]]
    preferred = passing[0]["candidate_jst"] if len(passing) == 1 else None
    return {
        "contract": "V4_FALLBACK_TIMING_MARGIN_V1",
        "source_cutoff_jst": "08:15",
        "primary_nominal_jst": "08:16",
        "current_fallback_jst": "08:25",
        "criteria": {
            "min_after_cutoff_seconds": MIN_AFTER_CUTOFF_SECONDS,
            "min_after_primary_nominal_seconds": MIN_AFTER_PRIMARY_SECONDS,
            "min_projected_worst_feed_headroom_seconds": MIN_PROJECTED_WORST_HEADROOM_SECONDS,
        },
        "observed_dates": [x.day for x in OBSERVED],
        "candidates": reports,
        "preferred_candidate_for_separate_approval": preferred,
        "railway_change_performed": False,
        "production_change_performed": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2, sort_keys=True))
