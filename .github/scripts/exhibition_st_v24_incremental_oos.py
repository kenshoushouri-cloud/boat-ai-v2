# -*- coding: utf-8 -*-
"""Read-only OOS audit of exhibition start-timing rank incremental value over current v24.

Fixed design, no tuning:
- current v24 lane formula and PROB_TEMP=2.20
- current Production PRE behavior: motor2/boat2 omitted, so v24 defaults 33/34
- exhibition ST ticket score exactly follows PR #122: z-score(-start_timing_rank),
  position weights 1.0 / 0.6 / 0.3
- beta = -0.02 fixed from the FIRST PR #122 training cutoff (through 2025-12-31)
- evaluate only future rows 2026-01-01..2026-08-22
- no beta search, subgroup selection, DB writes, Production/LINE changes, or promotion
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import v24_pre_candidate_notifier_pg as v24

DB = os.getenv("DATABASE_URL", "").strip()
START = date(2026, 1, 1)
END = date(2026, 8, 22)
HIST_LABEL = "historical"
FIXED_ST_BETA = -0.02  # frozen from PR #122 first train cutoff only; never searched here
POS = (1.0, 0.6, 0.3)
EPS = 1e-15
WINDOWS = (
    ("W1_2026JAN_FEB", date(2026, 1, 1), date(2026, 2, 28)),
    ("W2_2026MAR_APR", date(2026, 3, 1), date(2026, 4, 30)),
    ("W3_2026MAY_JUN", date(2026, 5, 1), date(2026, 6, 30)),
    ("W4_2026JUL_AUG22", date(2026, 7, 1), END),
)


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def norm_ticket(v: Any) -> str:
    import re
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


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    if 9 <= race_no <= 12:
        return "R09_12"
    return "R_OTHER"


def v24_distribution(entries: list[dict[str, Any]], venue: str) -> dict[str, float] | None:
    # Intentionally pass only fields used by current Production PRE fetch.
    # motor_place2_rate / boat_place2_rate are not passed, preserving fixed defaults 33/34.
    clean = [
        {
            "lane": e.get("lane"),
            "racer_class": e.get("racer_class"),
            "national_win_rate": e.get("national_win_rate"),
            "national_place2_rate": e.get("national_place2_rate"),
            "local_place2_rate": e.get("local_place2_rate"),
            "avg_st": e.get("avg_st"),
        }
        for e in entries
    ]
    by = v24._entry_by_lane(clean)
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None
    raw = {lane: v24._lane_raw_strength(by[lane], lane, venue) for lane in range(1, 7)}
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


def st_ticket_score(xrows: list[dict[str, Any]]) -> dict[str, float] | None:
    xb = {int(x.get("lane") or 0): x for x in xrows}
    if sorted(xb) != [1, 2, 3, 4, 5, 6]:
        return None
    vals: list[float] = []
    for lane in range(1, 7):
        rank = sf(xb[lane].get("start_timing_rank"), 0.0)
        if int(rank) not in range(1, 7):
            return None
        vals.append(-rank)  # exactly PR #122 orientation
    zs = zscores(vals)
    if zs is None:
        return None
    out: dict[str, float] = {}
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = POS[0] * zs[a - 1] + POS[1] * zs[b - 1] + POS[2] * zs[c - 1]
    return out


def apply_fixed_st(base: dict[str, float], score: dict[str, float]) -> dict[str, float]:
    vals = {t: p * math.exp(FIXED_ST_BETA * score[t]) for t, p in base.items()}
    z = sum(vals.values())
    return {t: p / z for t, p in vals.items()}


def rank_of(probs: dict[str, float], actual: str) -> int:
    target = probs[actual]
    return 1 + sum(1 for t, p in probs.items() if t != actual and p > target)


def first_marginal(probs: dict[str, float]) -> list[float]:
    out = [0.0] * 6
    for ticket, p in probs.items():
        out[int(ticket[0]) - 1] += p
    return out


def lane_rank(probs: list[float], idx: int) -> int:
    target = probs[idx]
    return 1 + sum(1 for j, p in enumerate(probs) if j != idx and p > target)


def metrics(base: dict[str, float], plus: dict[str, float], actual: str) -> dict[str, float]:
    yb = base[actual]
    yp = plus[actual]
    rb = rank_of(base, actual)
    rp = rank_of(plus, actual)
    actual_first = int(actual[0]) - 1
    fb = first_marginal(base)
    fp = first_marginal(plus)
    y = [1.0 if i == actual_first else 0.0 for i in range(6)]
    return {
        "tri_brier_base": sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in base.items()),
        "tri_brier_plus": sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in plus.items()),
        "tri_ll_base": -math.log(max(EPS, yb)),
        "tri_ll_plus": -math.log(max(EPS, yp)),
        "tri_rank_base": float(rb),
        "tri_rank_plus": float(rp),
        "top1_base": float(rb <= 1), "top1_plus": float(rp <= 1),
        "top3_base": float(rb <= 3), "top3_plus": float(rp <= 3),
        "top5_base": float(rb <= 5), "top5_plus": float(rp <= 5),
        "top10_base": float(rb <= 10), "top10_plus": float(rp <= 10),
        "first_brier_base": sum((y[i] - fb[i]) ** 2 for i in range(6)) / 6.0,
        "first_brier_plus": sum((y[i] - fp[i]) ** 2 for i in range(6)) / 6.0,
        "first_ll_base": -math.log(max(EPS, fb[actual_first])),
        "first_ll_plus": -math.log(max(EPS, fp[actual_first])),
        "first_rank_base": float(lane_rank(fb, actual_first)),
        "first_rank_plus": float(lane_rank(fp, actual_first)),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"n": 0.0}
    keys = [k for k in rows[0] if k not in {"race_id", "race_date", "venue", "race_band"}]
    out = {"n": float(len(rows))}
    for k in keys:
        out[k] = sum(float(r[k]) for r in rows) / len(rows)
    return out


def emit(label: str, m: dict[str, float]) -> None:
    n = int(m.get("n", 0.0))
    if not n:
        print(f"ST_V24_OOS={label} n:0", flush=True)
        return
    print(
        f"ST_V24_OOS={label} n:{n} "
        f"tri_brier_delta:{m['tri_brier_plus']-m['tri_brier_base']:+.8f} "
        f"tri_logloss_delta:{m['tri_ll_plus']-m['tri_ll_base']:+.8f} "
        f"tri_rank_delta:{m['tri_rank_plus']-m['tri_rank_base']:+.4f} "
        f"top1:{m['top1_base']*100:.2f}%->{m['top1_plus']*100:.2f}% "
        f"top3:{m['top3_base']*100:.2f}%->{m['top3_plus']*100:.2f}% "
        f"top5:{m['top5_base']*100:.2f}%->{m['top5_plus']*100:.2f}% "
        f"top10:{m['top10_base']*100:.2f}%->{m['top10_plus']*100:.2f}% "
        f"first_brier_delta:{m['first_brier_plus']-m['first_brier_base']:+.8f} "
        f"first_logloss_delta:{m['first_ll_plus']-m['first_ll_base']:+.8f} "
        f"first_rank_delta:{m['first_rank_plus']-m['first_rank_base']:+.4f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("ST_V24_OOS_MODE=read_only_fixed_beta_current_v24_no_tuning", flush=True)
    print(f"ST_V24_OOS_PERIOD={START}..{END}", flush=True)
    print("ST_V24_OOS_BASE=current_v24_fixed_motor33_boat34_prob_temp_2.20", flush=True)
    print("ST_V24_OOS_FEATURE=historical_start_timing_rank_ticket_score_exact_pr122_orientation", flush=True)
    print(f"ST_V24_OOS_BETA={FIXED_ST_BETA:+.2f}_frozen_from_pr122_first_train_cutoff_2025_12_31", flush=True)
    print("ST_V24_OOS_POLICY=no_beta_search_no_subgroup_selection_no_writes_no_production_no_line", flush=True)

    records: list[dict[str, Any]] = []
    coverage = defaultdict(int)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='240s'")
            cur.execute(
                """select r.race_id,r.race_date,r.race_no,
                          lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                          e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                          e.local_place2_rate,e.avg_st
                     from v2_races r join v2_race_entries e on e.race_id=r.race_id
                    where r.race_date between %s and %s
                    order by r.race_id,e.lane""",
                (START, END),
            )
            entries = [dict(x) for x in cur.fetchall()]
            cur.execute(
                """select x.race_id,x.lane,x.start_timing_rank
                     from v2_realtime_exhibition_snapshots x
                     join v2_races r on r.race_id=x.race_id
                    where r.race_date between %s and %s and x.snapshot_label=%s
                    order by x.race_id,x.lane""",
                (START, END, HIST_LABEL),
            )
            exhibition = [dict(x) for x in cur.fetchall()]
            cur.execute(
                """select res.race_id,res.trifecta_ticket
                     from v2_results res join v2_races r on r.race_id=res.race_id
                    where r.race_date between %s and %s""",
                (START, END),
            )
            results = {str(x["race_id"]): norm_ticket(x.get("trifecta_ticket")) for x in cur.fetchall()}

    eb: dict[str, list[dict[str, Any]]] = defaultdict(list)
    xb: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(e)
    for x in exhibition:
        xb[str(x["race_id"])].append(x)

    for rid, erows in eb.items():
        coverage["races"] += 1
        actual = results.get(rid, "")
        if not actual:
            coverage["missing_result"] += 1
            continue
        erows = sorted(erows, key=lambda x: int(x.get("lane") or 0))
        xrows = sorted(xb.get(rid, []), key=lambda x: int(x.get("lane") or 0))
        if len(erows) != 6 or len(xrows) != 6:
            coverage["incomplete"] += 1
            continue
        venue = str(erows[0].get("venue") or "").zfill(2)
        base = v24_distribution(erows, venue)
        score = st_ticket_score(xrows)
        if base is None or score is None or actual not in base:
            coverage["invalid"] += 1
            continue
        plus = apply_fixed_st(base, score)
        m = metrics(base, plus, actual)
        m.update({
            "race_id": rid,
            "race_date": erows[0]["race_date"],
            "venue": venue,
            "race_band": race_band(int(erows[0].get("race_no") or 0)),
        })
        records.append(m)
        coverage["evaluated"] += 1

    print(
        f"ST_V24_OOS_COVERAGE=races:{coverage['races']} evaluated:{coverage['evaluated']} "
        f"missing_result:{coverage['missing_result']} incomplete:{coverage['incomplete']} invalid:{coverage['invalid']}",
        flush=True,
    )

    emit("COMBINED", aggregate(records))
    window_signs = 0
    for name, a, b in WINDOWS:
        rr = [r for r in records if a <= r["race_date"] <= b]
        m = aggregate(rr)
        emit(name, m)
        if m.get("n", 0) and m["tri_ll_plus"] < m["tri_ll_base"]:
            window_signs += 1

    months: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bands: dict[str, list[dict[str, Any]]] = defaultdict(list)
    venues: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        months[r["race_date"].strftime("%Y-%m")].append(r)
        bands[r["race_band"]].append(r)
        venues[r["venue"]].append(r)

    month_signs = 0
    for month in sorted(months):
        m = aggregate(months[month])
        emit(f"MONTH:{month}", m)
        if m["tri_ll_plus"] < m["tri_ll_base"]:
            month_signs += 1
    for band in ("R01_04", "R05_08", "R09_12"):
        if bands.get(band):
            emit(f"RACE_BAND:{band}", aggregate(bands[band]))

    venue_metrics = [aggregate(venues[v]) for v in sorted(venues)]
    print(
        f"ST_V24_OOS_SIGN_COUNTS=windows_tri_ll_better:{window_signs}/{len(WINDOWS)} "
        f"months_tri_ll_better:{month_signs}/{len(months)} venues:{len(venue_metrics)} "
        f"venue_tri_ll_better:{sum(m['tri_ll_plus'] < m['tri_ll_base'] for m in venue_metrics)} "
        f"venue_tri_brier_better:{sum(m['tri_brier_plus'] < m['tri_brier_base'] for m in venue_metrics)} "
        f"venue_tri_rank_better:{sum(m['tri_rank_plus'] < m['tri_rank_base'] for m in venue_metrics)}",
        flush=True,
    )

    allm = aggregate(records)
    if (
        allm.get("n", 0)
        and allm["tri_ll_plus"] < allm["tri_ll_base"]
        and allm["tri_brier_plus"] < allm["tri_brier_base"]
        and window_signs >= 3
        and month_signs >= max(6, len(months) - 2)
    ):
        interpretation = "PROMISING_FIXED_ST_V24_OOS_RESEARCH_ONLY"
    elif allm.get("n", 0) and (
        allm["tri_ll_plus"] < allm["tri_ll_base"] or allm["tri_brier_plus"] < allm["tri_brier_base"]
    ):
        interpretation = "MIXED_FIXED_ST_V24_OOS_KEEP_RESEARCH_ONLY"
    else:
        interpretation = "NO_FIXED_ST_V24_OOS_SUPPORT"
    print(f"ST_V24_OOS_INTERPRETATION={interpretation}", flush=True)
    print("ST_V24_OOS_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("ST_V24_OOS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
