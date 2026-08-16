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
VERSION = "2026-08-16 n02-windlt4-final-shadow-v1"

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
    return races, entries_by, odds_by, weather_by

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
    races, entries_by, odds_by, weather_by = fetch_day()

    out = []
    stats = {
        "races": len(races),
        "ready": 0,
        "n02_base": 0,
        "wind_missing": 0,
        "wind_ge4": 0,
        "selected": 0,
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
        out.append({
            "race_id": rid,
            "race_date": race.get("race_date"),
            "venue_code": venue,
            "race_no": rno,
            "snapshot_label": SNAPSHOT_LABEL,
            "rule_id": "N02_WIND_LT4",
            "ticket": str(sel.get("ticket") or ""),
            "odds": sf(sel.get("odds"), 0.0),
            "prob": sf(sel.get("prob"), 0.0),
            "prob_rank": si(sel.get("prob_rank"), 999),
            "market_rank": si(sel.get("market_rank"), 999),
            "raw_ev": sf(sel.get("raw_ev"), 0.0),
            "wind_speed_m": wind,
            "recommendation": "SHADOW_BUY",
            "snapshot_at": now,
            "raw": {
                "fixed_rule": {
                    "prob_rank": "11-20",
                    "market_rank": "2-5",
                    "odds": "3.0-6.0",
                    "race_no": "7-10",
                    "select": "EV_MAX",
                    "wind": "<4.0",
                },
                "production_impact": "none",
            },
            "updated_at": now,
        })

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
            f"  SHADOW {row['race_id']} R{row['race_no']} "
            f"{row['ticket']} odds={row['odds']} "
            f"wind={row['wind_speed_m']}",
            flush=True,
        )
    print("=== N02 WIND_LT4 final shadow finished ===", flush=True)

if __name__ == "__main__":
    main()