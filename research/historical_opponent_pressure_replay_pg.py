# -*- coding: utf-8 -*-
"""Historical replay of frozen Opponent Pressure v2 using prior data only.

This reuses the frozen v2 scoring implementation but deliberately writes a
separate model_version=102 marker so Production V4 cannot accept reconstructed
rows as timing-clean Forward evidence.

For each target date:
- target card/class data come from v2_race_entries;
- training outcomes are restricted by the frozen implementation to
  TRAIN_START <= race_date < TARGET_DATE;
- target-date outcomes are never queried;
- only complete six-lane payloads with >=4 matched opponents per lane persist;
- existing rows are preserved with ON CONFLICT DO NOTHING.

No schema change, no LINE, no purchase, no Production selector/model change.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research import _historical_opponent_adapter as adapter


HISTORICAL_MODEL_VERSION = 102
WRITE_CONFIRM = "YES"
MAX_BATCH_DAYS = 7


def date_range(start_date: str, end_date: str) -> list[date]:
    a = date.fromisoformat(start_date)
    b = date.fromisoformat(end_date)
    if b < a:
        raise ValueError("end before start")
    days = (b - a).days + 1
    if days > MAX_BATCH_DAYS:
        raise ValueError(f"maximum batch is {MAX_BATCH_DAYS} days")
    if a < adapter.TRAIN_START:
        raise ValueError(f"start must be >= {adapter.TRAIN_START}")
    return [a + timedelta(days=i) for i in range(days)]


def replay_day(
    conn: psycopg.Connection[Any],
    target: date,
    *,
    write_enabled: bool,
) -> dict[str, Any]:
    old_target = adapter.TARGET_DATE
    adapter.TARGET_DATE = target
    try:
        meta, entries = adapter.load_targets(conn)
        effects = adapter.load_effects(conn)
        counts: Counter[str] = Counter()
        counts["target_races"] = len(meta)
        counts["effect_cells"] = len(effects)

        payloads: dict[str, dict[str, list[Any]]] = {}
        for rid, rows in entries.items():
            lanes = {int(x["lane"]) for x in rows}
            if len(rows) != 6 or lanes != {1, 2, 3, 4, 5, 6}:
                counts["incomplete_card"] += 1
                continue
            try:
                p = adapter.score(rows, effects)
            except RuntimeError:
                counts["missing_baseline"] += 1
                continue
            if not all(int(x) >= adapter.MIN_MATCHED_OPPONENTS for x in p["matched_opponents"]):
                counts["insufficient_matches"] += 1
                continue
            payloads[rid] = p

        counts["complete_payloads"] = len(payloads)

        inserted = conflicts = 0
        if write_enabled and payloads:
            with conn.cursor() as cur:
                for rid, p in payloads.items():
                    m = meta[rid]
                    cur.execute(
                        """
                        insert into v2_opponent_pressure_shadow_v2
                          (race_id,race_date,venue_id,race_no,model_version,train_end,
                           racer_classes,matched_opponents,base_win,base_top3,
                           score_win,score_top3,adj_win,adj_top3,updated_at)
                        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                        on conflict (race_id) do nothing
                        """,
                        (
                            rid,
                            m["race_date"],
                            m["venue_id"],
                            m["race_no"],
                            HISTORICAL_MODEL_VERSION,
                            target - timedelta(days=1),
                            p["racer_classes"],
                            p["matched_opponents"],
                            p["base_win"],
                            p["base_top3"],
                            p["score_win"],
                            p["score_top3"],
                            p["adj_win"],
                            p["adj_top3"],
                        ),
                    )
                    if int(cur.rowcount or 0):
                        inserted += 1
                    else:
                        conflicts += 1
            conn.commit()
        else:
            conn.rollback()

        counts["inserted"] = inserted
        counts["conflicts_preserved"] = conflicts
        return {
            "target_date": target.isoformat(),
            "counts": dict(sorted(counts.items())),
        }
    finally:
        adapter.TARGET_DATE = old_target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_OPP_START_DATE"))
    ap.add_argument("--end-date", default=os.getenv("HIST_OPP_END_DATE"))
    ap.add_argument(
        "--output",
        default=os.getenv(
            "HIST_OPP_OUTPUT",
            "historical-opponent-replay-manifest.json",
        ),
    )
    args = ap.parse_args()
    if not args.start_date or not args.end_date:
        raise SystemExit("start/end required")

    dates = date_range(args.start_date, args.end_date)
    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_OPPONENT_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    print(f"HIST_OPP_MODEL_VERSION={HISTORICAL_MODEL_VERSION}", flush=True)
    print("HIST_OPP_TRAIN_POLICY=frozen_v2_strictly_before_target_date", flush=True)
    print("HIST_OPP_TARGET_OUTCOME_READ=0", flush=True)
    print("HIST_OPP_EXISTING_ROWS_OVERWRITE=0", flush=True)
    print("HIST_OPP_PRODUCTION_ACCEPTED_MODEL=0", flush=True)
    print("HIST_OPP_LINE=0 BUY=0 STAKE_CHANGE=0", flush=True)
    print(f"HIST_OPP_WRITE_ENABLED={int(write_enabled)}", flush=True)

    reports = []
    totals: Counter[str] = Counter()
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='180s'")
        for target in dates:
            report = replay_day(conn, target, write_enabled=write_enabled)
            reports.append(report)
            totals.update(report["counts"])
            print(
                "HIST_OPP_DAY=date:"
                + report["target_date"]
                + " "
                + " ".join(f"{k}:{v}" for k,v in report["counts"].items()),
                flush=True,
            )

    payload = {
        "contract": "HISTORICAL_OPPONENT_PRESSURE_REPLAY_V1",
        "model_version": HISTORICAL_MODEL_VERSION,
        "train_start": adapter.TRAIN_START.isoformat(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "target_outcome_read": False,
        "production_accepted_model": False,
        "write_enabled": write_enabled,
        "totals": dict(sorted(totals.items())),
        "days": reports,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("HIST_OPP_TOTALS=" + json.dumps(payload["totals"], sort_keys=True), flush=True)
    print("HIST_OPP_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
