# -*- coding: utf-8 -*-
"""
diagnose_phase6_july_ready_pg.py

2026年7月が Phase6 FINAL OOS で ready=0 になった原因を、
条件ごとに分解して確認する読み取り専用診断。

確認項目:
- v2_races 対象件数
- 出走表6艇
- 三連単オッズ120通り
- 有効結果
- historical展示6艇
- historical気象
- historical選手状態6艇
- 各条件の共通集合
- 月内日別のready件数
- snapshot_label分布
- 代表的なNG race_idサンプル

DB更新・LINE通知・本番変更なし。

Start Command:
    python -u diagnose_phase6_july_ready_pg.py

Variables:
    DATABASE_URL
    DIAG_START_DATE=2026-07-01
    DIAG_END_DATE=2026-07-31
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-15 july-ready-diagnose-v1"

START_DATE = os.getenv("DIAG_START_DATE", "2026-07-01").strip()
END_DATE = os.getenv("DIAG_END_DATE", "2026-07-31").strip()

def next_day(s: str) -> str:
    return (
        datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")

def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def sf(v: Any, d: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(
        f"✅ diagnose_phase6_july_ready_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("読み取り専用。DB更新・LINE通知・本番変更なし。", flush=True)

    a = START_DATE
    b = next_day(END_DATE)
    ra = a.replace("-", "")
    rb = b.replace("-", "")

    races = fetch_all(
        """
        select race_id,race_date,venue_id,venue_code,venue_name,race_no
        from v2_races
        where race_date >= %s and race_date < %s
        order by race_date,venue_id,race_no
        """,
        (a, b),
    )

    entries = fetch_all(
        """
        select race_id,lane
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane
        """,
        (ra, rb),
    )

    odds = fetch_all(
        """
        select race_id,ticket,odds,is_final
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id,ticket
        """,
        (ra, rb),
    )

    results = fetch_all(
        """
        select
            race_id,
            trifecta_ticket,
            coalesce(trifecta_payout_yen,trifecta_payout) as payout_yen,
            result_status,
            race_status
        from v2_results
        where race_id >= %s and race_id < %s
        order by race_id
        """,
        (ra, rb),
    )

    exhibition = fetch_all(
        """
        select
            race_id,lane,snapshot_label,exhibition_time,start_timing
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
        order by race_id,snapshot_label,lane
        """,
        (ra, rb),
    )

    weather = fetch_all(
        """
        select
            race_id,snapshot_label,weather,wind_speed_m,wave_height_cm
        from v2_realtime_weather_snapshots
        where race_id >= %s and race_id < %s
        order by race_id,snapshot_label
        """,
        (ra, rb),
    )

    racer_cond = fetch_all(
        """
        select
            race_id,lane,snapshot_label,weight_kg,previous_st,previous_finish
        from v2_realtime_racer_condition_snapshots
        where race_id >= %s and race_id < %s
        order by race_id,snapshot_label,lane
        """,
        (ra, rb),
    )

    # group
    entries_by = defaultdict(set)
    for x in entries:
        lane = si(x.get("lane"))
        if 1 <= lane <= 6:
            entries_by[str(x.get("race_id") or "")].add(lane)

    odds_by = defaultdict(dict)
    for x in odds:
        rid = str(x.get("race_id") or "")
        t = v24._norm_ticket(x.get("ticket"))
        o = sf(x.get("odds"), 0.0)
        if rid and t and o > 0:
            odds_by[rid][t] = o

    result_ok = set()
    for x in results:
        rid = str(x.get("race_id") or "")
        t = v24._norm_ticket(x.get("trifecta_ticket"))
        p = si(x.get("payout_yen"), 0)
        if rid and t and p > 0:
            result_ok.add(rid)

    exh_by_label = defaultdict(lambda: defaultdict(set))
    for x in exhibition:
        rid = str(x.get("race_id") or "")
        label = str(x.get("snapshot_label") or "")
        lane = si(x.get("lane"))
        if rid and label and 1 <= lane <= 6 and x.get("exhibition_time") is not None:
            exh_by_label[label][rid].add(lane)

    weather_by_label = defaultdict(set)
    for x in weather:
        rid = str(x.get("race_id") or "")
        label = str(x.get("snapshot_label") or "")
        if rid and label:
            weather_by_label[label].add(rid)

    cond_by_label = defaultdict(lambda: defaultdict(set))
    for x in racer_cond:
        rid = str(x.get("race_id") or "")
        label = str(x.get("snapshot_label") or "")
        lane = si(x.get("lane"))
        if rid and label and 1 <= lane <= 6:
            cond_by_label[label][rid].add(lane)

    race_ids = [str(r.get("race_id") or "") for r in races]
    race_set = set(race_ids)

    entries_ok = {rid for rid in race_set if len(entries_by.get(rid, set())) == 6}

    odds_ok = set()
    odds_invalid_reason = {}
    for rid in race_set:
        od = odds_by.get(rid, {})
        ok, info = v24._validate_odds_snapshot(od)
        if ok:
            odds_ok.add(rid)
        else:
            odds_invalid_reason[rid] = info

    hist_exh_ok = {
        rid for rid in race_set
        if len(exh_by_label.get("historical", {}).get(rid, set())) == 6
    }
    hist_weather_ok = race_set & weather_by_label.get("historical", set())
    hist_cond_ok = {
        rid for rid in race_set
        if len(cond_by_label.get("historical", {}).get(rid, set())) == 6
    }

    ready = (
        race_set
        & entries_ok
        & odds_ok
        & result_ok
        & hist_exh_ok
    )

    print("\n=== main counts ===", flush=True)
    print(f"races={len(race_set)}", flush=True)
    print(f"entries_6={len(entries_ok)}", flush=True)
    print(f"odds_complete={len(odds_ok)}", flush=True)
    print(f"valid_result={len(result_ok & race_set)}", flush=True)
    print(f"historical_exhibition_6={len(hist_exh_ok)}", flush=True)
    print(f"historical_weather={len(hist_weather_ok)}", flush=True)
    print(f"historical_racer_condition_6={len(hist_cond_ok)}", flush=True)
    print(f"phase6_ready={len(ready)}", flush=True)

    print("\n=== cumulative funnel ===", flush=True)
    cur = set(race_set)
    print(f"start={len(cur)}", flush=True)
    for name, okset in [
        ("entries_6", entries_ok),
        ("odds_complete", odds_ok),
        ("valid_result", result_ok),
        ("historical_exhibition_6", hist_exh_ok),
        ("historical_weather", hist_weather_ok),
        ("historical_racer_condition_6", hist_cond_ok),
    ]:
        before = len(cur)
        cur &= okset
        print(
            f"{name}: before={before} after={len(cur)} dropped={before-len(cur)}",
            flush=True,
        )

    print("\n=== snapshot labels ===", flush=True)
    all_exh_labels = sorted(exh_by_label)
    all_weather_labels = sorted(weather_by_label)
    all_cond_labels = sorted(cond_by_label)

    print("exhibition:", flush=True)
    for label in all_exh_labels:
        complete = sum(
            1 for rid, lanes in exh_by_label[label].items()
            if rid in race_set and len(lanes) == 6
        )
        races_with = sum(1 for rid in exh_by_label[label] if rid in race_set)
        print(
            f"  label={label!r} races={races_with} complete6={complete}",
            flush=True,
        )

    print("weather:", flush=True)
    for label in all_weather_labels:
        count = len(weather_by_label[label] & race_set)
        print(f"  label={label!r} races={count}", flush=True)

    print("racer_condition:", flush=True)
    for label in all_cond_labels:
        complete = sum(
            1 for rid, lanes in cond_by_label[label].items()
            if rid in race_set and len(lanes) == 6
        )
        races_with = sum(1 for rid in cond_by_label[label] if rid in race_set)
        print(
            f"  label={label!r} races={races_with} complete6={complete}",
            flush=True,
        )

    print("\n=== daily ready ===", flush=True)
    by_date = defaultdict(list)
    race_meta = {}
    for r in races:
        rid = str(r.get("race_id") or "")
        ds = str(r.get("race_date") or "")[:10]
        by_date[ds].append(rid)
        race_meta[rid] = r

    for ds in sorted(by_date):
        ids = set(by_date[ds])
        print(
            f"{ds} races={len(ids)} "
            f"entries={len(ids & entries_ok)} "
            f"odds={len(ids & odds_ok)} "
            f"result={len(ids & result_ok)} "
            f"hist_exh={len(ids & hist_exh_ok)} "
            f"ready={len(ids & ready)}",
            flush=True,
        )

    def sample(title: str, ids: set[str], limit: int = 15):
        print(f"\n--- {title} sample ---", flush=True)
        for rid in sorted(ids)[:limit]:
            r = race_meta.get(rid, {})
            print(
                f"{rid} "
                f"{r.get('venue_name') or r.get('venue_code') or ''} "
                f"{r.get('race_no')}R",
                flush=True,
            )

    sample("entries NG", race_set - entries_ok)
    sample("odds NG", race_set - odds_ok)
    sample("result NG", race_set - result_ok)
    sample("historical exhibition NG", race_set - hist_exh_ok)
    sample("historical weather NG", race_set - hist_weather_ok)
    sample("historical racer_condition NG", race_set - hist_cond_ok)

    print("\n=== odds NG detail sample ===", flush=True)
    shown = 0
    for rid in sorted(race_set - odds_ok):
        print(
            f"{rid} valid_tickets={len(odds_by.get(rid, {}))} "
            f"detail={odds_invalid_reason.get(rid)}",
            flush=True,
        )
        shown += 1
        if shown >= 20:
            break

    print("\n=== diagnosis hint ===", flush=True)

    if len(hist_exh_ok) == 0 and any(
        len(lanes) == 6
        for label, byrid in exh_by_label.items()
        if label != "historical"
        for rid, lanes in byrid.items()
        if rid in race_set
    ):
        print(
            "LIKELY_CAUSE=2026-07 exhibition data exists under a non-historical snapshot_label.",
            flush=True,
        )
    elif len(result_ok & race_set) == 0:
        print(
            "LIKELY_CAUSE=2026-07 valid results are missing.",
            flush=True,
        )
    elif len(odds_ok) == 0:
        print(
            "LIKELY_CAUSE=2026-07 complete odds are missing or validation rule differs.",
            flush=True,
        )
    elif len(hist_exh_ok) == 0:
        print(
            "LIKELY_CAUSE=2026-07 historical exhibition snapshots are missing.",
            flush=True,
        )
    else:
        print(
            "LIKELY_CAUSE=multiple conditions; inspect cumulative funnel above.",
            flush=True,
        )

    print("=== july ready diagnosis finished ===", flush=True)


if __name__ == "__main__":
    main()