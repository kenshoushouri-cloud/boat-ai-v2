# -*- coding: utf-8 -*-
"""
v22_exhibition_shadow_pg.py

展示タイム補正版を、本番BUY/WATCH/SKIP判定へ影響させず裏側保存します。

処理:
- v2_race_entries と final_ab の直前オッズ・展示情報を読み込む
- 現行モデルのprob_rankを再計算
- 展示タイム順位 weight=0.20 を加えたshadow_prob_rankを計算
- 各レースの市場1番人気について、現行B候補/展示補正B候補を比較
- v2_exhibition_shadow_decisions にupsert

本番の v2_realtime_decisions、LINE通知、recommendation は変更しません。

Railway Start Command:
    python -u v22_exhibition_shadow_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    EXHIBITION_SHADOW_WEIGHT=0.20
    MIN_ODDS_ROWS=100
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

from db_pg import execute, fetch_all, upsert_rows

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
EXHIBITION_SHADOW_WEIGHT = float(os.getenv("EXHIBITION_SHADOW_WEIGHT", "0.20"))
MIN_ODDS_ROWS = int(os.getenv("MIN_ODDS_ROWS", "100"))
TARGET_RACE_IDS = {x.strip() for x in os.getenv("TARGET_RACE_IDS", "").split(",") if x.strip()}
PROB_TEMP = float(os.getenv("PROB_TEMP", "2.20"))

CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _norm_ticket(ticket: Any) -> str:
    s = unicodedata.normalize("NFKC", str(ticket or ""))
    nums = re.findall(r"[1-6]", s)
    return f"{nums[0]}-{nums[1]}-{nums[2]}" if len(nums) >= 3 else ""


def _rank_centered(rank: int) -> float:
    return {
        1: 1.0,
        2: 0.6,
        3: 0.2,
        4: -0.2,
        5: -0.6,
        6: -1.0,
    }.get(rank, 0.0)



def _json_safe(value: Any) -> Any:
    """JSONB保存前にDecimal・日時などをJSON化可能な値へ変換する。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)

def _ensure_schema() -> None:
    ddl = [
        """
        create table if not exists v2_exhibition_shadow_decisions (
            id bigserial primary key
        );
        """,
        "alter table v2_exhibition_shadow_decisions add column if not exists race_id text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists race_date date;",
        "alter table v2_exhibition_shadow_decisions add column if not exists venue_id text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists race_no integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists snapshot_label text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists selector_mode text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists ticket text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists odds numeric;",
        "alter table v2_exhibition_shadow_decisions add column if not exists market_rank integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists baseline_prob_rank integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists shadow_prob_rank integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists rank_delta integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists baseline_candidate boolean;",
        "alter table v2_exhibition_shadow_decisions add column if not exists shadow_candidate boolean;",
        "alter table v2_exhibition_shadow_decisions add column if not exists candidate_change text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists exhibition_weight numeric;",
        "alter table v2_exhibition_shadow_decisions add column if not exists head_lane integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists head_exhibition_rank integer;",
        "alter table v2_exhibition_shadow_decisions add column if not exists shadow_version text;",
        "alter table v2_exhibition_shadow_decisions add column if not exists raw jsonb;",
        "alter table v2_exhibition_shadow_decisions add column if not exists created_at timestamptz default now();",
        "alter table v2_exhibition_shadow_decisions add column if not exists updated_at timestamptz;",
        """
        create unique index if not exists uq_v2_exhibition_shadow_main
        on v2_exhibition_shadow_decisions
        (race_id, snapshot_label, selector_mode, ticket);
        """,
        "create index if not exists idx_v2_exhibition_shadow_date on v2_exhibition_shadow_decisions (race_date);",
        "create index if not exists idx_v2_exhibition_shadow_change on v2_exhibition_shadow_decisions (candidate_change);",
    ]
    for sql in ddl:
        execute(sql)


def _lane_strength(
    entry: Dict[str, Any],
    lane: int,
    venue_id: str,
    exhibition_rank: int = 0,
    exhibition_weight: float = 0.0,
) -> float:
    cls = _safe_int(entry.get("racer_class"), 2)
    cls_w = CLASS_WEIGHT.get(cls, 0.55)
    win_rate = _safe_float(entry.get("national_win_rate"), 0.0)
    nat2 = _safe_float(entry.get("national_place2_rate"), 32.0)
    loc2 = _safe_float(entry.get("local_place2_rate"), 30.0)

    # 現行v22と同じく、保存済み実値を使用。欠損時のみ既定値。
    mot2 = _safe_float(entry.get("motor_place2_rate"), 33.0)
    boat2 = _safe_float(entry.get("boat_place2_rate"), 34.0)

    avg_st = _safe_float(entry.get("avg_st") or entry.get("average_st"), 0.18)
    course = VENUE_COURSE_BIAS.get(venue_id, DEFAULT_COURSE_BIAS).get(
        lane, DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))

    return (
        cls_w
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course * 0.22
        + exhibition_weight * _rank_centered(exhibition_rank)
    )


def _prob_ranks(
    entries: List[Dict[str, Any]],
    exhibition_by_lane: Dict[int, Dict[str, Any]],
    venue_id: str,
    exhibition_weight: float,
) -> Dict[str, int]:
    by_lane = {
        _safe_int(e.get("lane")): e
        for e in entries
        if 1 <= _safe_int(e.get("lane")) <= 6
    }
    if len(by_lane) != 6:
        return {}

    raw: Dict[int, float] = {}
    for lane in range(1, 7):
        ex_rank = _safe_int(
            exhibition_by_lane.get(lane, {}).get("exhibition_time_rank"),
            0,
        )
        raw[lane] = _lane_strength(
            by_lane[lane],
            lane,
            venue_id,
            ex_rank,
            exhibition_weight,
        )

    weights = {lane: math.exp(raw[lane] / PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    probs: Dict[str, float] = {}

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
                probs[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / total_c)

    return {
        ticket: rank
        for rank, (ticket, _) in enumerate(
            sorted(probs.items(), key=lambda x: x[1], reverse=True),
            start=1,
        )
    }


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    _ensure_schema()

    print("✅ v22_exhibition_shadow_pg.py VERSION 2026-07-15 shadow-v3-target-race-ids", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} "
        f"EXHIBITION_SHADOW_WEIGHT={EXHIBITION_SHADOW_WEIGHT}",
        flush=True,
    )
    print("本番判定・LINE通知は変更しません。", flush=True)

    if not TARGET_RACE_IDS:
        print("今回の締切ウィンドウ対象は0件です。shadow保存を終了します。", flush=True)
        return
    print(f"TARGET_RACE_IDS enabled: {len(TARGET_RACE_IDS)} races", flush=True)

    races = fetch_all(
        """
        select race_id, race_date,
               coalesce(venue_id, venue_code) as venue_id,
               race_no
        from v2_races
        where race_date=%s
          and race_id = any(%s)
        order by venue_id, race_no;
        """,
        (TARGET_DATE, list(TARGET_RACE_IDS)),
    )

    entries_rows = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id = any(%s)
        order by race_id, lane;
        """,
        (list(TARGET_RACE_IDS),),
    )

    exhibition_rows = fetch_all(
        """
        select race_id, lane, exhibition_time_rank,
               exhibition_time, exhibition_time_diff
        from v2_realtime_exhibition_snapshots
        where race_date=%s and snapshot_label=%s
          and race_id = any(%s)
        order by race_id, lane;
        """,
        (TARGET_DATE, SNAPSHOT_LABEL, list(TARGET_RACE_IDS)),
    )

    odds_rows = fetch_all(
        """
        select race_id, ticket, odds, market_rank
        from v2_realtime_odds_snapshots
        where race_date=%s and snapshot_label=%s
          and race_id = any(%s)
        order by race_id, market_rank nulls last, odds;
        """,
        (TARGET_DATE, SNAPSHOT_LABEL, list(TARGET_RACE_IDS)),
    )

    entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries_rows:
        entries_by_race.setdefault(str(row.get("race_id")), []).append(row)

    exhibition_by_race: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for row in exhibition_rows:
        rid = str(row.get("race_id"))
        lane = _safe_int(row.get("lane"))
        if rid and 1 <= lane <= 6:
            exhibition_by_race.setdefault(rid, {})[lane] = row

    odds_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for row in odds_rows:
        rid = str(row.get("race_id"))
        ticket = _norm_ticket(row.get("ticket"))
        odds = _safe_float(row.get("odds"))
        if rid and ticket and odds > 0:
            x = dict(row)
            x["ticket"] = ticket
            x["odds"] = odds
            odds_by_race.setdefault(rid, []).append(x)

    save_rows: List[Dict[str, Any]] = []
    skipped_entries = 0
    skipped_exhibition = 0
    skipped_odds = 0

    for race in races:
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id") or "").zfill(2)
        race_no = _safe_int(race.get("race_no"))
        entries = entries_by_race.get(rid, [])
        exhibition = exhibition_by_race.get(rid, {})
        odds = odds_by_race.get(rid, [])

        if len(entries) != 6:
            skipped_entries += 1
            continue
        if len(exhibition) != 6:
            skipped_exhibition += 1
            continue
        if len(odds) < MIN_ODDS_ROWS:
            skipped_odds += 1
            continue

        baseline_ranks = _prob_ranks(entries, exhibition, venue_id, 0.0)
        shadow_ranks = _prob_ranks(
            entries,
            exhibition,
            venue_id,
            EXHIBITION_SHADOW_WEIGHT,
        )
        if not baseline_ranks or not shadow_ranks:
            continue

        favorite = min(
            odds,
            key=lambda x: (
                _safe_int(x.get("market_rank"), 999),
                _safe_float(x.get("odds"), 9999.0),
            ),
        )
        ticket = favorite["ticket"]
        favorite_odds = _safe_float(favorite.get("odds"))
        market_rank = _safe_int(favorite.get("market_rank"), 1)

        baseline_rank = baseline_ranks.get(ticket, 999)
        shadow_rank = shadow_ranks.get(ticket, 999)

        baseline_candidate = (
            11 <= baseline_rank <= 20
            and market_rank == 1
            and 3.0 <= favorite_odds < 5.0
            and race_no <= 9
        )
        shadow_candidate = (
            11 <= shadow_rank <= 20
            and market_rank == 1
            and 3.0 <= favorite_odds < 5.0
            and race_no <= 9
        )

        if baseline_candidate and not shadow_candidate:
            change = "removed"
        elif not baseline_candidate and shadow_candidate:
            change = "added"
        elif baseline_candidate and shadow_candidate:
            change = "kept"
        else:
            change = "none"

        head_lane = _safe_int(ticket.split("-")[0], 0)
        head_ex_rank = _safe_int(
            exhibition.get(head_lane, {}).get("exhibition_time_rank"),
            0,
        )

        save_rows.append({
            "race_id": rid,
            "race_date": TARGET_DATE,
            "venue_id": venue_id,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "selector_mode": SELECTOR_MODE,
            "ticket": ticket,
            "odds": favorite_odds,
            "market_rank": market_rank,
            "baseline_prob_rank": baseline_rank,
            "shadow_prob_rank": shadow_rank,
            # 正なら展示補正により順位上昇
            "rank_delta": baseline_rank - shadow_rank,
            "baseline_candidate": baseline_candidate,
            "shadow_candidate": shadow_candidate,
            "candidate_change": change,
            "exhibition_weight": EXHIBITION_SHADOW_WEIGHT,
            "head_lane": head_lane,
            "head_exhibition_rank": head_ex_rank,
            "shadow_version": "exhibition_time_rank_w020_v1",
            "raw": _json_safe({
                "baseline_prob_rank": baseline_rank,
                "shadow_prob_rank": shadow_rank,
                "head_exhibition": exhibition.get(head_lane, {}),
                "production_decision_unchanged": True,
            }),
            "updated_at": datetime.now(JST).isoformat(),
        })

    saved = upsert_rows(
        "v2_exhibition_shadow_decisions",
        save_rows,
        ["race_id", "snapshot_label", "selector_mode", "ticket"],
    ) if save_rows else 0

    changes = {"added": 0, "removed": 0, "kept": 0, "none": 0}
    improved = worsened = same = 0
    for row in save_rows:
        changes[row["candidate_change"]] += 1
        delta = _safe_int(row.get("rank_delta"))
        if delta > 0:
            improved += 1
        elif delta < 0:
            worsened += 1
        else:
            same += 1

    print("\n=== exhibition shadow summary ===", flush=True)
    print(f"races={len(races)} saved={saved}", flush=True)
    print(
        f"skipped_entries={skipped_entries} "
        f"skipped_exhibition={skipped_exhibition} skipped_odds={skipped_odds}",
        flush=True,
    )
    print(
        f"rank_improved={improved} rank_worsened={worsened} rank_same={same}",
        flush=True,
    )
    print(
        f"candidate_added={changes['added']} "
        f"candidate_removed={changes['removed']} "
        f"candidate_kept={changes['kept']} "
        f"candidate_none={changes['none']}",
        flush=True,
    )

    changed_rows = [
        row for row in save_rows
        if row["candidate_change"] in ("added", "removed")
    ]
    print("\n--- candidate change samples ---", flush=True)
    for row in changed_rows[:20]:
        print(
            f"{row['race_id']} {row['ticket']} odds={row['odds']:.1f} "
            f"base_rank={row['baseline_prob_rank']} "
            f"shadow_rank={row['shadow_prob_rank']} "
            f"change={row['candidate_change']} "
            f"head_ex_rank={row['head_exhibition_rank']}",
            flush=True,
        )

    print("=== exhibition shadow finished ===", flush=True)


if __name__ == "__main__":
    main()