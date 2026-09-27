# -*- coding: utf-8 -*-
"""Read-only timing provenance audit for stored S03 candidate-shadow rows."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

JST = ZoneInfo("Asia/Tokyo")
FORWARD_START = date(2026, 9, 13)
FORWARD_END = date(2026, 9, 27)
OUTPUT = Path(os.getenv("S03_TIMING_AUDIT_OUTPUT", "s03-snapshot-timing-audit.json"))


def jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas: list[float] = []
    null_snapshot = null_deadline = late = pre = wrong_day = 0
    by_window: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "pre": 0, "late": 0})
    late_examples: list[dict[str, Any]] = []
    for row in rows:
        window = str(row.get("window_name") or "unknown")
        by_window[window]["rows"] += 1
        snap = jst(row.get("snapshot_at"))
        deadline = jst(row.get("deadline_at"))
        if snap is None:
            null_snapshot += 1
            continue
        if deadline is None:
            null_deadline += 1
            continue
        race_day = row.get("race_date")
        if hasattr(race_day, "isoformat") and snap.date() != race_day:
            wrong_day += 1
        delta = (deadline - snap).total_seconds() / 60.0
        deltas.append(delta)
        if delta > 0:
            pre += 1
            by_window[window]["pre"] += 1
        else:
            late += 1
            by_window[window]["late"] += 1
            if len(late_examples) < 20:
                late_examples.append({
                    "race_id": str(row.get("race_id")),
                    "race_date": str(row.get("race_date")),
                    "window_name": window,
                    "snapshot_at_jst": snap.isoformat(),
                    "deadline_at_jst": deadline.isoformat(),
                    "minutes_before_deadline": round(delta, 3),
                })
    ds = sorted(deltas)
    def pct(p: float) -> float | None:
        if not ds:
            return None
        return round(ds[int((len(ds)-1)*p)], 3)
    return {
        "rows": len(rows),
        "null_snapshot": null_snapshot,
        "null_deadline": null_deadline,
        "snapshot_day_differs_from_race_date": wrong_day,
        "pre_deadline_rows": pre,
        "late_or_equal_rows": late,
        "pre_deadline_pct": round(pre / (pre + late) * 100.0, 4) if pre + late else None,
        "minutes_before_deadline": {
            "min": round(min(ds), 3) if ds else None,
            "p05": pct(0.05),
            "p25": pct(0.25),
            "median": round(median(ds), 3) if ds else None,
            "p75": pct(0.75),
            "p95": pct(0.95),
            "max": round(max(ds), 3) if ds else None,
        },
        "by_window": dict(sorted(by_window.items())),
        "late_examples": late_examples,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("S03_TIMING_POLICY=READ_ONLY_PROVENANCE_ONLY", flush=True)
    print("S03_TIMING_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """select s.race_id,s.race_date,s.window_name,s.snapshot_at,
                          s.evaluated_at,s.hit,s.return_yen,r.deadline_at
                     from v2_candidate_filter_shadow s
                     join v2_races r on r.race_id=s.race_id
                    where s.rule_id='S03'
                      and s.race_date <= %s
                    order by s.race_date,s.race_id""",
                (FORWARD_END,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.rollback()

    prefreeze = [r for r in rows if r["race_date"] < FORWARD_START]
    forward = [r for r in rows if FORWARD_START <= r["race_date"] <= FORWARD_END]
    result = {
        "contract": "s03_snapshot_timing_provenance_v1",
        "forward_period": {"start": FORWARD_START.isoformat(), "end": FORWARD_END.isoformat()},
        "all_through_forward_end": summarize(rows),
        "pre_freeze": summarize(prefreeze),
        "forward": summarize(forward),
        "safety": {"db_write": False, "line": False, "buy": False, "production_change": False},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("S03_TIMING_PREFREEZE=" + json.dumps(result["pre_freeze"], sort_keys=True), flush=True)
    print("S03_TIMING_FORWARD=" + json.dumps(result["forward"], sort_keys=True), flush=True)
    print("S03_TIMING_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
