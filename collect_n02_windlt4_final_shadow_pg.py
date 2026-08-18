# -*- coding: utf-8 -*-
"""
collect_n02_windlt4_final_shadow_pg.py

最終直前データ(final_ab等)を使って、固定済み N02_WIND_LT4 をShadow保存する。

固定条件:
- prob_rank 11-20
- market_rank 2-5
- odds 3.0以上 6.0未満
- race_no 7-10
- EV最大の1点
- wind_speed_m < 4.0
- 風速欠損は不採用

重要:
- LINE通知なし
- v2_realtime_decisions変更なし
- 本番BUY/WATCH/SKIP変更なし
- 購入処理なし
- COLLECTION_RACE_IDS（締切窓内の全レース）を対象にするため、
  既存candidate対象から外れていたR10もShadow検証可能。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db_pg import execute, fetch_all, upsert_rows
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-18 n02-windlt4-variant-shadow-v3"

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
COLLECTION_RACE_IDS_RAW = (
    os.getenv("COLLECTION_RACE_IDS")
    or os.getenv("TARGET_RACE_IDS")
    or ""
).strip()
COLLECTION_RACE_IDS = {
    x.strip() for x in COLLECTION_RACE_IDS_RAW.split(",") if x.strip()
}
ENABLED = os.getenv("N02_WINDLT4_SHADOW_ENABLED", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
MAX_WIND = float(os.getenv("N02_WINDLT4_MAX_WIND", "4.0"))

def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def sf(v: Any, d: Optional[float] = 0.0) -> Optional[float]:
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def ensure_schema() -> None:
    ddl = [
        """
        create table if not exists v2_n02_windlt4_final_shadow (
            id bigserial primary key
        );
        """,
        "alter table v2_n02_windlt4_final_shadow add column if not exists race_id text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists race_date date;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists venue_code text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists race_no integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists snapshot_label text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists rule_id text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists ticket text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists odds numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists prob numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists prob_rank integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists market_rank integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists raw_ev numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists wind_speed_m numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_lane integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_racer_number integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_avg_st numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_motor2 numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists motor2_vs_field numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_motor3 numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists motor3_vs_field numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists head_local3_gap numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists aux_score integer;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists aux_grade text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists course_stats_date date;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists course_top3_rate numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists course_avg_st numeric;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists recommendation text;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists snapshot_at timestamptz;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists raw jsonb;",
        "alter table v2_n02_windlt4_final_shadow add column if not exists updated_at timestamptz;",
        """
        create unique index if not exists uq_v2_n02_windlt4_final_shadow
        on v2_n02_windlt4_final_shadow (race_id, snapshot_label, rule_id);
        """,
        """
        create index if not exists ix_v2_n02_windlt4_final_shadow_date
        on v2_n02_windlt4_final_shadow (race_date, rule_id);
        """,
    ]
    for sql in ddl:
        execute(sql)

def fetch_day():
    day_prefix = TARGET_DATE.replace("-", "")
    next_prefix = (
        datetime.strptime(TARGET_DATE, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date=%s
        order by venue_id,race_no;
        """,
        (TARGET_DATE,),
    )
    if COLLECTION_RACE_IDS:
        races = [
            r for r in races
            if str(r.get("race_id") or "") in COLLECTION_RACE_IDS
        ]
    else:
        races = []

    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane;
        """,
        (day_prefix, next_prefix),
    )
    odds = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id,ticket;
        """,
        (day_prefix, next_prefix),
    )
    weather = fetch_all(
        """
        select *
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label=%s
        order by race_id;
        """,
        (TARGET_DATE, SNAPSHOT_LABEL),
    )

    entries_by: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries:
        entries_by.setdefault(str(row.get("race_id") or ""), []).append(row)

    odds_by: Dict[str, Dict[str, float]] = {}
    for row in odds:
        rid = str(row.get("race_id") or "")
        t = v24._norm_ticket(row.get("ticket"))
        o = sf(row.get("odds"), 0.0) or 0.0
        if rid and t and o > 0:
            odds_by.setdefault(rid, {})[t] = o

    weather_by = {
        str(row.get("race_id") or ""): row
        for row in weather
        if row.get("race_id")
    }

    # Forward Shadow用。各選手についてTARGET_DATE以前の最新コース別snapshotを使う。
    course_rows = fetch_all(
        """
        select distinct on (racer_number, course)
               racer_number, snapshot_date, course, top3_rate, avg_st
        from v2_racer_course_stats_snapshots
        where snapshot_date <= %s
        order by racer_number, course, snapshot_date desc;
        """,
        (TARGET_DATE,),
    )
    course_by = {}
    for row in course_rows:
        rn = si(row.get("racer_number"), 0)
        course = si(row.get("course"), 0)
        if rn > 0 and 1 <= course <= 6:
            course_by[(rn, course)] = row

    return races, entries_by, odds_by, weather_by, course_by

def match_n02(row: Dict[str, Any]) -> bool:
    pr = si(row.get("prob_rank"), 999)
    mr = si(row.get("market_rank"), 999)
    odd = sf(row.get("odds"), 0.0) or 0.0
    return 11 <= pr <= 20 and 2 <= mr <= 5 and 3.0 <= odd < 6.0

def select_ev(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    return max(
        rows,
        key=lambda r: (
            sf(r.get("raw_ev"), 0.0) or 0.0,
            sf(r.get("prob"), 0.0) or 0.0,
        ),
    )


def _valid(v: Any, lo: float, hi: float) -> Optional[float]:
    x = sf(v, None)
    if x is None or not (lo <= x <= hi):
        return None
    return x

def _aux_features(entries: List[Dict[str, Any]], head: int, course_by) -> Dict[str, Any]:
    by = v24._entry_by_lane(entries)
    h = by.get(head)
    if not h:
        return {}

    others = [by[i] for i in range(1, 7) if i != head and i in by]
    if len(others) != 5:
        return {}

    head_avg_st = _valid(h.get("avg_st"), 0.01, 0.60)
    head_motor2 = _valid(h.get("motor_place2_rate"), 0.01, 100.0)
    head_motor3 = _valid(h.get("motor_place3_rate"), 0.01, 100.0)
    head_nat3 = _valid(h.get("national_place3_rate"), 0.01, 100.0)
    head_local3 = _valid(h.get("local_place3_rate"), 0.01, 100.0)

    other_motor2 = [
        _valid(e.get("motor_place2_rate"), 0.01, 100.0)
        for e in others
    ]
    other_motor2 = [x for x in other_motor2 if x is not None]
    other_motor2_mean = (
        sum(other_motor2) / len(other_motor2)
        if len(other_motor2) >= 4 else None
    )

    other_motor3 = [
        _valid(e.get("motor_place3_rate"), 0.01, 100.0)
        for e in others
    ]
    other_motor3 = [x for x in other_motor3 if x is not None]
    other_motor3_mean = (
        sum(other_motor3) / len(other_motor3)
        if len(other_motor3) >= 4 else None
    )

    motor2_vs_field = (
        head_motor2 - other_motor2_mean
        if head_motor2 is not None and other_motor2_mean is not None
        else None
    )
    motor3_vs_field = (
        head_motor3 - other_motor3_mean
        if head_motor3 is not None and other_motor3_mean is not None
        else None
    )
    head_local3_gap = (
        head_local3 - head_nat3
        if head_local3 is not None and head_nat3 is not None
        else None
    )

    # TRAIN期間だけから固定したForward検証閾値。今後は動かさない。
    variant_flags = {
        "N02_WIND_LT4_ST15": bool(
            head_avg_st is not None and head_avg_st <= 0.1500
        ),
        "N02_WIND_LT4_MOTOR2": bool(
            head_motor2 is not None and head_motor2 >= 38.4056
        ),
        "N02_WIND_LT4_MOTOR2_GAP": bool(
            motor2_vs_field is not None and motor2_vs_field >= 5.7263
        ),
    }

    # 既存aux評価は互換性のため残す。
    flags = {
        "motor_edge": bool(
            motor3_vs_field is not None and motor3_vs_field >= 5.3096
        ),
        "head_motor3": bool(
            head_motor3 is not None and head_motor3 >= 54.2408
        ),
        "head_avg_st": variant_flags["N02_WIND_LT4_ST15"],
    }
    aux_score = sum(int(v) for v in flags.values())
    aux_grade = (
        "A" if aux_score >= 3
        else "B" if aux_score == 2
        else "C" if aux_score == 1
        else "D"
    )

    racer_number = si(h.get("racer_number"), 0)
    # 現時点では実進入コースではなく艇番=headを使用。Shadow記録のみ。
    cs = course_by.get((racer_number, head)) if racer_number else None

    return {
        "head_lane": head,
        "head_racer_number": racer_number or None,
        "head_avg_st": head_avg_st,
        "head_motor2": head_motor2,
        "motor2_vs_field": motor2_vs_field,
        "head_motor3": head_motor3,
        "motor3_vs_field": motor3_vs_field,
        "head_local3_gap": head_local3_gap,
        "aux_score": aux_score,
        "aux_grade": aux_grade,
        "aux_flags": flags,
        "variant_flags": variant_flags,
        "course_stats_date": cs.get("snapshot_date") if cs else None,
        "course_top3_rate": sf(cs.get("top3_rate"), None) if cs else None,
        "course_avg_st": sf(cs.get("avg_st"), None) if cs else None,
    }

def main() -> None:
    print(
        f"✅ collect_n02_windlt4_final_shadow_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"COLLECTION_RACE_IDS={len(COLLECTION_RACE_IDS)} "
        f"MAX_WIND={MAX_WIND}",
        flush=True,
    )
    print(
        "Shadow保存のみ。LINE通知・本番判定・購入処理は変更しません。",
        flush=True,
    )

    if not ENABLED:
        print("N02_WINDLT4_SHADOW_ENABLED=0: skip", flush=True)
        return
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")
    if not COLLECTION_RACE_IDS:
        print("今回のcollection window対象は0件です。", flush=True)
        return

    ensure_schema()
    races, entries_by, odds_by, weather_by, course_by = fetch_day()

    out = []
    stats = {
        "races": len(races),
        "ready": 0,
        "n02_base": 0,
        "wind_missing": 0,
        "wind_ge4": 0,
        "selected": 0,
        "aux_A": 0,
        "aux_B": 0,
        "aux_C": 0,
        "aux_D": 0,
        "variant_ST15": 0,
        "variant_MOTOR2": 0,
        "variant_MOTOR2_GAP": 0,
    }
    now = datetime.now(JST).isoformat()

    for race in races:
        rid = str(race.get("race_id") or "")
        rno = si(race.get("race_no"), 0)
        if rno not in {7, 8, 9, 10}:
            continue

        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})
        if len(v24._entry_by_lane(entries)) != 6:
            continue
        ok, _ = v24._validate_odds_snapshot(odds)
        if not ok:
            continue
        stats["ready"] += 1

        venue = str(
            race.get("venue_id") or race.get("venue_code") or ""
        ).zfill(2)
        ranked = v24._rank_candidates(entries, venue, odds)
        sel = select_ev([x for x in ranked if match_n02(x)])
        if not sel:
            continue
        stats["n02_base"] += 1

        weather = weather_by.get(rid)
        if not weather or weather.get("wind_speed_m") is None:
            stats["wind_missing"] += 1
            continue

        wind = sf(weather.get("wind_speed_m"), None)
        if wind is None:
            stats["wind_missing"] += 1
            continue
        if wind >= MAX_WIND:
            stats["wind_ge4"] += 1
            continue

        stats["selected"] += 1

        ticket = str(sel.get("ticket") or "")
        head = si(ticket.split("-")[0], 0)
        aux = _aux_features(entries, head, course_by)
        grade = str(aux.get("aux_grade") or "D")
        stats[f"aux_{grade}"] = stats.get(f"aux_{grade}", 0) + 1

        base_row = {
            "race_id": rid,
            "race_date": race.get("race_date"),
            "venue_code": venue,
            "race_no": rno,
            "snapshot_label": SNAPSHOT_LABEL,
            "ticket": ticket,
            "odds": sf(sel.get("odds"), 0.0),
            "prob": sf(sel.get("prob"), 0.0),
            "prob_rank": si(sel.get("prob_rank"), 999),
            "market_rank": si(sel.get("market_rank"), 999),
            "raw_ev": sf(sel.get("raw_ev"), 0.0),
            "wind_speed_m": wind,
            "head_lane": aux.get("head_lane"),
            "head_racer_number": aux.get("head_racer_number"),
            "head_avg_st": aux.get("head_avg_st"),
            "head_motor2": aux.get("head_motor2"),
            "motor2_vs_field": aux.get("motor2_vs_field"),
            "head_motor3": aux.get("head_motor3"),
            "motor3_vs_field": aux.get("motor3_vs_field"),
            "head_local3_gap": aux.get("head_local3_gap"),
            "aux_score": aux.get("aux_score"),
            "aux_grade": aux.get("aux_grade"),
            "course_stats_date": aux.get("course_stats_date"),
            "course_top3_rate": aux.get("course_top3_rate"),
            "course_avg_st": aux.get("course_avg_st"),
            "recommendation": "SHADOW_BUY",
            "snapshot_at": now,
            "updated_at": now,
        }

        fixed_common = {
            "prob_rank": "11-20",
            "market_rank": "2-5",
            "odds": "3.0-6.0",
            "race_no": "7-10",
            "select": "EV_MAX",
            "wind": "<4.0",
        }

        variant_defs = [
            ("N02_WIND_LT4", True, {}),
            (
                "N02_WIND_LT4_ST15",
                bool(aux.get("variant_flags", {}).get("N02_WIND_LT4_ST15")),
                {"head_avg_st_max": 0.1500},
            ),
            (
                "N02_WIND_LT4_MOTOR2",
                bool(aux.get("variant_flags", {}).get("N02_WIND_LT4_MOTOR2")),
                {"head_motor2_min": 38.4056},
            ),
            (
                "N02_WIND_LT4_MOTOR2_GAP",
                bool(aux.get("variant_flags", {}).get("N02_WIND_LT4_MOTOR2_GAP")),
                {"motor2_vs_field_min": 5.7263},
            ),
        ]

        for rule_id, matched, extra_rule in variant_defs:
            if not matched:
                continue

            if rule_id == "N02_WIND_LT4_ST15":
                stats["variant_ST15"] += 1
            elif rule_id == "N02_WIND_LT4_MOTOR2":
                stats["variant_MOTOR2"] += 1
            elif rule_id == "N02_WIND_LT4_MOTOR2_GAP":
                stats["variant_MOTOR2_GAP"] += 1

            row = dict(base_row)
            row["rule_id"] = rule_id
            row["raw"] = {
                "fixed_rule": {
                    **fixed_common,
                    **extra_rule,
                },
                "variant_family": "N02_WIND_LT4_FORWARD_FIXED_2026-08-18",
                "variant_flags": aux.get("variant_flags", {}),
                "phase7_fixed_aux": {
                    "motor_edge_threshold": 5.3096,
                    "head_motor3_threshold": 54.2408,
                    "head_avg_st_threshold": 0.1500,
                    "flags": aux.get("aux_flags", {}),
                    "score": aux.get("aux_score"),
                    "grade": aux.get("aux_grade"),
                },
                "course_stats_note": "course=head_lane assumption; shadow only",
                "production_impact": "none",
            }
            out.append(row)

    saved = 0
    if out:
        saved = upsert_rows(
            "v2_n02_windlt4_final_shadow",
            out,
            ["race_id", "snapshot_label", "rule_id"],
        )

    print(
        "summary "
        + " ".join(f"{k}={v}" for k, v in stats.items())
        + f" saved={saved}",
        flush=True,
    )
    for row in out[:10]:
        print(
            f"  SHADOW {row['rule_id']} {row['race_id']} R{row['race_no']} "
            f"{row['ticket']} odds={row['odds']} "
            f"wind={row['wind_speed_m']} "
            f"avgST={row.get('head_avg_st')} "
            f"motor2={row.get('head_motor2')} "
            f"m2edge={row.get('motor2_vs_field')}",
            flush=True,
        )
    print("=== N02 WIND_LT4 final shadow finished ===", flush=True)

if __name__ == "__main__":
    main()