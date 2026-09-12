# -*- coding: utf-8 -*-
"""Read-only timing audit for S03 PRE candidates versus Bao exhibition capture.

Purpose: determine whether exhibition evidence existed at or before the actual
S03 PRE snapshot. Rows captured after PRE are explicitly classified as future
information and must not be used to judge the PRE candidate.

No DB writes / LINE / BUY / Production behavior changes.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

DAYS = int(os.getenv("VALUE_S03_EX_TIMING_DAYS", "30"))
END_DATE = date.fromisoformat(os.getenv("VALUE_S03_EX_TIMING_END", "2026-09-12"))
START_DATE = END_DATE - timedelta(days=DAYS - 1)
OUTPUT = Path(os.getenv("VALUE_S03_EX_TIMING_OUTPUT", "value-s03-exhibition-timing.json"))


def pct(vals: list[float], q: float):
    if not vals:
        return None
    xs = sorted(vals)
    if len(xs) == 1:
        return round(xs[0], 4)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return round(xs[lo] * (1.0 - frac) + xs[hi] * frac, 4)


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"VALUE_S03_EX_TIMING_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_S03_EX_TIMING_MODE=actual_PRE_snapshot_vs_exhibition_capture_read_only", flush=True)
    print("VALUE_S03_EX_TIMING_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("select to_regclass('public.v2_bao_exhibition_shadow_snapshots') tbl")
            if not cur.fetchone()["tbl"]:
                out = {
                    "contract": "s03_exhibition_timing_v1",
                    "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
                    "table_exists": False,
                    "promotion_allowed": False,
                    "mutation_performed": False,
                }
                OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print("VALUE_S03_EX_TIMING_TABLE_EXISTS=0", flush=True)
                print("VALUE_S03_EX_TIMING_RESULT=PASS_READ_ONLY", flush=True)
                conn.rollback()
                return

            cur.execute(
                """select s.race_id,s.race_date,s.snapshot_at,
                          x.captured_at exhibition_at,x.deadline_at,
                          x.minutes_before
                     from v2_candidate_filter_shadow s
                     left join v2_bao_exhibition_shadow_snapshots x on x.race_id=s.race_id
                    where s.race_date between %s and %s
                      and s.rule_id='S03'
                    order by s.race_date,s.race_id""",
                (START_DATE, END_DATE),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.rollback()

    with_ex = [r for r in rows if r.get("exhibition_at") is not None]
    timing_ready = [
        r for r in with_ex
        if r.get("snapshot_at") is not None and r["exhibition_at"] <= r["snapshot_at"]
    ]
    future_only = [
        r for r in with_ex
        if r.get("snapshot_at") is not None and r["exhibition_at"] > r["snapshot_at"]
    ]
    missing_pre_time = [r for r in with_ex if r.get("snapshot_at") is None]
    deltas = [
        (r["exhibition_at"] - r["snapshot_at"]).total_seconds() / 60.0
        for r in with_ex if r.get("snapshot_at") is not None
    ]

    out = {
        "contract": "s03_exhibition_timing_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "table_exists": True,
        "s03_rows": len(rows),
        "same_race_exhibition_rows": len(with_ex),
        "timing_ready_exhibition_at_or_before_pre": len(timing_ready),
        "future_only_exhibition_after_pre": len(future_only),
        "missing_pre_snapshot_time": len(missing_pre_time),
        "exhibition_minus_pre_minutes": {
            "p05": pct(deltas, 0.05),
            "p50": pct(deltas, 0.50),
            "p95": pct(deltas, 0.95),
            "min": round(min(deltas), 4) if deltas else None,
            "max": round(max(deltas), 4) if deltas else None,
        },
        "rule": "only exhibition_at <= PRE snapshot_at is timing-safe for PRE evaluation",
        "promotion_allowed": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print(f"VALUE_S03_EX_TIMING_S03_ROWS={len(rows)}", flush=True)
    print(f"VALUE_S03_EX_TIMING_SAME_RACE_EX={len(with_ex)}", flush=True)
    print(f"VALUE_S03_EX_TIMING_READY={len(timing_ready)}", flush=True)
    print(f"VALUE_S03_EX_TIMING_FUTURE_ONLY={len(future_only)}", flush=True)
    print("VALUE_S03_EX_TIMING_DELTA_MINUTES=" + json.dumps(out["exhibition_minus_pre_minutes"], sort_keys=True), flush=True)
    print("VALUE_S03_EX_TIMING_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S03_EX_TIMING_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
