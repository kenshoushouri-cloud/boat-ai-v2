# -*- coding: utf-8 -*-
"""Read-only reason breakdown for combined Forward integrity exclusions."""
from __future__ import annotations

import math
import os
from collections import Counter, defaultdict

import psycopg
from psycopg.rows import dict_row

import course_opponent_combined_forward as combo


def opp_reason(row):
    if int(row.get("opp_model_version") or 0) != 2:
        return "model_version"
    race_date = row.get("race_date")
    if race_date is None or row.get("train_end") is None or row.get("train_end") >= race_date:
        return "train_end"
    deadline = combo.aware_jst(row.get("deadline_at"))
    created = combo.aware_jst(row.get("opp_created_at"))
    if deadline is None or created is None:
        return "missing_time"
    if created.date() != race_date:
        return "created_wrong_date"
    if created >= deadline:
        return "created_at_or_after_deadline"
    matched = row.get("matched_opponents")
    if not isinstance(matched, list) or len(matched) != 6:
        return "matched_shape"
    try:
        if any(int(x) < 4 for x in matched):
            return "matched_lt4"
    except Exception:
        return "matched_value"
    base_win = row.get("base_win"); adj_win = row.get("adj_win")
    if not isinstance(base_win, list) or len(base_win) != 6 or not isinstance(adj_win, list) or len(adj_win) != 6:
        return "prob_shape"
    try:
        if any(not math.isfinite(float(x)) or not (0.0 < float(x) < 1.0) for x in base_win + adj_win):
            return "prob_value"
    except Exception:
        return "prob_value"
    return "unknown"


def main():
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        rows = combo.load_rows(conn)
        conn.rollback()
    reasons = Counter()
    by_date = defaultdict(Counter)
    for row in rows:
        if combo.course_integrity(row) and not combo.opponent_integrity(row):
            reason = opp_reason(row)
            reasons[reason] += 1
            by_date[str(row.get("race_date"))][reason] += 1
    print(f"COURSE_OPP_INTEGRITY_JOINED={len(rows)}", flush=True)
    print(f"COURSE_OPP_INTEGRITY_INVALID_OPP={sum(reasons.values())}", flush=True)
    for reason in sorted(reasons):
        print(f"COURSE_OPP_INTEGRITY_REASON={reason}:{reasons[reason]}", flush=True)
    for d in sorted(by_date):
        parts = ",".join(f"{k}:{v}" for k, v in sorted(by_date[d].items()))
        print(f"COURSE_OPP_INTEGRITY_DATE={d} {parts}", flush=True)
    print("COURSE_OPP_INTEGRITY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
