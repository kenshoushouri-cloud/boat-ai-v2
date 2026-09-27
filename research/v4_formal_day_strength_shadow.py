# -*- coding: utf-8 -*-
"""Pure future-only day-strength shadow for immutable formal V4 artifacts.

No outcomes, payouts, odds, DB, network, persistence, LINE, BUY, or Production
surface exists here. The shadow never changes the formal TOP6/TOP2 contract.

Rule:
- extract the exact six formal rows (daily_rank 1..6);
- day_strength = arithmetic mean of their existing race_score values;
- once seven prior FORMAL_AVAILABLE artifact days exist, reference_strength is
  the median of the seven immediately prior formal-day strengths;
- KEEP_SHADOW iff current day_strength >= reference_strength;
- otherwise SKIP_SHADOW;
- before seven prior formal days: NOT_READY.

The rule is frozen prospectively for target dates >= 2026-09-28.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

CONTRACT = "V4_FORMAL_DAY_STRENGTH_SHADOW_V1"
START_DATE = date(2026, 9, 28)
LOOKBACK_FORMAL_DAYS = 7


@dataclass(frozen=True)
class FormalDay:
    target_date: date
    day_strength: float
    core_races: int


def _formal_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("prospective_evidence_eligible") is not True:
        raise ValueError("artifact is not prospective-evidence eligible")
    if payload.get("purchase_action") is not False:
        raise ValueError("purchase_action must be false")
    fp = payload.get("freeze_provenance") or {}
    if fp.get("outcome_read") is not False or fp.get("payout_read") is not False:
        raise ValueError("artifact must be pre-result")
    summary = payload.get("summary") or {}
    if int(summary.get("core_races") or 0) != 6:
        raise ValueError("exact six formal races required")
    if int(summary.get("core_tickets") or 0) != 12:
        raise ValueError("exact twelve formal tickets required")

    rows = sorted(
        [r for r in payload.get("feed", []) if r.get("daily_rank") is not None],
        key=lambda r: int(r["daily_rank"]),
    )
    if [int(r["daily_rank"]) for r in rows] != [1, 2, 3, 4, 5, 6]:
        raise ValueError("formal ranks must be exactly 1..6")
    for row in rows:
        x = row.get("race_score")
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError("race_score must be numeric")
        if not 0.0 <= float(x) <= 1.0:
            raise ValueError("race_score out of range")
    return rows


def extract_formal_day(payload: dict[str, Any]) -> FormalDay:
    rows = _formal_rows(payload)
    fp = payload.get("freeze_provenance") or {}
    summary = payload.get("summary") or {}
    raw_date = fp.get("target_date") or summary.get("date")
    target = date.fromisoformat(str(raw_date))
    strength = sum(float(r["race_score"]) for r in rows) / 6.0
    return FormalDay(target_date=target, day_strength=strength, core_races=6)


def classify_future_day(
    current: FormalDay,
    prior_formal_days: list[FormalDay],
) -> dict[str, Any]:
    if current.target_date < START_DATE:
        raise ValueError("shadow applies only from 2026-09-28")
    prior = sorted(
        [x for x in prior_formal_days if x.target_date < current.target_date],
        key=lambda x: x.target_date,
    )
    if len(prior) < LOOKBACK_FORMAL_DAYS:
        return {
            "contract": CONTRACT,
            "target_date": current.target_date.isoformat(),
            "classification": "NOT_READY",
            "day_strength": round(current.day_strength, 8),
            "reference_strength": None,
            "lookback_dates": [x.target_date.isoformat() for x in prior[-LOOKBACK_FORMAL_DAYS:]],
            "formal_action_changed": False,
            "promotion_allowed": False,
        }

    lookback = prior[-LOOKBACK_FORMAL_DAYS:]
    reference = float(statistics.median(x.day_strength for x in lookback))
    label = "KEEP_SHADOW" if current.day_strength >= reference else "SKIP_SHADOW"
    return {
        "contract": CONTRACT,
        "target_date": current.target_date.isoformat(),
        "classification": label,
        "day_strength": round(current.day_strength, 8),
        "reference_strength": round(reference, 8),
        "lookback_dates": [x.target_date.isoformat() for x in lookback],
        "lookback_strengths": [round(x.day_strength, 8) for x in lookback],
        "formal_action_changed": False,
        "promotion_allowed": False,
    }


def load_payload(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    raise SystemExit(
        "Pure library only. No live runner/schedule/persistence is activated by this research contract."
    )


if __name__ == "__main__":
    main()
