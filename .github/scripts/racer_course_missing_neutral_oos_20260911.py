# -*- coding: utf-8 -*-
"""Pre-registered read-only OOS evaluation of Course missing-row neutral fallback.

Frozen plan: docs/RACER_COURSE_MISSING_NEUTRAL_OOS_PLAN_20260911.md
Preregistration commit: 908462848b73440359fd239d8f75dc2fa8d3a009

No coefficient search. Course coefficient is fixed at 0.50. Timing-safe observed
Course Top3 values are z-scored among observed lanes only; missing/unusable lanes
receive z=0 (BASE raw strength unchanged). Outcomes are read only after feature
eligibility is determined. No odds, payout, ROI, writes, Production, LINE, or
purchase behavior is used or changed.
"""
from __future__ import annotations

import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v24_pre_candidate_notifier_pg as v24

DB = os.getenv("DATABASE_URL", "").strip()
JST = ZoneInfo("Asia/Tokyo")
START = date(2026, 7, 15)
END = date(2026, 9, 10)
MORNING_CUTOFF = time(8, 15)
COURSE_COEF = 0.50
EPS = 1e-15
BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 20260911
MIN_MISSING_RACES = 200
MIN_MISSING_DATES = 10


def sf(v: Any, default: float | None = None) -> float | None:
    try:
        if v in (None, ""):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def norm_ticket(v: Any) -> str:
    xs = re.findall(r"[1-6]", str(v or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def local_dt(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        return None
    return v.astimezone(JST)


def clean_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lane": r.get("lane"),
            "racer_class": r.get("racer_class"),
            "national_win_rate": r.get("national_win_rate"),
            "national_place2_rate": r.get("national_place2_rate"),
            "local_place2_rate": r.get("local_place2_rate"),
            "avg_st": r.get("avg_st"),
        }
        for r in rows
    ]


def ticket_probs_from_raw(raw: dict[int, float]) -> dict[str, float] | None:
    if sorted(raw) != [1, 2, 3, 4, 5, 6]:
        return None
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        return None
    out: dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        rem_b = total - weights[a]
        if rem_b <= 0:
            return None
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / rem_b
            rem_c = rem_b - weights[b]
            if rem_c <= 0:
                return None
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / rem_c)
    z = sum(out.values())
    if len(out) != 120 or z <= 0:
        return None
    return {ticket: p / z for ticket, p in out.items()}


def base_raw(rows: list[dict[str, Any]], venue: str) -> dict[int, float] | None:
    by = v24._entry_by_lane(clean_entries(rows))
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None
    try:
        return {lane: v24._lane_raw_strength(by[lane], lane, venue) for lane in range(1, 7)}
    except Exception:
        return None


def safe_course_value(row: dict[str, Any]) -> float | None:
    if row.get("snapshot_racer_number") is None:
        return None
    x = sf(row.get("course_top3_rate"))
    if x is None or not (0.0 <= x <= 100.0):
        return None
    created = local_dt(row.get("snapshot_created_at"))
    deadline = local_dt(row.get("deadline_at"))
    race_date = row.get("race_date")
    if created is None or deadline is None or not isinstance(race_date, date):
        return None
    if created.date() != race_date:
        return None
    cutoff = datetime.combine(race_date, MORNING_CUTOFF, tzinfo=JST)
    if created > cutoff or created >= deadline:
        return None
    return x


def observed_z_by_lane(rows: list[dict[str, Any]]) -> tuple[dict[int, float], int]:
    observed: dict[int, float] = {}
    for row in rows:
        lane = int(row.get("lane") or 0)
        x = safe_course_value(row)
        if lane in range(1, 7) and x is not None:
            observed[lane] = x
    zs = {lane: 0.0 for lane in range(1, 7)}
    n = len(observed)
    if n < 2:
        return zs, n
    vals = list(observed.values())
    mu = sum(vals) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / n)
    if sd < 1e-12:
        return zs, n
    for lane, value in observed.items():
        zs[lane] = (value - mu) / sd
    return zs, n


def distributions(rows: list[dict[str, Any]], venue: str) -> tuple[dict[str, float], dict[str, float], int] | None:
    raw = base_raw(rows, venue)
    if raw is None:
        return None
    base = ticket_probs_from_raw(raw)
    if base is None:
        return None
    zs, observed_n = observed_z_by_lane(rows)
    plus_raw = {lane: raw[lane] + COURSE_COEF * zs[lane] for lane in range(1, 7)}
    plus = ticket_probs_from_raw(plus_raw)
    if plus is None:
        return None
    return base, plus, observed_n


def metric(probs: dict[str, float], actual: str) -> tuple[float, float, float, float, float, float, float]:
    p_actual = probs[actual]
    rank = 1 + sum(1 for ticket, p in probs.items() if ticket != actual and p > p_actual)
    brier = sum((p - (1.0 if ticket == actual else 0.0)) ** 2 for ticket, p in probs.items())
    ll = -math.log(max(EPS, p_actual))
    return (
        brier,
        ll,
        float(rank),
        float(rank <= 1),
        float(rank <= 3),
        float(rank <= 5),
        float(rank <= 10),
    )


def aggregate(values: list[tuple[float, ...]]) -> tuple[float, ...] | None:
    if not values:
        return None
    return tuple(sum(row[i] for row in values) / len(values) for i in range(len(values[0])))


def bootstrap_ci(deltas: list[tuple[float, float, float]]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None:
    if not deltas:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(deltas)
    samples: list[tuple[float, float, float]] = []
    for _ in range(BOOTSTRAP_N):
        sb = sl = sr = 0.0
        for _j in range(n):
            b, l, r = deltas[rng.randrange(n)]
            sb += b
            sl += l
            sr += r
        samples.append((sb / n, sl / n, sr / n))
    samples_b = sorted(x[0] for x in samples)
    samples_l = sorted(x[1] for x in samples)
    samples_r = sorted(x[2] for x in samples)
    lo = int(0.025 * BOOTSTRAP_N)
    hi = min(BOOTSTRAP_N - 1, int(0.975 * BOOTSTRAP_N))
    return (
        (samples_b[lo], samples_b[hi]),
        (samples_l[lo], samples_l[hi]),
        (samples_r[lo], samples_r[hi]),
    )


def emit_subset(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    base_vals = [x["base_metric"] for x in rows]
    plus_vals = [x["plus_metric"] for x in rows]
    b = aggregate(base_vals)
    p = aggregate(plus_vals)
    if b is None or p is None:
        print(f"COURSE_NEUTRAL_SUBSET={label} n:0", flush=True)
        return {"n": 0}
    deltas = [(x["plus_metric"][0] - x["base_metric"][0], x["plus_metric"][1] - x["base_metric"][1], x["plus_metric"][2] - x["base_metric"][2]) for x in rows]
    ci = bootstrap_ci(deltas)
    db = p[0] - b[0]
    dll = p[1] - b[1]
    dr = p[2] - b[2]
    print(
        f"COURSE_NEUTRAL_SUBSET={label} n:{len(rows)} brier_delta:{db:+.8f} logloss_delta:{dll:+.8f} rank_delta:{dr:+.4f} "
        f"top1:{b[3]*100:.2f}%->{p[3]*100:.2f}% top3:{b[4]*100:.2f}%->{p[4]*100:.2f}% "
        f"top5:{b[5]*100:.2f}%->{p[5]*100:.2f}% top10:{b[6]*100:.2f}%->{p[6]*100:.2f}%",
        flush=True,
    )
    if ci:
        print(
            f"COURSE_NEUTRAL_CI95={label} brier:[{ci[0][0]:+.8f},{ci[0][1]:+.8f}] "
            f"logloss:[{ci[1][0]:+.8f},{ci[1][1]:+.8f}] rank:[{ci[2][0]:+.4f},{ci[2][1]:+.4f}]",
            flush=True,
        )
    return {"n": len(rows), "brier_delta": db, "ll_delta": dll, "rank_delta": dr, "ci": ci}


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("COURSE_NEUTRAL_MODE=read_only_preregistered_fixed_rule_no_tuning", flush=True)
    print("COURSE_NEUTRAL_PREREG=908462848b73440359fd239d8f75dc2fa8d3a009", flush=True)
    print(f"COURSE_NEUTRAL_PERIOD={START}..{END}", flush=True)
    print(f"COURSE_NEUTRAL_COEF={COURSE_COEF:.2f}", flush=True)
    print("COURSE_NEUTRAL_RULE=observed_only_z_missing_zero_base_unchanged", flush=True)
    print("COURSE_NEUTRAL_POLICY=no_odds_no_payout_no_roi_no_writes_no_production_no_line_no_subgroup_tuning", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='240s'")
            cur.execute(
                """
                SELECT r.race_id,r.race_date,r.race_no,r.deadline_at,
                       lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                       e.lane,e.racer_number,e.racer_class,e.national_win_rate,e.national_place2_rate,
                       e.local_place2_rate,e.avg_st,
                       s.racer_number AS snapshot_racer_number,
                       s.top3_rate course_top3_rate,s.created_at snapshot_created_at
                  FROM v2_races r
                  JOIN v2_race_entries e ON e.race_id=r.race_id
                  LEFT JOIN v2_racer_course_stats_snapshots s
                    ON s.racer_number=e.racer_number
                   AND s.snapshot_date=r.race_date
                   AND s.course=e.lane
                 WHERE r.race_date BETWEEN %s AND %s
                 ORDER BY r.race_id,e.lane
                """,
                (START, END),
            )
            entry_rows = [dict(x) for x in cur.fetchall()]
            # Outcome query is separate and happens after the feature-side snapshot query.
            cur.execute(
                """
                SELECT res.race_id,res.trifecta_ticket
                  FROM v2_results res
                  JOIN v2_races r ON r.race_id=res.race_id
                 WHERE r.race_date BETWEEN %s AND %s
                """,
                (START, END),
            )
            results = {str(x["race_id"]): norm_ticket(x.get("trifecta_ticket")) for x in cur.fetchall()}
        conn.rollback()

    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entry_rows:
        by_race[str(row["race_id"])].append(row)

    records: list[dict[str, Any]] = []
    coverage = Counter()
    by_date = Counter()
    by_venue = Counter()
    observed_counts = Counter()

    for race_id, rows in sorted(by_race.items()):
        coverage["target"] += 1
        rows = sorted(rows, key=lambda x: int(x.get("lane") or 0))
        if len(rows) != 6 or [int(x.get("lane") or 0) for x in rows] != [1, 2, 3, 4, 5, 6]:
            coverage["entries_not_exactly_6"] += 1
            continue
        actual = results.get(race_id, "")
        if not actual:
            coverage["missing_result"] += 1
            continue
        venue = str(rows[0].get("venue") or "").zfill(2)
        dist = distributions(rows, venue)
        if dist is None:
            coverage["invalid_distribution"] += 1
            continue
        base, plus, observed_n = dist
        if actual not in base or actual not in plus:
            coverage["actual_not_in_distribution"] += 1
            continue
        race_date = rows[0].get("race_date")
        record = {
            "race_id": race_id,
            "race_date": race_date,
            "venue": venue,
            "observed_n": observed_n,
            "base_metric": metric(base, actual),
            "plus_metric": metric(plus, actual),
        }
        records.append(record)
        coverage["evaluable"] += 1
        observed_counts[observed_n] += 1
        by_date[str(race_date)] += 1
        by_venue[venue] += 1

    print("COURSE_NEUTRAL_COVERAGE=" + " ".join(f"{k}:{coverage[k]}" for k in sorted(coverage)), flush=True)
    print("COURSE_NEUTRAL_OBSERVED_LANES=" + " ".join(f"n{k}:{observed_counts[k]}" for k in range(7)), flush=True)
    for d in sorted(by_date):
        print(f"COURSE_NEUTRAL_DATE=date:{d} n:{by_date[d]}", flush=True)
    for venue in sorted(by_venue):
        print(f"COURSE_NEUTRAL_VENUE=venue:{venue} n:{by_venue[venue]}", flush=True)

    all_result = emit_subset("ALL_ELIGIBLE", records)
    complete = [r for r in records if r["observed_n"] == 6]
    missing = [r for r in records if r["observed_n"] < 6]
    emit_subset("COMPLETE6", complete)
    missing_result = emit_subset("MISSING1PLUS", missing)

    missing_dates = len({r["race_date"] for r in missing})
    missing_venues = len({r["venue"] for r in missing})
    print(
        f"COURSE_NEUTRAL_MISSING_SAMPLE=n:{len(missing)} dates:{missing_dates} venues:{missing_venues} min_n:{MIN_MISSING_RACES} min_dates:{MIN_MISSING_DATES}",
        flush=True,
    )

    status = "DO_NOT_ADVANCE_NEUTRAL_FALLBACK"
    if len(missing) < MIN_MISSING_RACES or missing_dates < MIN_MISSING_DATES:
        status = "INSUFFICIENT_MISSING_SAMPLE"
    else:
        ci = missing_result.get("ci")
        supports = bool(
            ci
            and missing_result.get("ll_delta", 1.0) <= 0.0
            and missing_result.get("brier_delta", 1.0) <= 0.0
            and missing_result.get("rank_delta", 1.0) <= 0.0
            and ci[1][1] <= 0.0
            and ci[0][1] <= 0.0
            and all_result.get("ll_delta", 1.0) <= 0.0
            and all_result.get("brier_delta", 1.0) <= 0.0
        )
        if supports:
            status = "SUPPORTS_NEUTRAL_FALLBACK_FORWARD_RESEARCH_ONLY"
    print(f"COURSE_NEUTRAL_STATUS={status}", flush=True)
    print("COURSE_NEUTRAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
