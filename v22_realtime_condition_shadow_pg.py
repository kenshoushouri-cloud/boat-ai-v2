# -*- coding: utf-8 -*-
"""
v22_realtime_condition_shadow_pg.py

当日コンディション情報を加えたshadow順位を保存します。
本番判定・LINE通知・購入処理には影響しません。

使用項目:
- 調整重量
- 前走ST
- 前走着順
- 前走進入
- 部品交換
- 新プロペラ
- 安定板
- 進入固定

Start Command:
    python -u v22_realtime_condition_shadow_pg.py
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import execute, fetch_all, upsert_rows
import v22_realtime_decision_engine_pg as base
import v22_racer_course_shadow_pg as course_shadow

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
TARGET_RACE_IDS_RAW = os.getenv("TARGET_RACE_IDS", "").strip()
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
REALTIME_WEIGHT = float(os.getenv("REALTIME_CONDITION_SHADOW_WEIGHT", "0.20"))
SAVE_SHADOW = os.getenv("SAVE_REALTIME_CONDITION_SHADOW", "1").strip().lower() not in {"0","false","no"}
TARGET_RACE_IDS = [x.strip() for x in TARGET_RACE_IDS_RAW.split(",") if x.strip()]


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return d if v is None or v == "" else float(v)
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return d if v is None or v == "" else int(float(v))
    except Exception:
        return d


def ensure_schema() -> None:
    sqls = [
        "create table if not exists v2_realtime_condition_shadow_rankings (id bigserial primary key);",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists race_id text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists race_date date;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists venue_id text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists race_no integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists snapshot_label text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists selector_mode text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists ticket text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists odds numeric;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists market_rank integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists baseline_prob numeric;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists baseline_prob_rank integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists shadow_prob numeric;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists shadow_prob_rank integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists rank_delta integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists baseline_candidate boolean;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists shadow_candidate boolean;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists candidate_change text;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists condition_coverage integer;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists realtime_weight numeric;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists raw jsonb;",
        "alter table v2_realtime_condition_shadow_rankings add column if not exists updated_at timestamptz;",
        "create unique index if not exists uq_v2_rt_condition_shadow on v2_realtime_condition_shadow_rankings (race_id,snapshot_label,selector_mode,ticket);",
    ]
    for sql in sqls:
        execute(sql)


def target_races() -> List[Dict[str, Any]]:
    if TARGET_RACE_IDS:
        return fetch_all(
            "select * from v2_races where race_id=any(%s) order by venue_id,race_no;",
            (TARGET_RACE_IDS,),
        )
    return fetch_all(
        "select * from v2_races where race_date=%s order by venue_id,race_no;",
        (TARGET_DATE,),
    )


def group_rows(table: str, race_ids: List[str], extra: str = "") -> Dict[str, List[Dict[str, Any]]]:
    if not race_ids:
        return {}
    rows = fetch_all(
        f"select * from {table} where race_id=any(%s) {extra};",
        (race_ids,),
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


def condition_adjustment(row: Dict[str, Any], race_row: Dict[str, Any]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    adj = sf(row.get("adjustment_weight_kg"))
    if adj >= 2.0:
        score -= 0.20
        reasons.append(f"調整重量{adj:g}")
    elif adj >= 1.0:
        score -= 0.10
        reasons.append(f"調整重量{adj:g}")

    if row.get("previous_st") is not None:
        st = sf(row.get("previous_st"), 0.18)
        if st <= 0.10:
            score += 0.20
        elif st <= 0.15:
            score += 0.10
        elif st >= 0.25:
            score -= 0.15
        elif st >= 0.20:
            score -= 0.08
        reasons.append(f"前走ST{st:.2f}")

    finish = si(row.get("previous_finish"))
    if finish == 1:
        score += 0.10
    elif finish == 2:
        score += 0.05
    elif finish >= 5:
        score -= 0.05
    if finish:
        reasons.append(f"前走着{finish}")

    if si(row.get("previous_course")) == si(row.get("lane")) and si(row.get("lane")):
        score += 0.03
        reasons.append("前走同コース")

    parts = row.get("parts_replacements") or []
    if parts:
        score -= 0.08
        reasons.append(f"部品交換{len(parts)}")

    if row.get("is_new_propeller"):
        score -= 0.12
        reasons.append("新プロペラ")

    if race_row.get("is_stabilizer_used"):
        score *= 0.80
        reasons.append("安定板")
    if race_row.get("is_fixed_entry"):
        score += 0.02
        reasons.append("進入固定")

    return score * REALTIME_WEIGHT, reasons


def rank_shadow(
    entries: List[Dict[str, Any]],
    venue_id: str,
    odds: Dict[str, float],
    racer_conditions: Dict[int, Dict[str, Any]],
    race_condition: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], int, Dict[int, Any]]:
    by = base._entry_by_lane(entries)
    raw: Dict[int, float] = {}
    details: Dict[int, Any] = {}
    coverage = 0

    for lane in range(1, 7):
        cond = racer_conditions.get(lane)
        if cond:
            coverage += 1
        adjustment, reasons = condition_adjustment(cond or {}, race_condition or {})
        raw[lane] = base._lane_raw_strength(by[lane], lane, venue_id) + adjustment
        details[lane] = {"adjustment": adjustment, "reasons": reasons}

    weights = {lane: math.exp(raw[lane] / base.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    rows: List[Dict[str, Any]] = []

    for a in range(1, 7):
        pa = weights[a] / total
        tb = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / tb
            tc = tb - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                ticket = f"{a}-{b}-{c}"
                odd = sf(odds.get(ticket))
                if odd <= 0:
                    continue
                prob = pa * pb * (weights[c] / tc)
                rows.append({"ticket": ticket, "prob": prob, "odds": odd})

    for i, row in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), 1):
        row["market_rank"] = i
    for i, row in enumerate(sorted(rows, key=lambda x: x["prob"], reverse=True), 1):
        row["prob_rank"] = i
    return rows, coverage, details


def is_candidate(row: Dict[str, Any]) -> bool:
    return (
        11 <= si(row.get("prob_rank"), 999) <= 20
        and si(row.get("market_rank"), 999) == 1
        and 3.0 <= sf(row.get("odds")) < 5.0
    )


def main() -> None:
    print("✅ v22_realtime_condition_shadow_pg.py VERSION 2026-07-15 realtime-condition-shadow-v1", flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    ensure_schema()

    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} REALTIME_WEIGHT={REALTIME_WEIGHT}",
        flush=True,
    )
    print("本番判定・LINE通知・購入処理は変更しません。", flush=True)

    races = target_races()
    race_ids = [str(r.get("race_id")) for r in races]
    entries_by = group_rows("v2_race_entries", race_ids)
    odds_by = fetch_odds(race_ids)
    cond_rows = group_rows(
        "v2_realtime_racer_condition_snapshots",
        race_ids,
        f"and snapshot_label='{SNAPSHOT_LABEL}'",
    )
    cond_by = {
        rid: {si(row.get("lane")): row for row in rows}
        for rid, rows in cond_rows.items()
    }
    race_cond_rows = group_rows(
        "v2_realtime_race_condition_snapshots",
        race_ids,
        f"and snapshot_label='{SNAPSHOT_LABEL}'",
    )
    race_cond_by = {
        rid: rows[-1] for rid, rows in race_cond_rows.items() if rows
    }

    saved_rows: List[Dict[str, Any]] = []
    ready = skipped_entries = skipped_odds = full_coverage = 0
    improved = worsened = same = added = removed = kept = none = 0
    now_iso = datetime.now(JST).isoformat()

    for race in races:
        rid = str(race.get("race_id"))
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})

        if len(base._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue
        if len(odds) < 100:
            skipped_odds += 1
            continue

        ready += 1
        baseline = base._rank_candidates(entries, venue, odds)
        shadow, coverage, details = rank_shadow(
            entries, venue, odds, cond_by.get(rid, {}), race_cond_by.get(rid, {})
        )
        if coverage == 6:
            full_coverage += 1

        bmap = {r["ticket"]: r for r in baseline}
        smap = {r["ticket"]: r for r in shadow}

        for ticket, b in bmap.items():
            s = smap.get(ticket)
            if not s:
                continue
            br, sr = si(b.get("prob_rank"), 999), si(s.get("prob_rank"), 999)
            delta = br - sr
            improved += delta > 0
            worsened += delta < 0
            same += delta == 0

            bc, sc = is_candidate(b), is_candidate(s)
            change = "kept" if bc and sc else "removed" if bc else "added" if sc else "none"
            added += change == "added"
            removed += change == "removed"
            kept += change == "kept"
            none += change == "none"

            saved_rows.append({
                "race_id": rid,
                "race_date": TARGET_DATE,
                "venue_id": venue,
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
                "condition_coverage": coverage,
                "realtime_weight": REALTIME_WEIGHT,
                "raw": {"lane_details": details},
                "updated_at": now_iso,
            })

    saved = upsert_rows(
        "v2_realtime_condition_shadow_rankings",
        saved_rows,
        ["race_id", "snapshot_label", "selector_mode", "ticket"],
    ) if SAVE_SHADOW and saved_rows else 0

    print("=== realtime condition shadow summary ===", flush=True)
    print(f"races={len(races)} ready_races={ready}", flush=True)
    print(f"skipped_entries={skipped_entries} skipped_odds={skipped_odds}", flush=True)
    print(f"full_condition_coverage={full_coverage}/{ready}", flush=True)
    print(f"saved_rows={saved}", flush=True)
    print(f"rank_improved={improved} rank_worsened={worsened} rank_same={same}", flush=True)
    print(
        f"candidate_added={added} candidate_removed={removed} "
        f"candidate_kept={kept} candidate_none={none}",
        flush=True,
    )
    print("=== realtime condition shadow finished ===", flush=True)


if __name__ == "__main__":
    main()