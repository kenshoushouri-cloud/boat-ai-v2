# -*- coding: utf-8 -*-
"""Read-only S03_M2_POSITIVE_V1 audit using the common Forward economics contract."""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from research.forward_economics import forward_report

START = date.fromisoformat(os.getenv("S03_FORWARD_START", "2026-09-13"))
END = date.fromisoformat(os.getenv("S03_FORWARD_END", "2026-09-27"))
JST = ZoneInfo("Asia/Tokyo")
W = (1.0, 0.6, 0.3)

EXPECTED_20260926 = {
    "evaluated": 53,
    "hits": 4,
    "investment_yen": 5300,
    "return_yen": 10120,
    "profit_yen": 4820,
    "roi_pct": 190.9434,
    "largest_hit_yen": 4490,
    "largest_hit_share_pct": 44.3676,
}


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except Exception:
        return None


def jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def lanes(value: Any) -> tuple[int, int, int] | None:
    xs = [int(x) for x in re.findall(r"[1-6]", str(value or ""))]
    if len(xs) < 3 or len(set(xs[:3])) != 3:
        return None
    return xs[0], xs[1], xs[2]


def motor2_score(entries: list[dict[str, Any]], ticket: Any) -> float | None:
    ls = lanes(ticket)
    by = {si(e.get("lane")): e for e in entries}
    if ls is None or set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0.0 <= x <= 100.0:
            return None
        vals.append(x)
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    z = {i + 1: (vals[i] - mu) / sd for i in range(6)}
    a, b, c = ls
    return W[0] * z[a] + W[1] * z[b] + W[2] * z[c]


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("S03_M2_COMMON_POLICY=FROZEN_RULE_STRICT_PREDEADLINE_COMMON_ECON", flush=True)
    print("S03_M2_COMMON_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.ticket,s.snapshot_at,s.hit,s.return_yen,
                       s.payout_yen,s.investment_yen,s.evaluation_status,r.deadline_at
                  from v2_candidate_filter_shadow s
                  join v2_races r on r.race_id=s.race_id
                 where s.rule_id='S03'
                   and s.race_date between %s and %s
                 order by s.race_date,s.race_id
                """,
                (START, END),
            )
            rows = [dict(r) for r in cur.fetchall()]
            ids = sorted({str(r["race_id"]) for r in rows})
            entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                cur.execute(
                    """
                    select race_id,lane,motor_place2_rate
                      from v2_race_entries
                     where race_id=any(%s)
                     order by race_id,lane
                    """,
                    (ids,),
                )
                for row in cur.fetchall():
                    entries[str(row["race_id"])].append(dict(row))
        conn.rollback()

    positive = []
    timing_rejected = 0
    missing_motor = 0
    for row in rows:
        snap = jst(row.get("snapshot_at"))
        deadline = jst(row.get("deadline_at"))
        if snap is None or deadline is None or snap >= deadline:
            timing_rejected += 1
            continue
        score = motor2_score(entries.get(str(row["race_id"]), []), row.get("ticket"))
        if score is None:
            missing_motor += 1
            continue
        if score > 0.0:
            x = dict(row)
            x["motor2_score"] = score
            positive.append(x)

    report = forward_report(
        positive,
        unit_yen=100,
        bootstrap_samples=20_000,
        bootstrap_seed=20260927,
    )

    overall = report["overall"]
    exact_baseline = START == date(2026, 9, 13) and END == date(2026, 9, 26)
    if exact_baseline:
        for key, expected in EXPECTED_20260926.items():
            if overall[key] != expected:
                raise RuntimeError(
                    f"S03_M2 common parity failed {key}: {overall[key]} != {expected}"
                )

        if report["risk"]["max_drawdown_yen"] != 1600:
            raise RuntimeError("unexpected max drawdown")
        if report["risk"]["max_losing_streak"] != 16:
            raise RuntimeError("unexpected max losing streak")
        if report["chronological_halves"]["first"]["roi_pct"] != 319.6154:
            raise RuntimeError("unexpected first-half ROI")
        if report["chronological_halves"]["second"]["roi_pct"] != 67.037:
            raise RuntimeError("unexpected second-half ROI")
        if report["day_bootstrap"]["p_roi_gt_100_pct"] != 86.13:
            raise RuntimeError("unexpected bootstrap probability")

    print(
        "S03_M2_COMMON_INPUT="
        + json.dumps(
            {
                "source_s03_rows": len(rows),
                "timing_rejected": timing_rejected,
                "missing_motor": missing_motor,
                "positive_rows": len(positive),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    print("S03_M2_COMMON_COVERAGE=" + json.dumps(report["coverage"], sort_keys=True), flush=True)
    print("S03_M2_COMMON_OVERALL=" + json.dumps(overall, sort_keys=True), flush=True)
    print("S03_M2_COMMON_RISK=" + json.dumps(report["risk"], sort_keys=True), flush=True)
    print("S03_M2_COMMON_HALVES=" + json.dumps(report["chronological_halves"], sort_keys=True), flush=True)
    print("S03_M2_COMMON_BOOTSTRAP=" + json.dumps(report["day_bootstrap"], sort_keys=True), flush=True)
    print(f"S03_M2_COMMON_PERIOD={START.isoformat()}..{END.isoformat()}", flush=True)
    print(f"S03_M2_COMMON_REMAINING_TO_100={max(0, 100 - int(overall['evaluated']))}", flush=True)
    print(
        "S03_M2_COMMON_RESULT="
        + ("PASS_EXACT_FROZEN_SUBSET" if exact_baseline else "PASS_READ_ONLY_CHECKPOINT"),
        flush=True,
    )


if __name__ == "__main__":
    main()
