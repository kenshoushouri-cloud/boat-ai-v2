# -*- coding: utf-8 -*-
"""Forward Shadow collector for train-stable wave x venue x lane effects.

Safety:
- default WRITE_MODE=dryrun
- commit mode requires explicit COLLECTION_RACE_IDS
- never changes v2_realtime_decisions
- never sends LINE
- stores all three fixed observation weights (0.25/0.50/1.00)
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from db_pg import execute, fetch_all, upsert_rows
import v22_realtime_decision_engine_pg as decision
from wave_venue_lane_profile_pg import PROFILE_VERSION, load_profile, wave_bucket

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-22 wave-vl-final-shadow-v1"
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
WRITE_MODE = os.getenv("WAVE_SHADOW_WRITE_MODE", "dryrun").strip().lower()
ENABLED = os.getenv("WAVE_SHADOW_ENABLED", "1").strip().lower() in {"1","true","yes","on"}
COLLECTION_RAW = (os.getenv("COLLECTION_RACE_IDS") or os.getenv("TARGET_RACE_IDS") or "").strip()
COLLECTION_RACE_IDS = {x.strip() for x in COLLECTION_RAW.split(",") if x.strip()}
WEIGHTS = (0.25, 0.50, 1.00)

DDL = [
    "create table if not exists v2_wave_venue_lane_final_shadow (id bigserial primary key);",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists race_id text;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists race_date date;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists venue_code text;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists race_no integer;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists snapshot_label text;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists snapshot_at timestamptz;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists profile_version text;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists weight numeric;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists wave_height_cm numeric;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists wave_bucket text;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists effect_lanes integer;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists baseline_top_lane integer;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists adjusted_top_lane integer;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists baseline_top_prob numeric;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists adjusted_top_prob numeric;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists baseline_probs jsonb;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists adjusted_probs jsonb;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists effect_logit_by_lane jsonb;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists raw jsonb;",
    "alter table v2_wave_venue_lane_final_shadow add column if not exists updated_at timestamptz;",
    "create unique index if not exists uq_v2_wave_vl_final_shadow on v2_wave_venue_lane_final_shadow (race_id,snapshot_label,profile_version,weight);",
    "create index if not exists ix_v2_wave_vl_final_shadow_date on v2_wave_venue_lane_final_shadow (race_date,profile_version);",
]


def ensure_schema() -> None:
    for q in DDL:
        execute(q)


def softmax(raw: dict[int, float]) -> dict[int, float]:
    vals = {k: math.exp(v / decision.PROB_TEMP) for k, v in raw.items()}
    total = sum(vals.values())
    return {k: vals[k] / total for k in vals}


def load_live_rows() -> list[dict[str, Any]]:
    rows = fetch_all(
        """
        select r.race_id,r.race_date,r.venue_id,r.race_no,e.*,
               w.wave_height_cm,w.snapshot_at
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        join v2_realtime_weather_snapshots w
          on w.race_id=r.race_id and w.snapshot_label=%s
        where r.race_date=%s and w.wave_height_cm is not null
        order by r.race_id,e.lane
        """,
        (SNAPSHOT_LABEL, TARGET_DATE),
    )
    if COLLECTION_RACE_IDS:
        rows = [r for r in rows if str(r.get("race_id") or "") in COLLECTION_RACE_IDS]
    return rows


def build_rows(profile: dict, live_rows: list[dict[str, Any]]) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    for row in live_rows:
        grouped[str(row.get("race_id") or "")].append(row)

    out = []
    complete = 0
    covered = 0
    changed = {w: 0 for w in WEIGHTS}
    for rid, rr in grouped.items():
        if len(rr) != 6:
            continue
        lanes = {int(x.get("lane") or 0): x for x in rr}
        if set(lanes) != {1,2,3,4,5,6}:
            continue
        venue = str(rr[0].get("venue_id") or "").zfill(2)
        wave = rr[0].get("wave_height_cm")
        if wave is None:
            continue
        bucket = wave_bucket(wave)
        raw = {lane: decision._lane_raw_strength(lanes[lane], lane, venue) for lane in range(1,7)}
        bp = softmax(raw)
        base_top = max(bp, key=bp.get)
        effects = {lane: profile.get((venue, lane, bucket)) for lane in range(1,7)}
        effect_map = {str(lane): float(e["delta_logit"]) for lane,e in effects.items() if e}
        effect_count = len(effect_map)
        complete += 1
        if not effect_count:
            continue
        covered += 1

        for weight in WEIGHTS:
            adj = dict(raw)
            for lane,effect in effects.items():
                if effect:
                    adj[lane] += float(effect["delta_logit"]) * decision.PROB_TEMP * weight
            ap = softmax(adj)
            adj_top = max(ap, key=ap.get)
            changed[weight] += int(adj_top != base_top)
            out.append({
                "race_id": rid,
                "race_date": rr[0].get("race_date"),
                "venue_code": venue,
                "race_no": int(rr[0].get("race_no") or 0),
                "snapshot_label": SNAPSHOT_LABEL,
                "snapshot_at": rr[0].get("snapshot_at"),
                "profile_version": PROFILE_VERSION,
                "weight": weight,
                "wave_height_cm": float(wave),
                "wave_bucket": bucket,
                "effect_lanes": effect_count,
                "baseline_top_lane": base_top,
                "adjusted_top_lane": adj_top,
                "baseline_top_prob": float(bp[base_top]),
                "adjusted_top_prob": float(ap[adj_top]),
                "baseline_probs": {str(k): float(v) for k,v in bp.items()},
                "adjusted_probs": {str(k): float(v) for k,v in ap.items()},
                "effect_logit_by_lane": effect_map,
                "raw": {
                    "collector_version": VERSION,
                    "profile_groups": len(profile),
                    "write_mode": WRITE_MODE,
                },
                "updated_at": datetime.now(JST),
            })
    return out, {"complete": complete, "covered": covered, "changed": changed}


def main() -> None:
    print(f"✅ collect_wave_venue_lane_final_shadow_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} WRITE_MODE={WRITE_MODE}", flush=True)
    print(f"COLLECTION_RACE_IDS={len(COLLECTION_RACE_IDS)} PROFILE_VERSION={PROFILE_VERSION}", flush=True)
    print("Shadow専用。LINE・本番BUY/WATCH/SKIP・購入処理は変更しません。", flush=True)
    if not ENABLED:
        print("WAVE_SHADOW_ENABLED=0: skip", flush=True)
        return
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")
    if WRITE_MODE not in {"dryrun", "commit"}:
        raise RuntimeError("WAVE_SHADOW_WRITE_MODE must be dryrun or commit")
    if WRITE_MODE == "commit" and not COLLECTION_RACE_IDS:
        raise RuntimeError("commit mode requires explicit COLLECTION_RACE_IDS")

    profile = load_profile()
    live = load_live_rows()
    rows, stats = build_rows(profile, live)
    print(f"WAVE_SHADOW_PROFILE_GROUPS={len(profile)}", flush=True)
    print(f"WAVE_SHADOW_LIVE_ROWS={len(live)}", flush=True)
    print(f"WAVE_SHADOW_COMPLETE_RACES={stats['complete']}", flush=True)
    print(f"WAVE_SHADOW_COVERED_RACES={stats['covered']}", flush=True)
    print(f"WAVE_SHADOW_OUTPUT_ROWS={len(rows)}", flush=True)
    for w in WEIGHTS:
        print(f"WAVE_SHADOW_TOP1_CHANGED_{w:.2f}={stats['changed'][w]}", flush=True)

    if WRITE_MODE == "dryrun":
        print("WAVE_SHADOW_RESULT=PASS_DRYRUN_NO_WRITES", flush=True)
        return

    ensure_schema()
    saved = upsert_rows(
        "v2_wave_venue_lane_final_shadow",
        rows,
        ["race_id","snapshot_label","profile_version","weight"],
    ) if rows else 0
    print(f"WAVE_SHADOW_SAVED_ROWS={saved}", flush=True)
    print("WAVE_SHADOW_RESULT=PASS_COMMIT", flush=True)


if __name__ == "__main__":
    main()
