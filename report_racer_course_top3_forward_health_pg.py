# -*- coding: utf-8 -*-
"""Read-only realized health report for v2_racer_course_top3_forward_shadow.

Evaluates the frozen BASE and COURSE(0.50) 120-ticket distributions against
subsequently official race outcomes. This report never changes Shadow rows.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Tuple

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-25 racer-course-top3-forward-health-v1"
START_DATE = date.fromisoformat(os.getenv("RACER_COURSE_FORWARD_REPORT_START_DATE", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
EPS = 1e-15
SOURCE_CUTOFF = time(8, 15)
TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}


def _aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def _new() -> Dict[str, float]:
    return {"n": 0.0, "ll": 0.0, "br": 0.0, "rk": 0.0, "t1": 0.0, "t3": 0.0, "t5": 0.0, "t10": 0.0}


def _add(stats: Dict[str, float], probs: list[float], actual: str) -> None:
    idx = TICKET_INDEX[actual]
    p = max(float(probs[idx]), EPS)
    target = float(probs[idx])
    rank = 1 + sum(1 for i, x in enumerate(probs) if float(x) > target or (float(x) == target and i < idx))
    stats["n"] += 1
    stats["ll"] += -math.log(p)
    stats["br"] += sum((float(x) - (1.0 if i == idx else 0.0)) ** 2 for i, x in enumerate(probs))
    stats["rk"] += rank
    stats["t1"] += int(rank <= 1)
    stats["t3"] += int(rank <= 3)
    stats["t5"] += int(rank <= 5)
    stats["t10"] += int(rank <= 10)


def _mean(stats: Dict[str, float], key: str) -> float:
    return stats[key] / stats["n"] if stats["n"] else 0.0


def _emit(scope: str, stats: Dict[str, Dict[str, float]]) -> None:
    base = stats["BASE"]
    for model in ("BASE", "COURSE"):
        s = stats[model]
        n = int(s["n"])
        if not n:
            print(f"RACER_COURSE_FORWARD_HEALTH_SCOPE={scope} model:{model} n:0", flush=True)
            continue
        ll = _mean(s, "ll"); br = _mean(s, "br"); rk = _mean(s, "rk")
        print(
            f"RACER_COURSE_FORWARD_HEALTH_SCOPE={scope} model:{model} n:{n} "
            f"ll:{ll:.8f} brier:{br:.8f} rank:{rk:.4f} "
            f"delta_ll_vs_base:{ll-_mean(base,'ll'):+.8f} "
            f"delta_brier_vs_base:{br-_mean(base,'br'):+.8f} "
            f"delta_rank_vs_base:{rk-_mean(base,'rk'):+.4f} "
            f"top1:{_mean(s,'t1')*100:.2f}% top3:{_mean(s,'t3')*100:.2f}% "
            f"top5:{_mean(s,'t5')*100:.2f}% top10:{_mean(s,'t10')*100:.2f}%",
            flush=True,
        )


def _load(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute("select to_regclass('public.v2_racer_course_top3_forward_shadow') as reg")
        if cur.fetchone()["reg"] is None:
            return None
        cur.execute(
            """
            select s.race_id,s.race_date,s.venue_id,s.race_no,s.model_version,
                   s.formula_version,s.ticket_order_version,s.course_coef,s.source_cutoff_jst,
                   s.deadline_at,s.snapshot_at,s.minutes_before,s.course_top3_rates,
                   s.course_snapshot_ats,s.base_probs,s.course_probs,
                   r.result_status,r.race_status,r.trifecta_ticket
              from v2_racer_course_top3_forward_shadow s
              left join v2_results r on r.race_id=s.race_id
             where s.race_date between %s and %s
             order by s.race_date,s.venue_id,s.race_no,s.race_id
            """,
            (START_DATE, END_DATE),
        )
        return [dict(x) for x in cur.fetchall()]


def _valid_source_times(row: Dict[str, Any]) -> bool:
    values = row.get("course_snapshot_ats")
    if not isinstance(values, list) or len(values) != 6:
        return False
    race_date = row.get("race_date")
    deadline = _aware_jst(row.get("deadline_at"))
    if race_date is None or deadline is None:
        return False
    for raw in values:
        dt = _aware_jst(raw)
        if dt is None or dt.date() != race_date or dt.time().replace(tzinfo=None) > SOURCE_CUTOFF or dt >= deadline:
            return False
    return True


def main() -> None:
    print(f"RACER_COURSE_FORWARD_HEALTH_VERSION={VERSION}", flush=True)
    print(f"RACER_COURSE_FORWARD_HEALTH_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("RACER_COURSE_FORWARD_HEALTH_MODE=read_only_frozen_forward_no_updates_no_production_no_line", flush=True)
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = _load(conn)
    if rows is None:
        print("RACER_COURSE_FORWARD_HEALTH_TABLE=ABSENT", flush=True)
        print("RACER_COURSE_FORWARD_HEALTH_RESULT=PASS_NO_TABLE", flush=True)
        return

    overall = {m: _new() for m in ("BASE", "COURSE")}
    by_date = defaultdict(lambda: {m: _new() for m in ("BASE", "COURSE")})
    invalid = pending = evaluated = 0

    for row in rows:
        base = row.get("base_probs")
        course = row.get("course_probs")
        rates = row.get("course_top3_rates")
        snapshot_at = _aware_jst(row.get("snapshot_at"))
        deadline = _aware_jst(row.get("deadline_at"))
        schema_ok = (
            int(row.get("model_version") or 0) == 1
            and abs(float(row.get("course_coef") or 0.0) - 0.50) < 1e-9
            and str(row.get("source_cutoff_jst") or "") == "08:15"
            and str(row.get("ticket_order_version") or "") == "lexicographic_lane_loop_120_fixed_v1"
            and isinstance(rates, list) and len(rates) == 6
            and all(0.0 <= float(x) <= 100.0 for x in rates)
            and isinstance(base, list) and len(base) == 120
            and isinstance(course, list) and len(course) == 120
            and snapshot_at is not None and deadline is not None and snapshot_at < deadline
            and float(row.get("minutes_before") or 0.0) >= 3.0
            and _valid_source_times(row)
            and abs(sum(float(x) for x in base) - 1.0) <= 5e-5
            and abs(sum(float(x) for x in course) - 1.0) <= 5e-5
        )
        if not schema_ok:
            invalid += 1
            continue

        official = (
            str(row.get("result_status") or "").lower() == "official"
            and str(row.get("race_status") or "").lower() == "official"
        )
        actual = str(row.get("trifecta_ticket") or "").strip()
        if not official or actual not in TICKET_INDEX:
            pending += 1
            continue
        _add(overall["BASE"], base, actual)
        _add(overall["COURSE"], course, actual)
        d = str(row["race_date"])
        _add(by_date[d]["BASE"], base, actual)
        _add(by_date[d]["COURSE"], course, actual)
        evaluated += 1

    print(
        f"RACER_COURSE_FORWARD_HEALTH_COVERAGE=rows:{len(rows)} evaluated:{evaluated} pending:{pending} invalid:{invalid}",
        flush=True,
    )
    print("RACER_COURSE_FORWARD_HEALTH_SECTION=OVERALL", flush=True)
    _emit("OVERALL", overall)
    print("RACER_COURSE_FORWARD_HEALTH_SECTION=DATE", flush=True)
    for d in sorted(by_date):
        _emit(f"DATE:{d}", by_date[d])
    print("RACER_COURSE_FORWARD_HEALTH_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_FORWARD_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RACER_COURSE_FORWARD_HEALTH_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
