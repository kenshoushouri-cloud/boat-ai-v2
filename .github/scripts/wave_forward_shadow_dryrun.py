# -*- coding: utf-8 -*-
"""Read-only forward dry-run for the gated wave x venue x lane candidate.

Uses actual realtime weather snapshots (`final_ab` by default), rebuilds the
train-only stable profile, and compares probability changes in memory only.
No tables are created or modified and no notifications are sent.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wave_bt = load_module("wave_bt_forward", ROOT / ".github/scripts/wave_venue_lane_shadow_backtest.py")
wave_gate = load_module("wave_gate_forward", ROOT / ".github/scripts/wave_train_stability_gate_backtest.py")

from db_pg import fetch_all
import v22_realtime_decision_engine_pg as decision

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("WAVE_FORWARD_TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
SNAPSHOT_LABEL = os.getenv("WAVE_FORWARD_SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
WEIGHTS = (0.25, 0.50, 1.00)


def build_gated_profile():
    early = wave_bt.load_rows(wave_gate.START_DATE, wave_gate.INTERNAL_SPLIT)
    late = wave_bt.load_rows(wave_gate.next_day(wave_gate.INTERNAL_SPLIT), wave_gate.TRAIN_END)
    full_train = wave_bt.load_rows(wave_gate.START_DATE, wave_gate.TRAIN_END)
    e1 = wave_gate.half_effects(early)
    e2 = wave_gate.half_effects(late)
    stable = {
        key for key in (set(e1) & set(e2))
        if e1[key]["delta_logit"] * e2[key]["delta_logit"] > 0
    }
    full = wave_bt.build_profile(full_train)
    return {k: v for k, v in full.items() if k in stable}


def load_live_rows():
    return fetch_all(
        """
        select r.race_id,r.race_date,r.venue_id,e.*,
               w.wave_height_cm,w.snapshot_at
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        join v2_realtime_weather_snapshots w
          on w.race_id=r.race_id and w.snapshot_label=%s
        where r.race_date=%s
          and w.wave_height_cm is not null
        order by r.race_id,e.lane
        """,
        (SNAPSHOT_LABEL, TARGET_DATE),
    )


def softmax(raw):
    return wave_bt.softmax(raw)


def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    print("WAVE_FORWARD_MODE=read_only_dry_run", flush=True)
    print(f"WAVE_FORWARD_TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"WAVE_FORWARD_SNAPSHOT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("WAVE_FORWARD_POLICY=no_writes_no_tables_no_prediction_change_no_line", flush=True)

    profile = build_gated_profile()
    rows = load_live_rows()
    by_race = defaultdict(list)
    for row in rows:
        by_race[str(row.get("race_id"))].append(row)

    complete = 0
    profile_covered = 0
    lane_effects = 0
    top1_changed = {w: 0 for w in WEIGHTS}
    prob_abs_sum = {w: 0.0 for w in WEIGHTS}
    prob_cells = {w: 0 for w in WEIGHTS}
    max_prob_shift = {w: 0.0 for w in WEIGHTS}

    for _, rr in by_race.items():
        if len(rr) != 6:
            continue
        lanes = {int(x.get("lane") or 0): x for x in rr}
        if set(lanes) != {1,2,3,4,5,6}:
            continue
        venue = str(rr[0].get("venue_id") or "").zfill(2)
        wave = rr[0].get("wave_height_cm")
        if wave is None:
            continue
        bucket = wave_bt.wave_bucket(wave)
        raw = {lane: decision._lane_raw_strength(lanes[lane], lane, venue) for lane in range(1,7)}
        bp = softmax(raw)
        base_top = max(bp, key=bp.get)
        effects = {lane: profile.get((venue, lane, bucket)) for lane in range(1,7)}
        n_effect = sum(1 for v in effects.values() if v)
        if n_effect:
            profile_covered += 1
            lane_effects += n_effect
        complete += 1

        for weight in WEIGHTS:
            adj = dict(raw)
            for lane, effect in effects.items():
                if effect:
                    adj[lane] += effect["delta_logit"] * decision.PROB_TEMP * weight
            ap = softmax(adj)
            if max(ap, key=ap.get) != base_top:
                top1_changed[weight] += 1
            for lane in range(1,7):
                shift = abs(ap[lane] - bp[lane])
                prob_abs_sum[weight] += shift
                prob_cells[weight] += 1
                max_prob_shift[weight] = max(max_prob_shift[weight], shift)

    print(f"WAVE_FORWARD_PROFILE_GROUPS={len(profile)}", flush=True)
    print(f"WAVE_FORWARD_SNAPSHOT_ROWS={len(rows)}", flush=True)
    print(f"WAVE_FORWARD_COMPLETE_RACES={complete}", flush=True)
    print(
        f"WAVE_FORWARD_PROFILE_COVERED_RACES={profile_covered} "
        f"({(100.0*profile_covered/complete if complete else 0.0):.1f}%)",
        flush=True,
    )
    print(f"WAVE_FORWARD_EFFECT_LANE_APPLICATIONS={lane_effects}", flush=True)
    for weight in WEIGHTS:
        mean_shift = prob_abs_sum[weight] / prob_cells[weight] if prob_cells[weight] else 0.0
        print(
            f"WAVE_FORWARD_WEIGHT_{weight:.2f}=top1_changed:{top1_changed[weight]}/{complete} "
            f"mean_abs_prob_shift:{mean_shift:.6f} max_prob_shift:{max_prob_shift[weight]:.6f}",
            flush=True,
        )
    if complete == 0:
        print("WAVE_FORWARD_RESULT=PASS_NO_FINAL_SNAPSHOTS_YET", flush=True)
    else:
        print("WAVE_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
