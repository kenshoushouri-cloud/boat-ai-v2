# -*- coding: utf-8 -*-
"""Read-only realized-result Forward report for Bao.

Uses the exact probability transformations from bao_paired_forward_audit.py and
summarizes realized outcome log-loss deltas overall, by race date, and by venue.
This is diagnostic evidence only; it never promotes or changes Production logic.
"""
from __future__ import annotations

import os
import runpy
from collections import defaultdict
from pathlib import Path
from statistics import median

import psycopg
from psycopg.rows import dict_row

DB = (os.getenv("DATABASE_URL") or "").strip()
MIN_RESULTS = int(os.getenv("BAO_FORMAL_MIN_RESULTS", "30"))
AUDIT = runpy.run_path(str(Path(__file__).with_name("bao_paired_forward_audit.py")))
LANES = AUDIT["LANES"]


def _summary(rows: list[dict], metric: str) -> str:
    values = [float(row[metric]) for row in rows if row.get(metric) is not None]
    if not values:
        return "ready:0 improved:0/0 avg_delta:na median_delta:na"
    improved = sum(1 for value in values if value < 0)
    return (
        f"ready:{len(values)} improved:{improved}/{len(values)} "
        f"avg_delta:{sum(values)/len(values):.6f} "
        f"median_delta:{median(values):.6f}"
    )


def _group_lines(prefix: str, rows: list[dict], key: str, metric: str) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get(metric) is not None:
            grouped[str(row.get(key) or "unknown")].append(row)
    for value in sorted(grouped):
        print(
            f"{prefix}={key}:{value} {_summary(grouped[value], metric)}",
            flush=True,
        )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    print("BAO_FORMAL_MODE=read_only_realized_forward", flush=True)
    print(f"BAO_FORMAL_MIN_RESULTS={MIN_RESULTS}", flush=True)
    print("BAO_FORMAL_POLICY=no_writes_no_production_no_line_manual_review_only", flush=True)

    devig = AUDIT["devig"]
    sf = AUDIT["sf"]
    zscore = AUDIT["zscore"]
    ticket_scores = AUDIT["ticket_scores"]
    adjusted = AUDIT["adjusted"]
    frozen_exhibition_scores = AUDIT["frozen_exhibition_scores"]
    exhibition_timing_reason = AUDIT["exhibition_timing_reason"]
    outcome_logloss = AUDIT["outcome_logloss"]
    nt = AUDIT["nt"]
    motor_beta = AUDIT["MOTOR_BETA"]
    ex_beta = AUDIT["EX_TIME_BETA"]

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        pairs, _ = AUDIT["load_pairs"](conn)
        race_ids = [str(row["race_id"]) for row in pairs]
        entries_by: dict[str, list[dict]] = defaultdict(list)
        results: dict[str, str] = {}
        if race_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """select race_id,lane,motor_place2_rate
                       from v2_race_entries
                       where race_id = any(%s)
                       order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries_by[str(row["race_id"])].append(dict(row))
                cur.execute(
                    """select race_id,trifecta_ticket
                       from v2_results
                       where race_id = any(%s)""",
                    (race_ids,),
                )
                results = {
                    str(row["race_id"]): nt(row["trifecta_ticket"])
                    for row in cur.fetchall()
                }

    realized: list[dict] = []
    for row in pairs:
        rid = str(row["race_id"])
        actual = results.get(rid, "")
        qe = devig(row.get("early_odds"))
        ql = devig(row.get("late_odds"))
        if qe is None or ql is None or actual not in qe:
            continue

        by = {int(entry.get("lane") or 0): entry for entry in entries_by.get(rid, [])}
        if set(by) != LANES:
            continue
        vals = []
        for lane in range(1, 7):
            value = sf(by[lane].get("motor_place2_rate"))
            if value is None or not (0 <= value <= 100):
                vals = []
                break
            vals.append(value)
        motor_z = zscore(vals) if vals else None
        if motor_z is None:
            continue
        motor_score = ticket_scores(motor_z)
        qm = adjusted(qe, [motor_score], [motor_beta])

        rec = {
            "race_id": rid,
            "race_date": str(row.get("race_date") or ""),
            "venue_id": str(row.get("venue_id") or "").zfill(2),
            "motor_delta": outcome_logloss(qm, actual) - outcome_logloss(qe, actual),
            "exhibition_delta": None,
            "late_vs_early": outcome_logloss(ql, actual) - outcome_logloss(qe, actual),
        }

        if exhibition_timing_reason(row) == "ok":
            ex_score, reason = frozen_exhibition_scores(row.get("mid_exhibition_ranks"))
            if ex_score is not None and reason == "ok":
                qj = adjusted(qe, [motor_score, ex_score], [motor_beta, ex_beta])
                rec["exhibition_delta"] = (
                    outcome_logloss(qj, actual) - outcome_logloss(qm, actual)
                )
        realized.append(rec)

    motor_rows = [row for row in realized if row.get("motor_delta") is not None]
    ex_rows = [row for row in realized if row.get("exhibition_delta") is not None]

    print(f"BAO_FORMAL_MOTOR_OVERALL={_summary(motor_rows, 'motor_delta')}", flush=True)
    print(f"BAO_FORMAL_EXHIBITION_OVERALL={_summary(ex_rows, 'exhibition_delta')}", flush=True)
    print(f"BAO_FORMAL_LATE_REFERENCE={_summary(motor_rows, 'late_vs_early')}", flush=True)

    _group_lines("BAO_FORMAL_MOTOR_BY_DATE", motor_rows, "race_date", "motor_delta")
    _group_lines("BAO_FORMAL_MOTOR_BY_VENUE", motor_rows, "venue_id", "motor_delta")
    _group_lines("BAO_FORMAL_EXHIBITION_BY_DATE", ex_rows, "race_date", "exhibition_delta")
    _group_lines("BAO_FORMAL_EXHIBITION_BY_VENUE", ex_rows, "venue_id", "exhibition_delta")

    motor_ready = len(motor_rows) >= MIN_RESULTS
    ex_ready = len(ex_rows) >= MIN_RESULTS
    print(
        "BAO_FORMAL_MOTOR_SAMPLE_GATE="
        + ("READY_FOR_MANUAL_REVIEW" if motor_ready else "BLOCKED_INSUFFICIENT_RESULTS")
        + f" count:{len(motor_rows)}/{MIN_RESULTS}",
        flush=True,
    )
    print(
        "BAO_FORMAL_EXHIBITION_SAMPLE_GATE="
        + ("READY_FOR_MANUAL_REVIEW" if ex_ready else "BLOCKED_INSUFFICIENT_RESULTS")
        + f" count:{len(ex_rows)}/{MIN_RESULTS}",
        flush=True,
    )
    print("BAO_FORMAL_AUTO_PROMOTION=DISABLED", flush=True)
    print("BAO_FORMAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
