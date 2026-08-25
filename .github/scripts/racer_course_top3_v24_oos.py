# -*- coding: utf-8 -*-
"""Fixed expanding OOS test of official racer-by-course top3 rate over current v24.

Pre-registered before reading outcomes in this audit:
- feature: official `course top3 rate` only (not course avg ST / entry rate)
- early-PRE proxy: frame/lane is used as course
- snapshot must be exact race date, all six lanes complete, current stored row created
  before race deadline AND no later than 08:15 JST; this represents the scheduled
  07:15 JST morning collector and rejects later mutable re-runs
- current v24 baseline exactly preserves Production PRE motor2/boat2 defaults 33/34
- course effect is within-race z(course_top3_rate) added to v24 lane raw strength
- coefficient grid is fixed here and selected on TRAIN ONLY
- three expanding, non-overlapping test windows are fixed below
- no venue/race-band/date subgroup selection, no test-set coefficient tuning
- no writes / Production / LINE / threshold or promotion changes
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import defaultdict
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
END = date(2026, 8, 24)
MORNING_CUTOFF = time(8, 15)
COEFS = (0.00, 0.05, 0.10, 0.20, 0.30, 0.50)
EPS = 1e-15
MIN_TRAIN_N = 700
MIN_TEST_N = 300
SPLITS = (
    ("S1", date(2026, 7, 15), date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 8)),
    ("S2", date(2026, 7, 15), date(2026, 8, 8), date(2026, 8, 9), date(2026, 8, 16)),
    ("S3", date(2026, 7, 15), date(2026, 8, 16), date(2026, 8, 17), date(2026, 8, 24)),
)


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


def zscores(vals: list[float]) -> list[float] | None:
    if len(vals) != 6:
        return None
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    return [(x - mu) / sd for x in vals]


def _clean_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def distribution(rows: list[dict[str, Any]], venue: str, coef: float) -> dict[str, float] | None:
    clean = _clean_entries(rows)
    by = v24._entry_by_lane(clean)
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None
    course_vals: list[float] = []
    for lane in range(1, 7):
        match = next((r for r in rows if int(r.get("lane") or 0) == lane), None)
        x = sf(match.get("course_top3_rate") if match else None)
        if x is None or not (0 <= x <= 100):
            return None
        course_vals.append(x)
    zs = zscores(course_vals)
    if zs is None:
        return None

    raw = {lane: v24._lane_raw_strength(by[lane], lane, venue) + coef * zs[lane - 1] for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    if total <= 0:
        return None
    out: dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        rem_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / rem_b
            rem_c = rem_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / rem_c)
    z = sum(out.values())
    return {t: p / z for t, p in out.items()} if len(out) == 120 and z > 0 else None


def rank_of(probs: dict[str, float], actual: str) -> int:
    p = probs[actual]
    return 1 + sum(1 for t, x in probs.items() if t != actual and x > p)


def metrics(probs: dict[str, float], actual: str) -> tuple[float, float, float, float, float, float, float]:
    rank = rank_of(probs, actual)
    brier = sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in probs.items())
    ll = -math.log(max(EPS, probs[actual]))
    return (
        brier,
        ll,
        float(rank),
        float(rank <= 1),
        float(rank <= 3),
        float(rank <= 5),
        float(rank <= 10),
    )


def local_dt(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def morning_safe(row: dict[str, Any]) -> bool:
    created = local_dt(row.get("snapshot_created_at"))
    deadline = local_dt(row.get("deadline_at"))
    race_date = row.get("race_date")
    if created is None or deadline is None or race_date is None:
        return False
    return created.date() == race_date and created.time().replace(tzinfo=None) <= MORNING_CUTOFF and created < deadline


def aggregate(vals: list[tuple[float, float, float, float, float, float, float]]) -> tuple[float, ...] | None:
    if not vals:
        return None
    return tuple(sum(x[i] for x in vals) / len(vals) for i in range(7))


def evaluate(races: list[dict[str, Any]], coef: float) -> tuple[int, tuple[float, ...] | None]:
    vals = []
    for race in races:
        probs = distribution(race["rows"], race["venue"], coef)
        if probs is None or race["actual"] not in probs:
            continue
        vals.append(metrics(probs, race["actual"]))
    return len(vals), aggregate(vals)


def emit(label: str, n: int, base: tuple[float, ...], plus: tuple[float, ...], coef: float) -> None:
    print(
        f"RACER_COURSE_OOS={label} n:{n} coef:{coef:.2f} "
        f"brier_delta:{plus[0]-base[0]:+.8f} logloss_delta:{plus[1]-base[1]:+.8f} "
        f"rank_delta:{plus[2]-base[2]:+.4f} "
        f"top1:{base[3]*100:.2f}%->{plus[3]*100:.2f}% "
        f"top3:{base[4]*100:.2f}%->{plus[4]*100:.2f}% "
        f"top5:{base[5]*100:.2f}%->{plus[5]*100:.2f}% "
        f"top10:{base[6]*100:.2f}%->{plus[6]*100:.2f}%",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("RACER_COURSE_OOS_MODE=read_only_pre_registered_train_only_coefficient", flush=True)
    print(f"RACER_COURSE_OOS_PERIOD={START}..{END}", flush=True)
    print("RACER_COURSE_OOS_BASE=current_v24_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("RACER_COURSE_OOS_FEATURE=official_course_top3_rate_only_lane_as_course_proxy", flush=True)
    print("RACER_COURSE_OOS_SNAPSHOT_GATE=exact_date_all6_created_by_0815_jst_and_before_deadline", flush=True)
    print("RACER_COURSE_OOS_COEF_GRID=" + ",".join(f"{x:.2f}" for x in COEFS), flush=True)
    print("RACER_COURSE_OOS_POLICY=no_test_tuning_no_subgroup_selection_no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='180s'")
            cur.execute(
                """
                select r.race_id,r.race_date,r.race_no,r.deadline_at,
                       lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                       e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                       e.local_place2_rate,e.avg_st,
                       s.top3_rate course_top3_rate,s.created_at snapshot_created_at
                  from v2_races r
                  join v2_race_entries e on e.race_id=r.race_id
                  left join v2_racer_course_stats_snapshots s
                    on s.racer_number=e.racer_number
                   and s.snapshot_date=r.race_date
                   and s.course=e.lane
                 where r.race_date between %s and %s
                 order by r.race_id,e.lane
                """,
                (START, END),
            )
            entries = [dict(x) for x in cur.fetchall()]
            cur.execute(
                """select res.race_id,res.trifecta_ticket
                     from v2_results res join v2_races r on r.race_id=res.race_id
                    where r.race_date between %s and %s""",
                (START, END),
            )
            results = {str(x["race_id"]): norm_ticket(x.get("trifecta_ticket")) for x in cur.fetchall()}

    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        by_race[str(row["race_id"])].append(row)

    safe_races: list[dict[str, Any]] = []
    coverage = defaultdict(int)
    per_date = defaultdict(lambda: defaultdict(int))
    for rid, rows in by_race.items():
        coverage["target"] += 1
        rows = sorted(rows, key=lambda x: int(x.get("lane") or 0))
        d = rows[0].get("race_date") if rows else None
        if d:
            per_date[str(d)]["target"] += 1
        if len(rows) != 6 or sorted(int(x.get("lane") or 0) for x in rows) != [1, 2, 3, 4, 5, 6]:
            coverage["card_incomplete"] += 1
            continue
        if not all(sf(x.get("course_top3_rate")) is not None for x in rows):
            coverage["stats_incomplete"] += 1
            continue
        if not all(morning_safe(x) for x in rows):
            coverage["not_morning_frozen"] += 1
            continue
        coverage["morning_safe_full6"] += 1
        if d:
            per_date[str(d)]["safe"] += 1
        actual = results.get(rid, "")
        if not actual:
            coverage["missing_result"] += 1
            continue
        venue = str(rows[0].get("venue") or "").zfill(2)
        # Require both baseline and largest-grid distribution to be numerically valid before inclusion.
        if distribution(rows, venue, 0.0) is None or distribution(rows, venue, max(COEFS)) is None:
            coverage["invalid_distribution"] += 1
            continue
        safe_races.append({"race_id": rid, "race_date": d, "venue": venue, "rows": rows, "actual": actual})
        coverage["evaluable"] += 1

    print("RACER_COURSE_OOS_COVERAGE=" + " ".join(f"{k}:{v}" for k, v in coverage.items()), flush=True)
    for d in sorted(per_date):
        x = per_date[d]
        print(f"RACER_COURSE_OOS_DATE=date:{d} target:{x['target']} safe:{x['safe']}", flush=True)

    all_test_records: list[tuple[float, float, float, float, float, float, float]] = []
    all_test_plus: list[tuple[float, float, float, float, float, float, float]] = []
    selected: list[float] = []
    split_signs: list[tuple[float, float, float]] = []

    for name, train_start, train_end, test_start, test_end in SPLITS:
        train = [r for r in safe_races if train_start <= r["race_date"] <= train_end]
        test = [r for r in safe_races if test_start <= r["race_date"] <= test_end]
        if len(train) < MIN_TRAIN_N or len(test) < MIN_TEST_N:
            print(f"RACER_COURSE_OOS_SPLIT={name} status:INSUFFICIENT train_n:{len(train)} test_n:{len(test)}", flush=True)
            continue

        scored: list[tuple[float, float, int]] = []
        for coef in COEFS:
            n, m = evaluate(train, coef)
            if m is not None:
                scored.append((m[1], coef, n))
        scored.sort(key=lambda x: (x[0], x[1]))
        best_ll, coef, train_n = scored[0]
        selected.append(coef)
        print(
            f"RACER_COURSE_OOS_SELECT={name} train:{train_start}..{train_end} train_n:{train_n} "
            f"coef:{coef:.2f} train_ll:{best_ll:.8f} grid:" + ",".join(f"{c:.2f}" for c in COEFS),
            flush=True,
        )

        bn, bm = evaluate(test, 0.0)
        pn, pm = evaluate(test, coef)
        n = min(bn, pn)
        if bm is None or pm is None or n < MIN_TEST_N:
            print(f"RACER_COURSE_OOS_SPLIT={name} status:INVALID_EVAL n:{n}", flush=True)
            continue
        emit(f"{name}_TEST_{test_start}_{test_end}", n, bm, pm, coef)
        split_signs.append((pm[0] - bm[0], pm[1] - bm[1], pm[2] - bm[2]))

        # Non-overlapping test windows allow a clean overall aggregate.
        for race in test:
            b = distribution(race["rows"], race["venue"], 0.0)
            p = distribution(race["rows"], race["venue"], coef)
            if b is None or p is None or race["actual"] not in b or race["actual"] not in p:
                continue
            all_test_records.append(metrics(b, race["actual"]))
            all_test_plus.append(metrics(p, race["actual"]))

    bm_all = aggregate(all_test_records)
    pm_all = aggregate(all_test_plus)
    if bm_all is not None and pm_all is not None and len(all_test_records) == len(all_test_plus):
        emit("ALL_NONOVERLAP_TESTS", len(all_test_records), bm_all, pm_all, -1.0)

    valid_splits = len(split_signs)
    ll_improved = sum(1 for _, ll, _ in split_signs if ll < 0)
    brier_improved = sum(1 for b, _, _ in split_signs if b < 0)
    rank_improved = sum(1 for _, _, r in split_signs if r < 0)
    positive_selected = sum(1 for c in selected if c > 0)
    overall_support = bool(
        valid_splits == 3
        and positive_selected == 3
        and ll_improved == 3
        and brier_improved == 3
        and bm_all is not None
        and pm_all is not None
        and pm_all[1] < bm_all[1]
        and pm_all[0] < bm_all[0]
    )
    print(
        f"RACER_COURSE_OOS_STABILITY=valid_splits:{valid_splits} positive_selected:{positive_selected}/{valid_splits} "
        f"ll_improved:{ll_improved}/{valid_splits} brier_improved:{brier_improved}/{valid_splits} rank_improved:{rank_improved}/{valid_splits}",
        flush=True,
    )
    print(
        "RACER_COURSE_OOS_VERDICT=" + (
            "SUPPORTS_FIXED_FORWARD_SHADOW_RESEARCH_ONLY" if overall_support else "NO_ROBUST_INCREMENTAL_SUPPORT_YET"
        ),
        flush=True,
    )
    print("RACER_COURSE_OOS_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("RACER_COURSE_OOS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
