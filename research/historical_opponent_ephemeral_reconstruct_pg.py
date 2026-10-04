# -*- coding: utf-8 -*-
"""Ephemeral historical Opponent reconstruction for matched-contract backtest.

This script never writes PostgreSQL. It recomputes the frozen Opponent Pressure
v2 math from strictly prior data and serializes backtest-only rows to a local
JSON artifact. Existing v2/model_version=2 rows remain untouched.
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


CONTRACT = "HISTORICAL_OPPONENT_EPHEMERAL_RECONSTRUCT_V1"
SOURCE_MODEL_VERSION = 102
MAX_DAYS = 10


def date_range(start_date: str, end_date: str) -> list[date]:
    a = date.fromisoformat(start_date)
    b = date.fromisoformat(end_date)
    if b < a:
        raise ValueError("end before start")
    days = (b - a).days + 1
    if days > MAX_DAYS:
        raise ValueError(f"maximum ephemeral range is {MAX_DAYS} days")
    if a < adapter.TRAIN_START:
        raise ValueError(f"start must be >= {adapter.TRAIN_START}")
    return [a + timedelta(days=i) for i in range(days)]


def reconstruct_day(
    conn: psycopg.Connection[Any],
    target: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    old_target = adapter.TARGET_DATE
    adapter.TARGET_DATE = target
    try:
        meta, entries = adapter.load_targets(conn)
        effects = adapter.load_effects(conn)
        counts: Counter[str] = Counter()
        counts["target_races"] = len(meta)
        counts["effect_cells"] = len(effects)

        rows: list[dict[str, Any]] = []
        for rid, card in sorted(entries.items()):
            lanes = {int(x["lane"]) for x in card}
            if len(card) != 6 or lanes != {1, 2, 3, 4, 5, 6}:
                counts["incomplete_card"] += 1
                continue
            try:
                p = adapter.score(card, effects)
            except RuntimeError:
                counts["missing_baseline"] += 1
                continue
            if not all(int(x) >= adapter.MIN_MATCHED_OPPONENTS for x in p["matched_opponents"]):
                counts["insufficient_matches"] += 1
                continue

            m = meta[rid]
            base = [float(x) for x in p["base_win"]]
            adj = [float(x) for x in p["adj_win"]]
            rows.append(
                {
                    "race_id": rid,
                    "race_date": target.isoformat(),
                    "venue_id": str(m["venue_id"]),
                    "race_no": int(m["race_no"]),
                    "source_model_version": SOURCE_MODEL_VERSION,
                    "train_end": (target - timedelta(days=1)).isoformat(),
                    "racer_classes": [int(x) for x in p["racer_classes"]],
                    "matched_opponents": [int(x) for x in p["matched_opponents"]],
                    "base_win": base,
                    "adj_win": adj,
                    "opponent_delta": [
                        round(adj[i] - base[i], 6)
                        for i in range(6)
                    ],
                    "provenance": "ephemeral_historical102_strict_prior_only",
                }
            )

        counts["reconstructed"] = len(rows)
        conn.rollback()
        return (
            {
                "target_date": target.isoformat(),
                "counts": dict(sorted(counts.items())),
            },
            rows,
        )
    finally:
        adapter.TARGET_DATE = old_target


def reconstruct(start_date: str, end_date: str) -> dict[str, Any]:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    days = date_range(start_date, end_date)
    reports: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='180s'")

        for target in days:
            report, day_rows = reconstruct_day(conn, target)
            reports.append(report)
            rows.extend(day_rows)
            totals.update(report["counts"])
            print(
                "OPP_EPHEMERAL_DAY="
                + json.dumps(report, sort_keys=True),
                flush=True,
            )

    race_ids = [str(x["race_id"]) for x in rows]
    if len(race_ids) != len(set(race_ids)):
        raise RuntimeError("duplicate reconstructed race_id")

    return {
        "contract": CONTRACT,
        "source_model_version": SOURCE_MODEL_VERSION,
        "period": [start_date, end_date],
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "target_outcome_read": False,
        "database_write": False,
        "existing_rows_changed": False,
        "production_change": False,
        "days": reports,
        "totals": dict(sorted(totals.items())),
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument(
        "--output",
        default="historical-opponent-ephemeral-reconstruct.json",
    )
    ap.add_argument("--expect-races", type=int)
    args = ap.parse_args()

    print("OPP_EPHEMERAL_DB_WRITE=0", flush=True)
    print("OPP_EPHEMERAL_EXISTING_ROWS_CHANGED=0", flush=True)
    print("OPP_EPHEMERAL_TARGET_OUTCOME_READ=0", flush=True)
    print("OPP_EPHEMERAL_PRODUCTION_CHANGE=0", flush=True)

    payload = reconstruct(args.start_date, args.end_date)
    reconstructed = int(payload["totals"].get("reconstructed", 0))
    if args.expect_races is not None and reconstructed != args.expect_races:
        raise RuntimeError(
            f"expected {args.expect_races} reconstructed races, got {reconstructed}"
        )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print(
        "OPP_EPHEMERAL_TOTALS="
        + json.dumps(payload["totals"], sort_keys=True),
        flush=True,
    )
    print(f"OPP_EPHEMERAL_RECONSTRUCTED={reconstructed}", flush=True)
    print("OPP_EPHEMERAL_RESULT=PASS_READ_ONLY_ARTIFACT", flush=True)


if __name__ == "__main__":
    main()
