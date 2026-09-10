# -*- coding: utf-8 -*-
"""Deterministic paired bootstrap for Racer Course Top3 Forward Shadow.

Research-only, read-only robustness check. Reuses the same frozen validation
rules and evaluates per-race COURSE-minus-BASE deltas for LogLoss, Brier and
rank. No database writes and no production promotion.
"""
from __future__ import annotations

import math
import os
import random
from typing import Any

import psycopg
from psycopg.rows import dict_row

import report_racer_course_top3_forward_health_pg as rpt
from research_racer_course_top3_venue_health_pg import _valid

SEED = 20260910
REPS = 5000


def _per_race_delta(base: list[float], course: list[float], actual: str) -> tuple[float, float, float]:
    idx = rpt.TICKET_INDEX[actual]
    pb = max(float(base[idx]), rpt.EPS)
    pc = max(float(course[idx]), rpt.EPS)
    ll = -math.log(pc) - (-math.log(pb))
    brier_base = sum((float(x) - (1.0 if i == idx else 0.0)) ** 2 for i, x in enumerate(base))
    brier_course = sum((float(x) - (1.0 if i == idx else 0.0)) ** 2 for i, x in enumerate(course))
    target_b = float(base[idx])
    target_c = float(course[idx])
    rank_b = 1 + sum(1 for i, x in enumerate(base) if float(x) > target_b or (float(x) == target_b and i < idx))
    rank_c = 1 + sum(1 for i, x in enumerate(course) if float(x) > target_c or (float(x) == target_c and i < idx))
    return ll, brier_course - brier_base, float(rank_c - rank_b)


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def main() -> None:
    print("RACER_COURSE_BOOTSTRAP_MODE=read_only_paired_bootstrap_no_updates_no_production_no_line", flush=True)
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = rpt._load(conn)
    if rows is None:
        print("RACER_COURSE_BOOTSTRAP_RESULT=PASS_NO_TABLE", flush=True)
        return

    diffs: list[tuple[float, float, float]] = []
    invalid = pending = 0
    for row in rows:
        if not _valid(row):
            invalid += 1
            continue
        official = (
            str(row.get("result_status") or "").lower() == "official"
            and str(row.get("race_status") or "").lower() == "official"
        )
        actual = str(row.get("trifecta_ticket") or "").strip()
        if not official or actual not in rpt.TICKET_INDEX:
            pending += 1
            continue
        diffs.append(_per_race_delta(row["base_probs"], row["course_probs"], actual))

    n = len(diffs)
    if n == 0:
        raise RuntimeError("no evaluated rows")
    means = tuple(sum(d[j] for d in diffs) / n for j in range(3))

    rng = random.Random(SEED)
    boot = [[], [], []]
    for _ in range(REPS):
        sums = [0.0, 0.0, 0.0]
        for _ in range(n):
            d = diffs[rng.randrange(n)]
            sums[0] += d[0]
            sums[1] += d[1]
            sums[2] += d[2]
        for j in range(3):
            boot[j].append(sums[j] / n)

    names = ("LL", "BRIER", "RANK")
    print(
        f"RACER_COURSE_BOOTSTRAP_COVERAGE=rows:{len(rows)} evaluated:{n} pending:{pending} invalid:{invalid} reps:{REPS} seed:{SEED}",
        flush=True,
    )
    for j, name in enumerate(names):
        values = sorted(boot[j])
        lo = _quantile(values, 0.025)
        hi = _quantile(values, 0.975)
        nonnegative = sum(1 for x in values if x >= 0.0) / REPS
        print(
            f"RACER_COURSE_BOOTSTRAP_METRIC={name} mean_delta:{means[j]:+.8f} "
            f"ci95:[{lo:+.8f},{hi:+.8f}] bootstrap_nonnegative:{nonnegative:.6f}",
            flush=True,
        )

    print("RACER_COURSE_BOOTSTRAP_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_BOOTSTRAP_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RACER_COURSE_BOOTSTRAP_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",
            flush=True,
        )
        raise
