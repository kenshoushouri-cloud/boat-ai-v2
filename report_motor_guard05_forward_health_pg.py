# -*- coding: utf-8 -*-
"""Read-only realized health report for v2_motor_guard05_forward_shadow.

Evaluates frozen BASE/FULL/GUARD05 120-ticket distributions against official
results. The collector is the only writer; this report never updates Shadow rows.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Tuple

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-25 motor-guard05-forward-health-v1"
START_DATE = date.fromisoformat(os.getenv("MOTOR_GUARD_FORWARD_REPORT_START_DATE", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
EPS = 1e-15
TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}


def _norm_ticket(v: Any) -> str:
    return str(v or "").strip()


def _new() -> Dict[str, float]:
    return {"n": 0.0, "ll": 0.0, "br": 0.0, "rk": 0.0}


def _add(s: Dict[str, float], probs: list[float], actual: str) -> None:
    idx = TICKET_INDEX[actual]
    p = max(float(probs[idx]), EPS)
    s["n"] += 1
    s["ll"] += -math.log(p)
    s["br"] += sum((float(x) - (1.0 if i == idx else 0.0)) ** 2 for i, x in enumerate(probs))
    s["rk"] += 1 + sum(1 for i, x in enumerate(probs) if float(x) > float(probs[idx]) or (float(x) == float(probs[idx]) and i < idx))


def _mean(s: Dict[str, float], key: str) -> float:
    return s[key] / s["n"] if s["n"] else 0.0


def _emit(scope: str, stats: Dict[str, Dict[str, float]]) -> None:
    full = stats["FULL"]
    for name in ("BASE", "FULL", "GUARD05"):
        s = stats[name]
        n = int(s["n"])
        if not n:
            print(f"MOTOR_GUARD_FORWARD_HEALTH_SCOPE={scope} model:{name} n:0", flush=True)
            continue
        ll = _mean(s, "ll"); br = _mean(s, "br"); rk = _mean(s, "rk")
        print(
            f"MOTOR_GUARD_FORWARD_HEALTH_SCOPE={scope} model:{name} n:{n} "
            f"ll:{ll:.8f} brier:{br:.8f} rank:{rk:.4f} "
            f"delta_ll_vs_full:{ll-_mean(full,'ll'):+.8f} "
            f"delta_brier_vs_full:{br-_mean(full,'br'):+.8f} "
            f"delta_rank_vs_full:{rk-_mean(full,'rk'):+.4f}",
            flush=True,
        )


def _load(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute("select to_regclass('public.v2_motor_guard05_forward_shadow') as reg")
        if cur.fetchone()["reg"] is None:
            return None
        cur.execute(
            """
            select s.race_id,s.race_date,s.venue_id,s.race_no,s.model_version,
                   s.count_mode,s.guard_max_prior,s.generation_start,s.deadline_at,
                   s.snapshot_at,s.prior_day_counts,s.guard_flags,
                   s.base_probs,s.full_probs,s.guard_probs,
                   r.result_status,r.race_status,r.trifecta_ticket
              from v2_motor_guard05_forward_shadow s
              left join v2_results r on r.race_id=s.race_id
             where s.race_date between %s and %s
             order by s.race_date,s.venue_id,s.race_no,s.race_id
            """,
            (START_DATE, END_DATE),
        )
        return [dict(x) for x in cur.fetchall()]


def main() -> None:
    print(f"MOTOR_GUARD_FORWARD_HEALTH_VERSION={VERSION}", flush=True)
    print(f"MOTOR_GUARD_FORWARD_HEALTH_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("MOTOR_GUARD_FORWARD_HEALTH_MODE=read_only_frozen_forward_no_updates_no_production_no_line", flush=True)
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = _load(conn)
    if rows is None:
        print("MOTOR_GUARD_FORWARD_HEALTH_TABLE=ABSENT", flush=True)
        print("MOTOR_GUARD_FORWARD_HEALTH_RESULT=PASS_NO_TABLE", flush=True)
        return

    overall = {m: _new() for m in ("BASE", "FULL", "GUARD05")}
    affected = {m: _new() for m in ("BASE", "FULL", "GUARD05")}
    by_date = defaultdict(lambda: {m: _new() for m in ("BASE", "FULL", "GUARD05")})
    invalid = pending = evaluated = affected_n = 0

    for r in rows:
        arrays = [r.get("base_probs"), r.get("full_probs"), r.get("guard_probs")]
        flags = r.get("guard_flags")
        prior_counts = r.get("prior_day_counts")
        valid_schema = (
            int(r.get("model_version") or 0) == 1
            and str(r.get("count_mode") or "") == "PRIOR_DAY"
            and int(r.get("guard_max_prior") or -1) == 5
            and isinstance(flags, list) and len(flags) == 6
            and isinstance(prior_counts, list) and len(prior_counts) == 6
            and all(isinstance(x, list) and len(x) == 120 for x in arrays)
            and r.get("snapshot_at") is not None and r.get("deadline_at") is not None
            and r["snapshot_at"] < r["deadline_at"]
        )
        if not valid_schema:
            invalid += 1
            continue
        official = (
            str(r.get("result_status") or "").lower() == "official"
            and str(r.get("race_status") or "").lower() == "official"
        )
        actual = _norm_ticket(r.get("trifecta_ticket"))
        if not official or actual not in TICKET_INDEX:
            pending += 1
            continue

        for probs in arrays:
            ssum = sum(float(x) for x in probs)
            if abs(ssum - 1.0) > 5e-5:
                invalid += 1
                break
        else:
            is_affected = any(bool(x) for x in flags)
            data = {"BASE": arrays[0], "FULL": arrays[1], "GUARD05": arrays[2]}
            for model, probs in data.items():
                _add(overall[model], probs, actual)
                _add(by_date[str(r["race_date"])][model], probs, actual)
                if is_affected:
                    _add(affected[model], probs, actual)
            evaluated += 1
            affected_n += int(is_affected)

    print(
        f"MOTOR_GUARD_FORWARD_HEALTH_COVERAGE=rows:{len(rows)} evaluated:{evaluated} pending:{pending} invalid:{invalid} affected_evaluated:{affected_n}",
        flush=True,
    )
    print("MOTOR_GUARD_FORWARD_HEALTH_SECTION=OVERALL", flush=True)
    _emit("OVERALL", overall)
    print("MOTOR_GUARD_FORWARD_HEALTH_SECTION=AFFECTED", flush=True)
    _emit("AFFECTED", affected)
    print("MOTOR_GUARD_FORWARD_HEALTH_SECTION=DATE", flush=True)
    for d in sorted(by_date):
        _emit(f"DATE:{d}", by_date[d])
    print("MOTOR_GUARD_FORWARD_HEALTH_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("MOTOR_GUARD_FORWARD_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MOTOR_GUARD_FORWARD_HEALTH_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
