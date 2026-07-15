# -*- coding: utf-8 -*-
"""
v22_previous_st_fixed_shadow_pg.py

固定済み前走ST設定を使い、現行順位とのshadow比較を保存します。

固定設定（7/15探索結果）:
- 前走ST <= 0.08: +0.08
- 前走ST >= 0.18: -0.18

重要:
- 本番判定・LINE通知・購入処理は変更しません。
- TARGET_RACE_IDS指定時は、その対象レースだけ処理します。
- 日付外検証用なので、設定値は探索せず固定します。

Start Command:
    python -u v22_previous_st_fixed_shadow_pg.py
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import execute, fetch_all, upsert_rows
import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
TARGET_RACE_IDS_RAW = os.getenv("TARGET_RACE_IDS", "").strip()
TARGET_RACE_IDS = [x.strip() for x in TARGET_RACE_IDS_RAW.split(",") if x.strip()]
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"

FAST_THRESHOLD = float(os.getenv("PREVIOUS_ST_FAST_THRESHOLD", "0.08"))
FAST_BONUS = float(os.getenv("PREVIOUS_ST_FAST_BONUS", "0.08"))
SLOW_THRESHOLD = float(os.getenv("PREVIOUS_ST_SLOW_THRESHOLD", "0.18"))
SLOW_PENALTY = float(os.getenv("PREVIOUS_ST_SLOW_PENALTY", "0.18"))

SAVE_SHADOW = os.getenv("SAVE_PREVIOUS_ST_SHADOW", "1").strip().lower() not in {
    "0", "false", "no"
}


def sf(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def si(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def ensure_schema() -> None:
    sqls = [
        "create table if not exists v2_previous_st_shadow_rankings (id bigserial primary key);",
        "alter table v2_previous_st_shadow_rankings add column if not exists race_id text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists race_date date;",
        "alter table v2_previous_st_shadow_rankings add column if not exists venue_id text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists race_no integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists snapshot_label text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists selector_mode text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists ticket text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists odds numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists market_rank integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists baseline_prob numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists baseline_prob_rank integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists shadow_prob numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists shadow_prob_rank integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists rank_delta integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists baseline_candidate boolean;",
        "alter table v2_previous_st_shadow_rankings add column if not exists shadow_candidate boolean;",
        "alter table v2_previous_st_shadow_rankings add column if not exists candidate_change text;",
        "alter table v2_previous_st_shadow_rankings add column if not exists condition_coverage integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists previous_st_filled integer;",
        "alter table v2_previous_st_shadow_rankings add column if not exists fast_threshold numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists fast_bonus numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists slow_threshold numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists slow_penalty numeric;",
        "alter table v2_previous_st_shadow_rankings add column if not exists raw jsonb;",
        "alter table v2_previous_st_shadow_rankings add column if not exists updated_at timestamptz;",
        "create unique index if not exists uq_v2_previous_st_shadow on v2_previous_st_shadow_rankings (race_id,snapshot_label,selector_mode,ticket);",
        "create index if not exists ix_v2_previous_st_shadow_date on v2_previous_st_shadow_rankings (race_date);",
    ]
    for sql in sqls:
        execute(sql)


def target_races() -> List[Dict[str, Any]]:
    if TARGET_RACE_IDS_RAW and not TARGET_RACE_IDS:
        return []
    if TARGET_RACE_IDS:
        return fetch_all(
            "select * from v2_races where race_id=any(%s) order by venue_id,race_no;",
            (TARGET_RACE_IDS,),
        )
    return fetch_all(
        "select * from v2_races where race_date=%s order by venue_id,race_no;",
        (TARGET_DATE,),
    )


def group_rows(table: str, race_ids: List[str], extra_sql: str = "", params=()) -> Dict[str, List[Dict[str, Any]]]:
    if not race_ids:
        return {}
    rows = fetch_all(
        f"select * from {table} where race_id=any(%s) {extra_sql};",
        (race_ids, *params),
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.get("race_id")), []).append(row)
    return out


def fetch_odds(race_ids: List[str]) -> Dict[str, Dict[str, float]]:
    if not race_ids:
        return {}
    rows = fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta where race_id=any(%s);",
        (race_ids,),
    )
    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        ticket = base._norm_ticket(row.get("ticket"))
        odds = sf(row.get("odds"))
        if ticket and odds > 0:
            out.setdefault(str(row.get("race_id")), {})[ticket] = odds
    return out


def rank_shadow(
    entries: List[Dict[str, Any]],
    venue_id: str,
    odds: Dict[str, float],
    conditions: Dict[int, Dict[str, Any]],
):
    by_lane = base._entry_by_lane(entries)
    raw: Dict[int, float] = {}
    lane_details: Dict[int, Dict[str, Any]] = {}
    previous_st_filled = 0

    for lane in range(1, 7):
        score = base._lane_raw_strength(by_lane[lane], lane, venue_id)
        cond = conditions.get(lane, {})
        previous_st = cond.get("previous_st")
        adjustment = 0.0

        if previous_st is not None:
            previous_st_filled += 1
            st = sf(previous_st, 0.18)
            if st <= FAST_THRESHOLD:
                adjustment = FAST_BONUS
            elif st >= SLOW_THRESHOLD:
                adjustment = -SLOW_PENALTY
            score += adjustment
            lane_details[lane] = {
                "previous_st": st,
                "adjustment": adjustment,
            }
        else:
            lane_details[lane] = {
                "previous_st": None,
                "adjustment": 0.0,
            }

        raw[lane] = score

    weights = {lane: math.exp(raw[lane] / base.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    rows = []

    for a in range(1, 7):
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                ticket = f"{a}-{b}-{c}"
                odd = sf(odds.get(ticket))
                if odd <= 0:
                    continue
                prob = pa * pb * (weights[c] / total_c)
                rows.append({"ticket": ticket, "prob": prob, "odds": odd})

    for i, row in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), 1):
        row["market_rank"] = i
    for i, row in enumerate(sorted(rows, key=lambda x: x["prob"], reverse=True), 1):
        row["prob_rank"] = i

    return rows, previous_st_filled, lane_details


def is_candidate(row: Dict[str, Any]) -> bool:
    return (
        11 <= si(row.get("prob_rank"), 999) <= 20
        and si(row.get("market_rank"), 999) == 1
        and 3.0 <= sf(row.get("odds")) < 5.0
    )


def main() -> None:
    print(
        "✅ v22_previous_st_fixed_shadow_pg.py "
        "VERSION 2026-07-16 fixed-oos-v1",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    ensure_schema()

    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE}",
        flush=True,
    )
    print(
        f"FIXED_CONFIG fast<={FAST_THRESHOLD:.2f} bonus=+{FAST_BONUS:.2f} "
        f"slow>={SLOW_THRESHOLD:.2f} penalty=-{SLOW_PENALTY:.2f}",
        flush=True,
    )
    print("本番判定・LINE通知・購入処理は変更しません。", flush=True)

    races = target_races()
    race_ids = [str(r.get("race_id")) for r in races]
    entries_by = group_rows("v2_race_entries", race_ids)
    odds_by = fetch_odds(race_ids)
    cond_by_rows = group_rows(
        "v2_realtime_racer_condition_snapshots",
        race_ids,
        "and snapshot_label=%s",
        (SNAPSHOT_LABEL,),
    )
    cond_by = {
        rid: {si(row.get("lane")): row for row in rows}
        for rid, rows in cond_by_rows.items()
    }

    save_rows = []
    ready = skipped_entries = skipped_odds = full_condition = st_present_races = 0
    improved = worsened = same = added = removed = kept = none = 0
    now_iso = datetime.now(JST).isoformat()

    for race in races:
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})
        conditions = cond_by.get(rid, {})

        if len(base._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue
        if len(odds) < 100:
            skipped_odds += 1
            continue

        ready += 1
        if len(conditions) == 6:
            full_condition += 1

        baseline = base._rank_candidates(entries, venue_id, odds)
        shadow, st_filled, details = rank_shadow(entries, venue_id, odds, conditions)
        if st_filled > 0:
            st_present_races += 1

        bmap = {row["ticket"]: row for row in baseline}
        smap = {row["ticket"]: row for row in shadow}

        for ticket, b in bmap.items():
            s = smap.get(ticket)
            if not s:
                continue

            br = si(b.get("prob_rank"), 999)
            sr = si(s.get("prob_rank"), 999)
            delta = br - sr
            improved += delta > 0
            worsened += delta < 0
            same += delta == 0

            bc = is_candidate(b)
            sc = is_candidate(s)
            change = "kept" if bc and sc else "removed" if bc else "added" if sc else "none"
            added += change == "added"
            removed += change == "removed"
            kept += change == "kept"
            none += change == "none"

            save_rows.append({
                "race_id": rid,
                "race_date": TARGET_DATE,
                "venue_id": venue_id,
                "race_no": si(race.get("race_no")),
                "snapshot_label": SNAPSHOT_LABEL,
                "selector_mode": SELECTOR_MODE,
                "ticket": ticket,
                "odds": sf(b.get("odds")),
                "market_rank": si(b.get("market_rank"), 999),
                "baseline_prob": sf(b.get("prob")),
                "baseline_prob_rank": br,
                "shadow_prob": sf(s.get("prob")),
                "shadow_prob_rank": sr,
                "rank_delta": delta,
                "baseline_candidate": bc,
                "shadow_candidate": sc,
                "candidate_change": change,
                "condition_coverage": len(conditions),
                "previous_st_filled": st_filled,
                "fast_threshold": FAST_THRESHOLD,
                "fast_bonus": FAST_BONUS,
                "slow_threshold": SLOW_THRESHOLD,
                "slow_penalty": SLOW_PENALTY,
                "raw": {"lane_details": details},
                "updated_at": now_iso,
            })

    saved = (
        upsert_rows(
            "v2_previous_st_shadow_rankings",
            save_rows,
            ["race_id", "snapshot_label", "selector_mode", "ticket"],
        )
        if SAVE_SHADOW and save_rows
        else 0
    )

    print("=== previous ST fixed shadow summary ===", flush=True)
    print(f"races={len(races)} ready_races={ready}", flush=True)
    print(f"skipped_entries={skipped_entries} skipped_odds={skipped_odds}", flush=True)
    print(f"full_condition_coverage={full_condition}/{ready}", flush=True)
    print(f"previous_st_present_races={st_present_races}/{ready}", flush=True)
    print(f"saved_rows={saved}", flush=True)
    print(f"rank_improved={improved} rank_worsened={worsened} rank_same={same}", flush=True)
    print(
        f"candidate_added={added} candidate_removed={removed} "
        f"candidate_kept={kept} candidate_none={none}",
        flush=True,
    )
    print("=== previous ST fixed shadow finished ===", flush=True)


if __name__ == "__main__":
    main()