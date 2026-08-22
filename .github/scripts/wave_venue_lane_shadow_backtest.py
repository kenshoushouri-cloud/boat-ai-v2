# -*- coding: utf-8 -*-
"""Read-only OOS backtest for venue x lane x wave-height adjustment.

This script never writes to PostgreSQL and never changes production prediction,
Shadow tables, Railway settings, or LINE behavior.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all
import v22_realtime_decision_engine_pg as base

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("WAVE_BT_START_DATE", "2025-07-01"))
SPLIT_DATE = date.fromisoformat(os.getenv("WAVE_BT_SPLIT_DATE", "2026-05-31"))
END_DATE = date.fromisoformat(os.getenv("WAVE_BT_END_DATE", "2026-08-22"))
HIST_LABEL = "historical"
BUCKET_MIN = 30
BASE_MIN = 100
SHRINK_K = 50.0
WEIGHTS = (0.25, 0.50, 1.00)
EPS = 1e-6


def wave_bucket(v):
    x = float(v)
    if x < 3:
        return "<3"
    if x < 6:
        return "3-<6"
    if x < 10:
        return "6-<10"
    return "10+"


def logit(p):
    p = min(1.0 - EPS, max(EPS, p))
    return math.log(p / (1.0 - p))


def softmax(raw):
    vals = {k: math.exp(v / base.PROB_TEMP) for k, v in raw.items()}
    s = sum(vals.values())
    return {k: vals[k] / s for k in vals}


def metrics(rows):
    n = len(rows)
    if not n:
        return {"n": 0, "top1": 0.0, "logloss": 0.0, "brier": 0.0}
    top1 = 0
    ll = 0.0
    br = 0.0
    for probs, winner in rows:
        pred = max(probs, key=probs.get)
        top1 += int(pred == winner)
        ll += -math.log(max(EPS, probs.get(winner, EPS)))
        br += sum((probs[l] - (1.0 if l == winner else 0.0)) ** 2 for l in probs)
    return {"n": n, "top1": top1 / n, "logloss": ll / n, "brier": br / n}


def load_rows(start, end):
    return fetch_all(
        """
        select r.race_id,r.race_date,r.venue_id,e.*,re.finish_position,w.wave_height_cm
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        join v2_result_entries re
          on re.race_id=e.race_id and re.lane=e.lane and re.racer_number=e.racer_number
        join v2_realtime_weather_snapshots w
          on w.race_id=r.race_id and w.snapshot_label=%s
        where r.race_date >= %s and r.race_date <= %s
          and re.finish_position between 1 and 6
          and w.wave_height_cm is not null
        order by r.race_date,r.race_id,e.lane
        """,
        (HIST_LABEL, start, end),
    )


def build_profile(rows):
    base_counts = defaultdict(lambda: [0, 0])
    bucket_counts = defaultdict(lambda: [0, 0])
    for x in rows:
        venue = str(x.get("venue_id") or "").zfill(2)
        lane = int(x.get("lane") or 0)
        if lane not in range(1, 7):
            continue
        win = int(x.get("finish_position") == 1)
        b = wave_bucket(x.get("wave_height_cm"))
        base_counts[(venue, lane)][0] += 1
        base_counts[(venue, lane)][1] += win
        bucket_counts[(venue, lane, b)][0] += 1
        bucket_counts[(venue, lane, b)][1] += win

    out = {}
    for key, (n, wins) in bucket_counts.items():
        venue, lane, _ = key
        bn, bw = base_counts[(venue, lane)]
        if n < BUCKET_MIN or bn < BASE_MIN:
            continue
        p_bucket = (wins + 0.5) / (n + 1.0)
        p_base = (bw + 0.5) / (bn + 1.0)
        shrink = n / (n + SHRINK_K)
        out[key] = {
            "n": n,
            "base_n": bn,
            "delta_logit": (logit(p_bucket) - logit(p_base)) * shrink,
        }
    return out


def group_races(rows):
    by = defaultdict(list)
    for x in rows:
        by[str(x.get("race_id"))].append(x)
    return by


def stability_summary(base_groups, adj_groups):
    result = {}
    keys = sorted(base_groups)
    for w in WEIGHTS:
        eligible = 0
        logloss_better = 0
        brier_better = 0
        top1_not_worse = 0
        all_three = 0
        for key in keys:
            bm = metrics(base_groups[key])
            am = metrics(adj_groups[w].get(key, []))
            if bm["n"] < 50 or am["n"] != bm["n"]:
                continue
            eligible += 1
            ll = am["logloss"] < bm["logloss"]
            br = am["brier"] < bm["brier"]
            t1 = am["top1"] >= bm["top1"]
            logloss_better += int(ll)
            brier_better += int(br)
            top1_not_worse += int(t1)
            all_three += int(ll and br and t1)
        result[w] = {
            "eligible": eligible,
            "logloss_better": logloss_better,
            "brier_better": brier_better,
            "top1_not_worse": top1_not_worse,
            "all_three": all_three,
        }
    return result


def evaluate(rows, profile):
    grouped = group_races(rows)
    baseline = []
    adjusted = {w: [] for w in WEIGHTS}
    month_base = defaultdict(list)
    month_adj = {w: defaultdict(list) for w in WEIGHTS}
    venue_base = defaultdict(list)
    venue_adj = {w: defaultdict(list) for w in WEIGHTS}
    covered_races = 0
    complete_races = 0

    for _, rr in grouped.items():
        if len(rr) != 6:
            continue
        lanes = {int(x.get("lane") or 0): x for x in rr}
        if set(lanes) != {1, 2, 3, 4, 5, 6}:
            continue
        winners = [lane for lane, x in lanes.items() if int(x.get("finish_position") or 0) == 1]
        if len(winners) != 1:
            continue
        winner = winners[0]
        venue = str(rr[0].get("venue_id") or "").zfill(2)
        month = str(rr[0].get("race_date"))[:7]
        bucket = wave_bucket(rr[0].get("wave_height_cm"))
        raw = {lane: base._lane_raw_strength(lanes[lane], lane, venue) for lane in range(1, 7)}
        base_rec = (softmax(raw), winner)
        baseline.append(base_rec)
        month_base[month].append(base_rec)
        venue_base[venue].append(base_rec)
        complete_races += 1

        effects = {lane: profile.get((venue, lane, bucket)) for lane in range(1, 7)}
        if any(effects.values()):
            covered_races += 1
        for weight in WEIGHTS:
            adj_raw = dict(raw)
            for lane, effect in effects.items():
                if effect:
                    adj_raw[lane] += effect["delta_logit"] * base.PROB_TEMP * weight
            rec = (softmax(adj_raw), winner)
            adjusted[weight].append(rec)
            month_adj[weight][month].append(rec)
            venue_adj[weight][venue].append(rec)

    return {
        "complete": complete_races,
        "covered": covered_races,
        "baseline": metrics(baseline),
        "adjusted": {w: metrics(v) for w, v in adjusted.items()},
        "month_stability": stability_summary(month_base, month_adj),
        "venue_stability": stability_summary(venue_base, venue_adj),
    }


def print_stability(prefix, data):
    for w in WEIGHTS:
        s = data[w]
        e = s["eligible"]
        print(
            f"WAVE_SHADOW_BT_{prefix}_{w:.2f}=eligible:{e} "
            f"logloss_better:{s['logloss_better']}/{e} "
            f"brier_better:{s['brier_better']}/{e} "
            f"top1_not_worse:{s['top1_not_worse']}/{e} "
            f"all_three:{s['all_three']}/{e}",
            flush=True,
        )


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if not (START_DATE <= SPLIT_DATE < END_DATE):
        raise RuntimeError("invalid period")

    oos_start = date.fromordinal(SPLIT_DATE.toordinal() + 1)
    print("WAVE_SHADOW_BT_MODE=read_only", flush=True)
    print(f"WAVE_SHADOW_BT_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(f"WAVE_SHADOW_BT_TRAIN={START_DATE}..{SPLIT_DATE}", flush=True)
    print(f"WAVE_SHADOW_BT_OOS={oos_start}..{END_DATE}", flush=True)
    print(f"WAVE_SHADOW_BT_GATES=bucket>={BUCKET_MIN},base>={BASE_MIN},shrink_k={SHRINK_K}", flush=True)
    print("WAVE_SHADOW_BT_POLICY=no_writes_no_production_no_shadow_table_no_line", flush=True)

    train = load_rows(START_DATE, SPLIT_DATE)
    oos = load_rows(oos_start, END_DATE)
    profile = build_profile(train)
    print(f"WAVE_SHADOW_BT_PROFILE_GROUPS={len(profile)}", flush=True)
    result = evaluate(oos, profile)
    complete = result["complete"]
    covered = result["covered"]
    base_m = result["baseline"]
    print(f"WAVE_SHADOW_BT_OOS_RACES={complete}", flush=True)
    print(f"WAVE_SHADOW_BT_COVERED_RACES={covered} ({(100.0 * covered / complete if complete else 0.0):.1f}%)", flush=True)
    print(f"WAVE_SHADOW_BT_BASELINE=top1:{100 * base_m['top1']:.3f}% logloss:{base_m['logloss']:.6f} brier:{base_m['brier']:.6f}", flush=True)
    for w in WEIGHTS:
        m = result["adjusted"][w]
        print(
            f"WAVE_SHADOW_BT_WEIGHT_{w:.2f}=top1:{100 * m['top1']:.3f}% "
            f"logloss:{m['logloss']:.6f} brier:{m['brier']:.6f} "
            f"delta_top1_pt:{100 * (m['top1'] - base_m['top1']):+.3f} "
            f"delta_logloss:{m['logloss'] - base_m['logloss']:+.6f} "
            f"delta_brier:{m['brier'] - base_m['brier']:+.6f}",
            flush=True,
        )
    print_stability("MONTH_STABILITY", result["month_stability"])
    print_stability("VENUE_STABILITY", result["venue_stability"])
    print("WAVE_SHADOW_BT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
