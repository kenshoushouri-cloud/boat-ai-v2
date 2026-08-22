# -*- coding: utf-8 -*-
"""Read-only train-internal stability gate for venue x lane x wave effects.

The gate is decided entirely inside the training period. The untouched OOS
period is used only once for final evaluation. No database writes or production
changes are performed.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_SCRIPT = ROOT / ".github" / "scripts" / "wave_venue_lane_shadow_backtest.py"
spec = importlib.util.spec_from_file_location("wave_bt", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load wave backtest module")
wave_bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wave_bt)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
START_DATE = date.fromisoformat(os.getenv("WAVE_GATE_START_DATE", "2025-07-01"))
INTERNAL_SPLIT = date.fromisoformat(os.getenv("WAVE_GATE_INTERNAL_SPLIT", "2026-02-28"))
TRAIN_END = date.fromisoformat(os.getenv("WAVE_GATE_TRAIN_END", "2026-05-31"))
OOS_END = date.fromisoformat(os.getenv("WAVE_GATE_OOS_END", "2026-08-22"))
HALF_BUCKET_MIN = 15
HALF_BASE_MIN = 50
HALF_MIN_ABS_LOGIT = 0.05
HALF_SHRINK_K = 25.0


def next_day(d: date) -> date:
    return date.fromordinal(d.toordinal() + 1)


def logit(p: float) -> float:
    eps = 1e-6
    p = min(1.0 - eps, max(eps, p))
    return math.log(p / (1.0 - p))


def half_effects(rows):
    base_counts = defaultdict(lambda: [0, 0])
    bucket_counts = defaultdict(lambda: [0, 0])
    for x in rows:
        venue = str(x.get("venue_id") or "").zfill(2)
        lane = int(x.get("lane") or 0)
        if lane not in range(1, 7):
            continue
        win = int(x.get("finish_position") == 1)
        bucket = wave_bt.wave_bucket(x.get("wave_height_cm"))
        base_counts[(venue, lane)][0] += 1
        base_counts[(venue, lane)][1] += win
        bucket_counts[(venue, lane, bucket)][0] += 1
        bucket_counts[(venue, lane, bucket)][1] += win

    out = {}
    for key, (n, wins) in bucket_counts.items():
        venue, lane, _ = key
        bn, bw = base_counts[(venue, lane)]
        if n < HALF_BUCKET_MIN or bn < HALF_BASE_MIN:
            continue
        pb = (wins + 0.5) / (n + 1.0)
        p0 = (bw + 0.5) / (bn + 1.0)
        shrink = n / (n + HALF_SHRINK_K)
        delta = (logit(pb) - logit(p0)) * shrink
        if abs(delta) < HALF_MIN_ABS_LOGIT:
            continue
        out[key] = {"n": n, "base_n": bn, "delta_logit": delta}
    return out


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if not (START_DATE <= INTERNAL_SPLIT < TRAIN_END < OOS_END):
        raise RuntimeError("invalid periods")

    late_start = next_day(INTERNAL_SPLIT)
    oos_start = next_day(TRAIN_END)
    print("WAVE_GATE_MODE=read_only", flush=True)
    print(f"WAVE_GATE_TRAIN_EARLY={START_DATE}..{INTERNAL_SPLIT}", flush=True)
    print(f"WAVE_GATE_TRAIN_LATE={late_start}..{TRAIN_END}", flush=True)
    print(f"WAVE_GATE_OOS={oos_start}..{OOS_END}", flush=True)
    print(
        f"WAVE_GATE_RULE=half_bucket>={HALF_BUCKET_MIN},half_base>={HALF_BASE_MIN},"
        f"abs_logit>={HALF_MIN_ABS_LOGIT},same_sign,half_shrink_k={HALF_SHRINK_K}",
        flush=True,
    )
    print("WAVE_GATE_POLICY=train_only_gate_no_oos_selection_no_writes_no_production_no_line", flush=True)

    early = wave_bt.load_rows(START_DATE, INTERNAL_SPLIT)
    late = wave_bt.load_rows(late_start, TRAIN_END)
    full_train = wave_bt.load_rows(START_DATE, TRAIN_END)
    oos = wave_bt.load_rows(oos_start, OOS_END)

    e1 = half_effects(early)
    e2 = half_effects(late)
    stable_keys = {
        key for key in (set(e1) & set(e2))
        if e1[key]["delta_logit"] * e2[key]["delta_logit"] > 0
    }
    full_profile = wave_bt.build_profile(full_train)
    gated_profile = {key: value for key, value in full_profile.items() if key in stable_keys}

    print(f"WAVE_GATE_EARLY_ELIGIBLE={len(e1)}", flush=True)
    print(f"WAVE_GATE_LATE_ELIGIBLE={len(e2)}", flush=True)
    print(f"WAVE_GATE_SAME_SIGN_KEYS={len(stable_keys)}", flush=True)
    print(f"WAVE_GATE_FULL_PROFILE_GROUPS={len(full_profile)}", flush=True)
    print(f"WAVE_GATE_FINAL_PROFILE_GROUPS={len(gated_profile)}", flush=True)

    result = wave_bt.evaluate(oos, gated_profile)
    complete = result["complete"]
    covered = result["covered"]
    bm = result["baseline"]
    print(f"WAVE_GATE_OOS_RACES={complete}", flush=True)
    print(f"WAVE_GATE_COVERED_RACES={covered} ({(100.0*covered/complete if complete else 0.0):.1f}%)", flush=True)
    print(f"WAVE_GATE_BASELINE=top1:{100*bm['top1']:.3f}% logloss:{bm['logloss']:.6f} brier:{bm['brier']:.6f}", flush=True)
    for w in wave_bt.WEIGHTS:
        m = result["adjusted"][w]
        print(
            f"WAVE_GATE_WEIGHT_{w:.2f}=top1:{100*m['top1']:.3f}% "
            f"logloss:{m['logloss']:.6f} brier:{m['brier']:.6f} "
            f"delta_top1_pt:{100*(m['top1']-bm['top1']):+.3f} "
            f"delta_logloss:{m['logloss']-bm['logloss']:+.6f} "
            f"delta_brier:{m['brier']-bm['brier']:+.6f}",
            flush=True,
        )
        ms = result["month_stability"][w]
        vs = result["venue_stability"][w]
        print(
            f"WAVE_GATE_MONTH_{w:.2f}=eligible:{ms['eligible']} all_three:{ms['all_three']} "
            f"logloss_better:{ms['logloss_better']} brier_better:{ms['brier_better']} "
            f"top1_not_worse:{ms['top1_not_worse']}", flush=True,
        )
        print(
            f"WAVE_GATE_VENUE_{w:.2f}=eligible:{vs['eligible']} all_three:{vs['all_three']} "
            f"logloss_better:{vs['logloss_better']} brier_better:{vs['brier_better']} "
            f"top1_not_worse:{vs['top1_not_worse']}", flush=True,
        )
    print("WAVE_GATE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
