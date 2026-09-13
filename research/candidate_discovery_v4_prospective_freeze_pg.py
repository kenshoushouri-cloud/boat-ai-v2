# -*- coding: utf-8 -*-
"""Create a timestamp-proven prospective V4 Forward freeze (READ ONLY).

This wrapper runs the integrated V4 candidate generator without changing the
candidate formula, then fails closed unless the artifact was actually generated
on the target JST date, after the fixed 08:15 source cutoff, from a complete
race-card universe, and before the earliest selected core-race deadline.

It never reads outcomes/payouts, never writes the database, never sends LINE,
and never authorizes purchase or Production promotion.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / ".github" / "scripts" / "candidate_discovery_v4_main_feed_pg.py"
TARGET_DATE = date.fromisoformat(
    os.getenv("CANDIDATE_V4_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
)
SOURCE_CUTOFF = time(8, 15)
RAW_OUTPUT = Path(
    os.getenv("CANDIDATE_V4_RAW_OUTPUT", "candidate-discovery-v4-main-feed.raw.json")
).resolve()
OUTPUT = Path(
    os.getenv("CANDIDATE_V4_PROSPECTIVE_OUTPUT", "candidate-discovery-v4-prospective-freeze.json")
).resolve()
V4_CONTRACT = "candidate_discovery_v4_main_feed_v1"
CORE_RACES = 6
CORE_TICKETS = 12


def _aware(value: Any) -> datetime:
    if not value:
        raise RuntimeError("core deadline missing")
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_generated(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("contract") != V4_CONTRACT:
        raise RuntimeError(f"unexpected V4 contract: {data.get('contract')}")
    for key in ("mutation_performed", "line_sent", "purchase_action", "production_behavior_changed", "promotion_allowed"):
        if data.get(key) is not False:
            raise RuntimeError(f"generated artifact safety flag must be false: {key}")

    summary = data.get("summary") or {}
    scheduled = int(summary.get("scheduled_races") or 0)
    evaluable = int(summary.get("evaluable_races") or 0)
    if scheduled <= 0 or evaluable != scheduled:
        raise RuntimeError(
            f"race universe incomplete: scheduled={scheduled} evaluable={evaluable}"
        )
    if int(summary.get("core_races") or 0) != CORE_RACES:
        raise RuntimeError("V4 core race count mismatch")
    if int(summary.get("core_tickets") or 0) != CORE_TICKETS:
        raise RuntimeError("V4 core ticket count mismatch")

    feed = data.get("feed")
    if not isinstance(feed, list):
        raise RuntimeError("V4 feed list required")
    core = [
        row for row in feed
        if isinstance(row, dict)
        and not bool(row.get("legacy_carryover"))
        and row.get("daily_rank") is not None
    ]
    if len(core) != CORE_RACES:
        raise RuntimeError(f"expected {CORE_RACES} core feed rows, got {len(core)}")
    ranks = sorted(int(row.get("daily_rank") or 0) for row in core)
    if ranks != list(range(1, CORE_RACES + 1)):
        raise RuntimeError(f"invalid core daily ranks: {ranks}")
    for row in core:
        core_tickets = [
            t for t in (row.get("tickets") or [])
            if isinstance(t, dict) and t.get("core_order") in (1, 2)
        ]
        if len(core_tickets) != 2:
            raise RuntimeError(f"core TOP2 ticket contract mismatch: {row.get('race_id')}")
    return core


def main() -> None:
    if not (os.getenv("DATABASE_URL") or "").strip():
        raise RuntimeError("DATABASE_URL required")
    if RAW_OUTPUT == OUTPUT:
        raise RuntimeError("raw and final freeze output paths must differ")

    started = datetime.now(JST)
    cutoff = datetime.combine(TARGET_DATE, SOURCE_CUTOFF, tzinfo=JST)
    if started.date() != TARGET_DATE:
        raise RuntimeError(
            f"prospective freeze target must equal current JST date: target={TARGET_DATE} now={started.date()}"
        )
    if started < cutoff:
        raise RuntimeError(
            f"prospective freeze started before source cutoff: started={started.isoformat()} cutoff={cutoff.isoformat()}"
        )

    env = dict(os.environ)
    env["CANDIDATE_V4_DATE"] = TARGET_DATE.isoformat()
    env["CANDIDATE_V4_OUTPUT"] = str(RAW_OUTPUT)
    print(f"CANDIDATE_V4_PROSPECTIVE_TARGET={TARGET_DATE.isoformat()}", flush=True)
    print(f"CANDIDATE_V4_PROSPECTIVE_STARTED_AT_JST={started.isoformat()}", flush=True)
    print(f"CANDIDATE_V4_PROSPECTIVE_SOURCE_CUTOFF_JST={cutoff.isoformat()}", flush=True)
    print("CANDIDATE_V4_PROSPECTIVE_RESULT_READ=0 PAYOUT_READ=0 DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    subprocess.run([sys.executable, "-u", str(GENERATOR)], cwd=ROOT, env=env, check=True)
    completed = datetime.now(JST)

    data = json.loads(RAW_OUTPUT.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("generated V4 artifact must be a JSON object")
    core = _validate_generated(data)
    deadlines = [_aware(row.get("deadline_at")) for row in core]
    earliest = min(deadlines)
    if started >= earliest or completed >= earliest:
        raise RuntimeError(
            "prospective freeze was not completed before earliest selected core deadline: "
            f"started={started.isoformat()} completed={completed.isoformat()} earliest={earliest.isoformat()}"
        )

    data["generated_at_jst"] = completed.isoformat()
    data["prospective_evidence_eligible"] = True
    data["freeze_provenance"] = {
        "guard_version": "candidate_discovery_v4_pre_result_freeze_v1",
        "mode": "prospective",
        "target_date": TARGET_DATE.isoformat(),
        "started_at_jst": started.isoformat(),
        "completed_at_jst": completed.isoformat(),
        "source_cutoff_at_jst": cutoff.isoformat(),
        "earliest_core_deadline_at_jst": earliest.isoformat(),
        "race_universe_complete": True,
        "prospective_evidence_eligible": True,
        "outcome_read": False,
        "payout_read": False,
        "db_write": False,
    }
    OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    digest = _sha256(OUTPUT)
    print(f"CANDIDATE_V4_PROSPECTIVE_COMPLETED_AT_JST={completed.isoformat()}", flush=True)
    print(f"CANDIDATE_V4_PROSPECTIVE_EARLIEST_CORE_DEADLINE_JST={earliest.isoformat()}", flush=True)
    print(f"CANDIDATE_V4_PROSPECTIVE_JSON_SHA256={digest}", flush=True)
    print("CANDIDATE_V4_PROSPECTIVE_EVIDENCE_ELIGIBLE=true", flush=True)
    print("CANDIDATE_V4_PROSPECTIVE_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_V4_PROSPECTIVE_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_V4_PROSPECTIVE_RESULT=PASS_PRE_RESULT_FREEZE", flush=True)


if __name__ == "__main__":
    main()
