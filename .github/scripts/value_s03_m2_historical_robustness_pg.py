# -*- coding: utf-8 -*-
"""Read-only historical robustness audit for frozen S03_M2_POSITIVE_V1.

The rule is already frozen prospectively. This script does NOT tune its source
population, score, weights, beta, threshold, or stake. It uses all available
pre-freeze S03 PRE-shadow rows before 2026-09-13 and reports robustness only.

No DB writes / Railway mutation / LINE / BUY / Production behavior changes.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

CONTRACT = "S03_M2_POSITIVE_V1"
FREEZE_DATE = date(2026, 9, 13)
END_DATE = date(2026, 9, 12)
POS_W = (1.0, 0.6, 0.3)
BETA = 0.06
SCORE_BOUNDARY = 0.0
UNIT_YEN = 100
BOOTSTRAP_SAMPLES = 20000
BOOTSTRAP_SEED = 20260927
OUTPUT = Path(os.getenv("VALUE_S03_M2_HIST_OUTPUT", "value-s03-m2-historical-robustness.json"))

FROZEN_CONFIG = {
    "contract": CONTRACT,
    "freeze_date": FREEZE_DATE.isoformat(),
    "source_rule_id": "S03",
    "feature": "motor_place2_rate",
    "position_weights": list(POS_W),
    "beta": BETA,
    "score_operator": ">",
    "score_boundary": SCORE_BOUNDARY,
    "unit_yen": UNIT_YEN,
}


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any, default: float | None = None) -> float | None:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def aware_jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    return value.astimezone(ZoneInfo("Asia/Tokyo"))


def ticket_lanes(value: Any) -> tuple[int, int, int] | None:
    xs = [int(x) for x in re.findall(r"[1-6]", str(value or ""))]
    if len(xs) < 3 or len(set(xs[:3])) != 3:
        return None
    return xs[0], xs[1], xs[2]


def score_for(entries: list[dict[str, Any]], ticket: Any) -> float | None:
    lanes = ticket_lanes(ticket)
    if lanes is None:
        return None
    by = {si(e.get("lane")): e for e in entries}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals: list[float] = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0.0 <= x <= 100.0:
            return None
        vals.append(float(x))
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    z = {lane: (vals[lane - 1] - mu) / sd for lane in range(1, 7)}
    a, b, c = lanes
    return POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]


def settled(row: dict[str, Any]) -> bool:
    return row.get("hit") is not None and row.get("return_yen") is not None


def max_drawdown_and_losing_streak(rows: list[dict[str, Any]]) -> tuple[int, int]:
    running = 0
    peak = 0
    max_dd = 0
    losing = 0
    max_losing = 0
    for row in rows:
        ret = si(row.get("return_yen"), 0) if bool(row.get("hit")) else 0
        running += ret - UNIT_YEN
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        if ret > 0:
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
    return max_dd, max_losing


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rr = [r for r in rows if settled(r)]
    rr.sort(key=lambda r: (str(r["race_date"]), str(r["race_id"])))
    invested = len(rr) * UNIT_YEN
    gross = sum(si(r.get("return_yen"), 0) if bool(r.get("hit")) else 0 for r in rr)
    hits = sum(int(bool(r.get("hit"))) for r in rr)
    hit_returns = sorted(
        [si(r.get("return_yen"), 0) for r in rr if bool(r.get("hit"))],
        reverse=True,
    )
    max_dd, max_losing = max_drawdown_and_losing_streak(rr)
    return {
        "evaluated": len(rr),
        "hits": hits,
        "hit_rate_pct": round(hits / len(rr) * 100.0, 4) if rr else None,
        "investment_yen": invested,
        "return_yen": gross,
        "profit_yen": gross - invested,
        "roi_pct": round(gross / invested * 100.0, 4) if invested else None,
        "largest_hit_yen": hit_returns[0] if hit_returns else 0,
        "largest_hit_share_pct": round(hit_returns[0] / gross * 100.0, 4) if hit_returns and gross else 0.0,
        "max_drawdown_yen": max_dd,
        "max_losing_streak": max_losing,
    }


def chronological_blocks(rows: list[dict[str, Any]], n: int = 4) -> list[dict[str, Any]]:
    days = sorted({str(r["race_date"]) for r in rows if settled(r)})
    if not days:
        return []
    n = min(n, len(days))
    base, extra = divmod(len(days), n)
    out = []
    pos = 0
    for idx in range(n):
        size = base + (1 if idx < extra else 0)
        block_days = set(days[pos:pos + size])
        pos += size
        rr = [r for r in rows if str(r["race_date"]) in block_days and settled(r)]
        s = summary(rr)
        out.append({
            "block": idx + 1,
            "start_date": min(block_days),
            "end_date": max(block_days),
            "days": len(block_days),
            **s,
        })
    return out


def monthly(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if settled(row):
            by[str(row["race_date"])[:7]].append(row)
    return [{"month": m, **summary(rr)} for m, rr in sorted(by.items())]


def day_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if settled(row):
            by[str(row["race_date"])].append(row)
    days = sorted(by)
    if not days:
        return {"samples": 0, "p_roi_gt_100_pct": None, "ci95_roi_pct": [None, None]}
    rnd = random.Random(BOOTSTRAP_SEED)
    rois: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        invest = gross = 0
        for _j in days:
            d = days[rnd.randrange(len(days))]
            for row in by[d]:
                invest += UNIT_YEN
                if bool(row.get("hit")):
                    gross += si(row.get("return_yen"), 0)
        rois.append(gross / invest * 100.0 if invest else 0.0)
    rois.sort()
    n = len(rois)
    return {
        "samples": n,
        "seed": BOOTSTRAP_SEED,
        "median_roi_pct": round(rois[n // 2], 4),
        "ci95_roi_pct": [
            round(rois[int(0.025 * (n - 1))], 4),
            round(rois[int(0.975 * (n - 1))], 4),
        ],
        "p_roi_gt_100_pct": round(sum(x > 100.0 for x in rois) / n * 100.0, 4),
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"S03_M2_HIST_CONTRACT={CONTRACT}", flush=True)
    print(f"S03_M2_HIST_PRE_FREEZE_END={END_DATE}", flush=True)
    print("S03_M2_HIST_POLICY=ALL_AVAILABLE_PRE_FREEZE_S03_NO_RETUNE", flush=True)
    print("S03_M2_HIST_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    shadow: list[dict[str, Any]] = []
    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    deadlines: dict[str, datetime] = {}

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute(
                """select s.race_id,s.race_date,s.rule_id,s.ticket,s.snapshot_at,
                          s.hit,s.return_yen,s.evaluated_at,r.deadline_at
                     from v2_candidate_filter_shadow s
                     join v2_races r on r.race_id=s.race_id
                    where s.rule_id='S03'
                      and s.race_date < %s
                    order by s.race_date,s.race_id""",
                (FREEZE_DATE,),
            )
            shadow = [dict(r) for r in cur.fetchall()]
            race_ids = sorted({str(r["race_id"]) for r in shadow})
            if race_ids:
                cur.execute(
                    """select race_id,lane,motor_place2_rate
                         from v2_race_entries
                        where race_id=any(%s)
                        order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries[str(row["race_id"])].append(dict(row))
        conn.rollback()

    timing_valid: list[dict[str, Any]] = []
    invalid_timing = 0
    missing_motor = 0
    eligible: list[dict[str, Any]] = []
    complement: list[dict[str, Any]] = []

    for row in shadow:
        snap = aware_jst(row.get("snapshot_at"))
        deadline = aware_jst(row.get("deadline_at"))
        if snap is None or deadline is None or snap >= deadline:
            invalid_timing += 1
            continue
        timing_valid.append(row)
        score = score_for(entries.get(str(row["race_id"]), []), row.get("ticket"))
        if score is None:
            missing_motor += 1
            continue
        x = dict(row)
        x["motor2_score"] = score
        x["motor2_factor"] = math.exp(BETA * score)
        if score > SCORE_BOUNDARY:
            eligible.append(x)
        else:
            complement.append(x)

    eligible_eval = [r for r in eligible if settled(r)]
    complement_eval = [r for r in complement if settled(r)]
    all_eval = [r for r in timing_valid if settled(r)]

    result = {
        "contract": "s03_m2_positive_v1_historical_robustness_v1",
        "frozen_config": FROZEN_CONFIG,
        "period": {
            "selection": "all_available_pre_freeze_S03",
            "latest_allowed_date": END_DATE.isoformat(),
            "observed_first_date": min((str(r["race_date"]) for r in shadow), default=None),
            "observed_last_date": max((str(r["race_date"]) for r in shadow), default=None),
        },
        "coverage": {
            "source_s03_rows": len(shadow),
            "timing_valid_pre_deadline_rows": len(timing_valid),
            "invalid_timing_rows": invalid_timing,
            "missing_motor_rows": missing_motor,
            "eligible_positive_rows": len(eligible),
            "complement_nonpositive_rows": len(complement),
            "eligible_evaluated": len(eligible_eval),
            "complement_evaluated": len(complement_eval),
            "all_s03_evaluated": len(all_eval),
        },
        "eligible_positive": {
            "overall": summary(eligible),
            "monthly": monthly(eligible),
            "chronological_blocks": chronological_blocks(eligible, 4),
            "day_bootstrap": day_bootstrap(eligible),
        },
        "nonpositive_complement": {
            "overall": summary(complement),
        },
        "all_timing_valid_s03": {
            "overall": summary(timing_valid),
        },
        "safety": {
            "fixed_rule_no_retune": True,
            "all_available_pre_freeze_source": True,
            "timing_requires_snapshot_before_deadline": True,
            "db_write": False,
            "line": False,
            "buy": False,
            "production_change": False,
            "promotion_allowed": False,
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    s = result["eligible_positive"]["overall"]
    b = result["eligible_positive"]["day_bootstrap"]
    print("S03_M2_HIST_COVERAGE=" + json.dumps(result["coverage"], sort_keys=True), flush=True)
    print(
        "S03_M2_HIST_ELIGIBLE="
        f"evaluated:{s['evaluated']} hits:{s['hits']} roi:{s['roi_pct']} "
        f"profit:{s['profit_yen']} largest_hit_share:{s['largest_hit_share_pct']} "
        f"max_dd:{s['max_drawdown_yen']} max_losing:{s['max_losing_streak']}",
        flush=True,
    )
    print(
        "S03_M2_HIST_BOOTSTRAP="
        f"median_roi:{b['median_roi_pct']} ci95:{b['ci95_roi_pct']} "
        f"p_roi_gt_100:{b['p_roi_gt_100_pct']}",
        flush=True,
    )
    print("S03_M2_HIST_PROMOTION_ALLOWED=0", flush=True)
    print("S03_M2_HIST_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
