#!/usr/bin/env python3
"""V5 ConoHa 2GB stage contract. Offline plan/validation ONLY.

This module has no database drivers, network calls, subprocess execution,
credential access, writes, scheduler integration, or betting path.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from typing import Iterable


@dataclass(frozen=True)
class Stage:
    name: str
    needs: tuple[str, ...]
    phase: str
    mode: str
    on_missing: str


STAGES: tuple[Stage, ...] = (
    Stage("roster_prepare", (), "before_deadline", "future_manual_wiring", "RETRY_WITHIN_WINDOW"),
    Stage("beforeinfo_capture", ("roster_prepare",), "before_deadline", "future_manual_wiring", "RETRY_WITHIN_WINDOW"),
    Stage("odds_capture", ("roster_prepare",), "before_deadline", "future_manual_wiring", "RETRY_WITHIN_WINDOW"),
    Stage("evidence_gate", ("beforeinfo_capture", "odds_capture"), "before_deadline", "offline_rule_only", "NO_PREDICTION"),
    Stage("v5_shadow_predict", ("evidence_gate",), "before_deadline", "disabled", "NO_PREDICTION"),
    Stage("result_capture", (), "after_race", "future_manual_wiring", "RETRY_WHEN_OFFICIAL"),
    Stage("result_audit", ("evidence_gate", "result_capture"), "after_race", "disabled", "KEEP_PENDING"),
    Stage("weekly_backtest", ("result_audit",), "offline_historical", "manual_only", "KEEP_PENDING"),
)


class UnsafePlan(ValueError):
    """Fail closed when a declared stage is unsafe or inconsistent."""


def validate_dag(stages: Iterable[Stage]) -> list[str]:
    stages = tuple(stages)
    if len({s.name for s in stages}) != len(stages):
        raise UnsafePlan("duplicate_stage_name")
    by_name = {s.name: s for s in stages}
    required = {
        "roster_prepare", "beforeinfo_capture", "odds_capture", "evidence_gate",
        "v5_shadow_predict", "result_capture", "result_audit", "weekly_backtest",
    }
    if set(by_name) != required:
        raise UnsafePlan("stage_set_not_approved")
    if any("buy" in s.name.lower() or "ticket" in s.name.lower() or "purchase" in s.name.lower() for s in stages):
        raise UnsafePlan("buy_stage_forbidden")
    if any(s.mode not in ("future_manual_wiring", "offline_rule_only", "disabled", "manual_only") for s in stages):
        raise UnsafePlan("execution_not_authorized")
    if any(s.phase not in ("before_deadline", "after_race", "offline_historical") for s in stages):
        raise UnsafePlan("unapproved_phase")
    if set(by_name["v5_shadow_predict"].needs) != {"evidence_gate"}:
        raise UnsafePlan("prediction_requires_evidence_gate")
    if set(by_name["evidence_gate"].needs) != {"beforeinfo_capture", "odds_capture"}:
        raise UnsafePlan("evidence_gate_requires_both_sources")
    if set(by_name["result_audit"].needs) != {"evidence_gate", "result_capture"}:
        raise UnsafePlan("audit_requires_gate_and_official_results")
    if set(by_name["weekly_backtest"].needs) != {"result_audit"}:
        raise UnsafePlan("backtest_requires_audit")
    if "result_capture" in by_name["v5_shadow_predict"].needs:
        raise UnsafePlan("future_information_leak")
    ordered: list[str] = []
    remaining = set(by_name)
    while remaining:
        phase_order = {"before_deadline": 0, "after_race": 1, "offline_historical": 2}
        ready = sorted(
            (n for n in remaining if set(by_name[n].needs) <= set(ordered)),
            key=lambda n: (phase_order[by_name[n].phase], n),
        )
        if not ready:
            raise UnsafePlan("cycle_or_unknown_dependency")
        chosen = ready[0]
        ordered.append(chosen)
        remaining.remove(chosen)
    # No after-race information may be an ancestor of a predeadline stage.
    for name in ordered:
        if by_name[name].phase == "before_deadline":
            ancestors = set(by_name[name].needs)
            todo = list(ancestors)
            while todo:
                n = todo.pop()
                if by_name[n].phase != "before_deadline":
                    raise UnsafePlan("future_information_leak")
                for parent in by_name[n].needs:
                    if parent not in ancestors:
                        ancestors.add(parent)
                        todo.append(parent)
    return ordered


@dataclass(frozen=True)
class Evidence:
    deadline_at: datetime
    captured_at: datetime | None
    roster_complete: bool
    beforeinfo_complete: bool
    odds_complete: bool
    captured_before_decision_proven: bool
    source_is_historical_replay: bool
    already_frozen: bool


def gate(e: Evidence) -> str:
    """A positive result permits only a future SHADOW forecast, never a purchase.

    Missing evidence remains missing; historical replay cannot stand in for
    an actual pre-deadline observation. No result information is consumed.
    """
    if e.already_frozen:
        return "SKIP_ALREADY_FROZEN"
    if e.source_is_historical_replay:
        return "SKIP_HISTORICAL_NOT_FORWARD"
    if e.deadline_at.tzinfo is None or e.deadline_at.utcoffset() is None:
        return "SKIP_UNTRUSTED_TIMESTAMP"
    if e.captured_at is None or e.captured_at.tzinfo is None or e.captured_at.utcoffset() is None:
        return "SKIP_MISSING_CAPTURE_PROOF"
    if not e.captured_before_decision_proven:
        return "SKIP_MISSING_CAPTURE_PROOF"
    if e.captured_at.astimezone(timezone.utc) >= e.deadline_at.astimezone(timezone.utc):
        return "SKIP_LATE_CAPTURE"
    if not e.roster_complete:
        return "SKIP_MISSING_ROSTER"
    if not e.beforeinfo_complete:
        return "SKIP_MISSING_BEFOREINFO"
    if not e.odds_complete:
        return "SKIP_MISSING_ODDS"
    return "READY_SHADOW_ONLY_BUY_HARD_HOLD"


def main() -> int:
    parser = argparse.ArgumentParser(description="V5 ConoHa offline DAG plan; never runs jobs")
    parser.add_argument("--race-date", required=True, help="YYYY-MM-DD; for plan label only")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        target = date.fromisoformat(args.race_date)
        if args.race_date != target.isoformat():
            raise ValueError()
    except ValueError:
        parser.error("race-date must be a valid YYYY-MM-DD")
    order = validate_dag(STAGES)
    by_name = {s.name: s for s in STAGES}
    result = {
        "race_date": args.race_date,
        "mode": "OFFLINE_PLAN_NO_EXECUTION",
        "runtime_enabled": False,
        "db_connection": False,
        "network_connection": False,
        "buy": "HARD_HOLD",
        "ordering": [asdict(by_name[n]) for n in order],
        "concurrency": "one bounded job using v5_serial_resource_guard.sh; lock required for ALL writers",
        "idempotency": "(race_id, deadline_at, stage, snapshot_version); never overwrite prior frozen evidence",
        "retry": "within source window only; rate-limit; no historical backfill as forward proof",
        "pending": "retain missing/no-buy/refund/unknown records; never silently drop from ROI",
        "warning": "No collection, prediction, purchase, backup, DB, network, or restore was executed",
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("V5_DAG=OFFLINE_PLAN_ONLY", "RACE_DATE=" + args.race_date, "BUY=HARD_HOLD", sep="\n")
        for i, s in enumerate(result["ordering"], start=1):
            print(f"{i:02d} {s['name']} <- {','.join(s['needs']) or 'none'} [{s['phase']}] mode:{s['mode']} missing:{s['on_missing']}")
        print("V5_DAG_PRODUCTION_READY=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
