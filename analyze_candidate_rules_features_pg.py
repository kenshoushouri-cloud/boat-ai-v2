# -*- coding: utf-8 -*-
"""
analyze_candidate_rules_features_pg.py

2025-07-01～2026-06-30 の過去データを使い、
現行 Shadow 7ルール（S01～S05 / N01 / N02）を同じ v24 確率モデルで再現し、
展示・気象・選手直前状態を付加してバックテストする読み取り専用スクリプト。

目的:
1. 現行7ルールの基準成績を再確認
2. 1日平均候補数・候補なし日・重複率を確認
3. 展示/気象/体重/前走情報が的中・ROIに効くか探索するための基礎集計
4. 次段階の N03/N04 条件探索用データを作る

重要:
- DB更新なし
- LINE通知なし
- 本番判定変更なし
- 購入処理なし
- v2_realtime_exhibition_snapshots は snapshot_label='historical' のみ使用
- v2_realtime_weather_snapshots は snapshot_label='historical' のみ使用
- v2_realtime_racer_condition_snapshots は snapshot_label='historical' のみ使用

Start Command:
    python -u analyze_candidate_rules_features_pg.py

Variables:
    DATABASE_URL
    BT_START_DATE=2025-07-01
    BT_END_DATE=2026-06-30

任意:
    BT_RULES=S01,S02,S03,S04,S05,N01,N02
    BT_REQUIRE_EXHIBITION=1
    BT_MIN_SEGMENT_N=20
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))

VERSION = "2026-08-15 seven-rules-features-v1"

START_DATE = os.getenv("BT_START_DATE", "2025-07-01").strip()
END_DATE = os.getenv("BT_END_DATE", "2026-06-30").strip()
MIN_SEGMENT_N = max(1, int(os.getenv("BT_MIN_SEGMENT_N", "20")))

REQUIRE_EXHIBITION = (
    os.getenv("BT_REQUIRE_EXHIBITION", "1").strip().lower()
    in {"1", "true", "yes", "on"}
)

def parse_rule_ids(raw: str) -> set[str]:
    return {
        x.strip().upper()
        for x in re.split(r"[,\s]+", raw or "")
        if x.strip()
    }

REQUESTED_RULES = parse_rule_ids(
    os.getenv(
        "BT_RULES",
        "S01,S02,S03,S04,S05,N01,N02",
    )
)

RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "S01",
        "description": "pr6-15 mr21-30 odds30-50 R01-09 standard EV",
        "pr_min": 6, "pr_max": 15,
        "mr_min": 21, "mr_max": 30,
        "odds_min": 30.0, "odds_max": 50.0,
        "race_nos": set(range(1, 10)),
        "venue_style": "standard",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S02",
        "description": "pr16-30 mr6-10 odds20-30 R07-09 in_strong prob",
        "pr_min": 16, "pr_max": 30,
        "mr_min": 6, "mr_max": 10,
        "odds_min": 20.0, "odds_max": 30.0,
        "race_nos": {7, 8, 9},
        "venue_style": "in_strong",
        "event_category": "ALL",
        "select_mode": "prob",
    },
    {
        "rule_id": "S03",
        "description": "pr11-25 mr6-10 odds30-50 R07-09 standard EV",
        "pr_min": 11, "pr_max": 25,
        "mr_min": 6, "mr_max": 10,
        "odds_min": 30.0, "odds_max": 50.0,
        "race_nos": {7, 8, 9},
        "venue_style": "standard",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S04",
        "description": "pr1-5 mr11-20 odds20-30 R01-03 all EV",
        "pr_min": 1, "pr_max": 5,
        "mr_min": 11, "mr_max": 20,
        "odds_min": 20.0, "odds_max": 30.0,
        "race_nos": {1, 2, 3},
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "S05",
        "description": "pr1-5 mr1-5 odds10-20 all_ladies prob",
        "pr_min": 1, "pr_max": 5,
        "mr_min": 1, "mr_max": 5,
        "odds_min": 10.0, "odds_max": 20.0,
        "race_nos": set(range(1, 13)),
        "venue_style": "ALL",
        "event_category": "all_ladies",
        "select_mode": "prob",
    },
    {
        "rule_id": "N01",
        "description": "Phase4 A_STABLE pr11-25 mr2-5 odds3-6 R07-12 EV",
        "pr_min": 11, "pr_max": 25,
        "mr_min": 2, "mr_max": 5,
        "odds_min": 3.0, "odds_max": 6.0,
        "race_nos": set(range(7, 13)),
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
    {
        "rule_id": "N02",
        "description": "Phase4 B_PROFIT pr11-20 mr2-5 odds3-6 R07-10 EV",
        "pr_min": 11, "pr_max": 20,
        "mr_min": 2, "mr_max": 5,
        "odds_min": 3.0, "odds_max": 6.0,
        "race_nos": set(range(7, 11)),
        "venue_style": "ALL",
        "event_category": "ALL",
        "select_mode": "ev",
    },
]

ACTIVE_RULES = [
    r for r in RULES
    if not REQUESTED_RULES or r["rule_id"] in REQUESTED_RULES
]

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

def sf(v: Any, d: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def next_day(s: str) -> str:
    return (
        datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")

def month_starts(a: str, b: str) -> Iterable[str]:
    cur = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-01")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

def month_end_exclusive(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def norm_ticket(v: Any) -> str:
    return v24._norm_ticket(v)

def match_rule(row: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    pr = si(row.get("prob_rank"), 999)
    mr = si(row.get("market_rank"), 999)
    odd = sf(row.get("odds"), 0.0)
    return (
        rule["pr_min"] <= pr <= rule["pr_max"]
        and rule["mr_min"] <= mr <= rule["mr_max"]
        and rule["odds_min"] <= odd < rule["odds_max"]
    )

def select_one(
    rows: List[Dict[str, Any]],
    mode: str,
) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    if mode == "ev":
        return max(
            rows,
            key=lambda r: (
                sf(r.get("raw_ev"), 0.0),
                sf(r.get("prob"), 0.0),
            ),
        )
    return max(
        rows,
        key=lambda r: (
            sf(r.get("prob"), 0.0),
            sf(r.get("raw_ev"), 0.0),
        ),
    )

def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return ([], [], [], [], [], [], [])

    ra = a.replace("-", "")
    rb = b.replace("-", "")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s and race_date < %s
        order by race_date, venue_id, race_no
        """,
        (a, b),
    )

    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id, lane
        """,
        (ra, rb),
    )

    odds = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id,ticket
        """,
        (ra, rb),
    )

    results = fetch_all(
        """
        select race_id,trifecta_ticket,
               coalesce(trifecta_payout_yen,trifecta_payout) as payout_yen
        from v2_results
        where race_id >= %s and race_id < %s
        """,
        (ra, rb),
    )

    exhibition = fetch_all(
        """
        select *
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label='historical'
        order by race_id,lane
        """,
        (ra, rb),
    )

    weather = fetch_all(
        """
        select *
        from v2_realtime_weather_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label='historical'
        order by race_id
        """,
        (ra, rb),
    )

    racer_condition = fetch_all(
        """
        select *
        from v2_realtime_racer_condition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label='historical'
        order by race_id,lane
        """,
        (ra, rb),
    )

    return (
        races, entries, odds, results,
        exhibition, weather, racer_condition,
    )

def max_losing_streak(rows: List[Dict[str, Any]]) -> int:
    cur = 0
    best = 0
    for r in rows:
        if r["hit"]:
            cur = 0
        else:
            cur += 1
            best = max(best, cur)
    return best

def max_drawdown(rows: List[Dict[str, Any]]) -> int:
    equity = 0
    peak = 0
    worst = 0
    for r in rows:
        equity += r["profit"]
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst

def metrics(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    n = len(rows)
    hits = sum(1 for r in rows if r["hit"])
    ret = sum(r["return_yen"] for r in rows)
    inv = n * 100
    profit = ret - inv
    payouts = sorted(
        [r["return_yen"] for r in rows if r["hit"]],
        reverse=True,
    )
    return {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n * 100 if n else 0.0,
        "roi": ret / inv * 100 if inv else 0.0,
        "profit": profit,
        "max_losing_streak": max_losing_streak(rows),
        "max_drawdown": max_drawdown(rows),
        "single_share": payouts[0] / ret * 100 if payouts and ret else 0.0,
    }

def print_metric(prefix: str, rows: List[Dict[str, Any]]) -> None:
    m = metrics(rows)
    print(
        f"{prefix} n={int(m['n'])} hits={int(m['hits'])} "
        f"hit_rate={m['hit_rate']:.2f}% ROI={m['roi']:.2f}% "
        f"profit={int(m['profit'])} "
        f"lose_streak={int(m['max_losing_streak'])} "
        f"maxDD={int(m['max_drawdown'])} "
        f"single={m['single_share']:.1f}%",
        flush=True,
    )

def bucket(
    value: Optional[float],
    cuts: List[Tuple[Optional[float], Optional[float], str]],
) -> str:
    if value is None:
        return "missing"
    for lo, hi, label in cuts:
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return label
    return "other"

def report_feature(
    title: str,
    rows: List[Dict[str, Any]],
    key: str,
    ordered: Optional[List[str]] = None,
) -> None:
    print(f"\n--- feature: {title} ---", flush=True)
    groups = defaultdict(list)
    for r in rows:
        groups[str(r.get(key, "missing"))].append(r)

    keys = ordered or sorted(groups)
    for k in keys:
        seg = groups.get(k, [])
        if len(seg) >= MIN_SEGMENT_N:
            print_metric(f"{k}", seg)

def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"✅ analyze_candidate_rules_features_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "ACTIVE_RULES=" + ",".join(r["rule_id"] for r in ACTIVE_RULES),
        flush=True,
    )
    print(
        f"REQUIRE_EXHIBITION={REQUIRE_EXHIBITION} "
        f"MIN_SEGMENT_N={MIN_SEGMENT_N}",
        flush=True,
    )
    print(
        "読み取り専用。DB更新・LINE通知・本番判定・購入処理なし。",
        flush=True,
    )

    rows_by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_selected: List[Dict[str, Any]] = []

    audit = defaultdict(int)

    for ms in month_starts(START_DATE, END_DATE):
        mx = month_end_exclusive(ms)

        (
            races, entry_rows, odds_rows, result_rows,
            exhibition_rows, weather_rows, condition_rows,
        ) = fetch_month(ms, mx)

        entries_by = defaultdict(list)
        for x in entry_rows:
            entries_by[str(x.get("race_id") or "")].append(x)

        odds_by = defaultdict(dict)
        for x in odds_rows:
            rid = str(x.get("race_id") or "")
            t = norm_ticket(x.get("ticket"))
            o = sf(x.get("odds"), 0.0)
            if rid and t and o > 0:
                odds_by[rid][t] = o

        results_by = {}
        for x in result_rows:
            rid = str(x.get("race_id") or "")
            t = norm_ticket(x.get("trifecta_ticket"))
            p = si(x.get("payout_yen"), 0)
            if rid and t and p > 0:
                results_by[rid] = (t, p)

        exhibition_by = defaultdict(list)
        for x in exhibition_rows:
            exhibition_by[str(x.get("race_id") or "")].append(x)

        weather_by = {}
        for x in weather_rows:
            rid = str(x.get("race_id") or "")
            if rid:
                weather_by[rid] = x

        condition_by = defaultdict(list)
        for x in condition_rows:
            condition_by[str(x.get("race_id") or "")].append(x)

        month_ready = 0
        month_candidates = 0

        for race in races:
            audit["races"] += 1

            rid = str(race.get("race_id") or "")
            entries = entries_by.get(rid, [])
            odds = odds_by.get(rid, {})
            result = results_by.get(rid)

            if len(v24._entry_by_lane(entries)) != 6:
                audit["skip_entries"] += 1
                continue

            ok, _ = v24._validate_odds_snapshot(odds)
            if not ok:
                audit["skip_odds"] += 1
                continue

            if not result:
                audit["skip_result"] += 1
                continue

            exh = exhibition_by.get(rid, [])
            exh_by_lane = {
                si(x.get("lane"), 0): x
                for x in exh
                if 1 <= si(x.get("lane"), 0) <= 6
            }

            if REQUIRE_EXHIBITION and len(exh_by_lane) != 6:
                audit["skip_exhibition"] += 1
                continue

            weather = weather_by.get(rid, {})
            conditions = condition_by.get(rid, [])
            cond_by_lane = {
                si(x.get("lane"), 0): x
                for x in conditions
                if 1 <= si(x.get("lane"), 0) <= 6
            }

            month_ready += 1
            audit["ready"] += 1

            venue = str(
                race.get("venue_id")
                or race.get("venue_code")
                or ""
            ).zfill(2)
            race_no = si(race.get("race_no"), 0)
            race_date = str(race.get("race_date") or "")[:10]

            meta_text = v24._metadata_text(race)
            venue_style = v24._infer_venue_style(venue)
            event_category = v24._infer_event_category(meta_text)

            ranked = v24._rank_candidates(entries, venue, odds)
            result_ticket, payout = result

            for rule in ACTIVE_RULES:
                if race_no not in rule["race_nos"]:
                    continue
                if (
                    rule["venue_style"] != "ALL"
                    and venue_style != rule["venue_style"]
                ):
                    continue
                if (
                    rule["event_category"] != "ALL"
                    and event_category != rule["event_category"]
                ):
                    continue

                matches = [x for x in ranked if match_rule(x, rule)]
                selected = select_one(matches, rule["select_mode"])
                if not selected:
                    continue

                ticket = str(selected.get("ticket") or "")
                head_lane = si(ticket.split("-")[0], 0) if ticket else 0
                head_exh = exh_by_lane.get(head_lane, {})
                head_cond = cond_by_lane.get(head_lane, {})

                odd = sf(selected.get("odds"), 0.0)
                hit = ticket == result_ticket
                return_yen = payout if hit else 0

                wind_speed = (
                    sf(weather.get("wind_speed_m"), None)
                    if weather.get("wind_speed_m") is not None
                    else None
                )
                wave_height = (
                    sf(weather.get("wave_height_cm"), None)
                    if weather.get("wave_height_cm") is not None
                    else None
                )
                weight = (
                    sf(head_cond.get("weight_kg"), None)
                    if head_cond.get("weight_kg") is not None
                    else None
                )
                prev_st = (
                    sf(head_cond.get("previous_st"), None)
                    if head_cond.get("previous_st") is not None
                    else None
                )

                row = {
                    "rule_id": rule["rule_id"],
                    "race_id": rid,
                    "date": race_date,
                    "month": race_date[:7],
                    "venue": venue,
                    "venue_name": VENUE_NAMES.get(venue, venue),
                    "venue_style": venue_style,
                    "event_category": event_category,
                    "race_no": race_no,
                    "ticket": ticket,
                    "head_lane": head_lane,
                    "odds": odd,
                    "prob": sf(selected.get("prob"), 0.0),
                    "prob_rank": si(selected.get("prob_rank"), 999),
                    "market_rank": si(selected.get("market_rank"), 999),
                    "raw_ev": sf(selected.get("raw_ev"), 0.0),
                    "hit": hit,
                    "return_yen": return_yen,
                    "profit": return_yen - 100,
                    "result_ticket": result_ticket,
                    "payout_yen": payout,

                    "exh_time": (
                        sf(head_exh.get("exhibition_time"), None)
                        if head_exh.get("exhibition_time") is not None
                        else None
                    ),
                    "exh_rank": (
                        si(head_exh.get("exhibition_time_rank"), 0)
                        if head_exh.get("exhibition_time_rank") is not None
                        else None
                    ),
                    "exh_diff": (
                        sf(head_exh.get("exhibition_time_diff"), None)
                        if head_exh.get("exhibition_time_diff") is not None
                        else None
                    ),
                    "exh_st": (
                        sf(head_exh.get("start_timing"), None)
                        if head_exh.get("start_timing") is not None
                        else None
                    ),
                    "exh_st_rank": (
                        si(head_exh.get("start_timing_rank"), 0)
                        if head_exh.get("start_timing_rank") is not None
                        else None
                    ),
                    "weather": str(weather.get("weather") or "missing"),
                    "wind_direction": str(
                        weather.get("wind_direction") or "missing"
                    ),
                    "wind_speed": wind_speed,
                    "wave_height": wave_height,
                    "weight": weight,
                    "prev_st": prev_st,
                    "prev_finish": (
                        si(head_cond.get("previous_finish"), 0)
                        if head_cond.get("previous_finish") is not None
                        else None
                    ),
                }

                # 分析用bucket
                row["exh_rank_bucket"] = (
                    str(row["exh_rank"])
                    if row["exh_rank"] in (1, 2, 3, 4, 5, 6)
                    else "missing"
                )
                row["exh_st_rank_bucket"] = (
                    str(row["exh_st_rank"])
                    if row["exh_st_rank"] in (1, 2, 3, 4, 5, 6)
                    else "missing"
                )
                row["wind_bucket"] = bucket(
                    wind_speed,
                    [
                        (None, 2.0, "0-2"),
                        (2.0, 4.0, "2-4"),
                        (4.0, 6.0, "4-6"),
                        (6.0, None, "6+"),
                    ],
                )
                row["wave_bucket"] = bucket(
                    wave_height,
                    [
                        (None, 3.0, "0-3"),
                        (3.0, 6.0, "3-6"),
                        (6.0, 11.0, "6-10"),
                        (11.0, None, "11+"),
                    ],
                )
                row["weight_bucket"] = bucket(
                    weight,
                    [
                        (None, 50.0, "<50"),
                        (50.0, 53.0, "50-53"),
                        (53.0, 56.0, "53-56"),
                        (56.0, None, "56+"),
                    ],
                )
                row["prev_st_bucket"] = bucket(
                    prev_st,
                    [
                        (None, 0.10, "<0.10"),
                        (0.10, 0.15, "0.10-0.15"),
                        (0.15, 0.20, "0.15-0.20"),
                        (0.20, None, "0.20+"),
                    ],
                )

                rows_by_rule[rule["rule_id"]].append(row)
                all_selected.append(row)
                month_candidates += 1

        print(
            f"month={ms[:7]} races={len(races)} "
            f"ready={month_ready} candidates={month_candidates}",
            flush=True,
        )

    print("\n=== data audit ===", flush=True)
    for k in (
        "races", "ready", "skip_entries", "skip_odds",
        "skip_result", "skip_exhibition",
    ):
        print(f"{k}={audit[k]}", flush=True)

    # rule別の基本成績
    print("\n=== baseline rule summary ===", flush=True)
    for rule in ACTIVE_RULES:
        rid = rule["rule_id"]
        rows = sorted(
            rows_by_rule[rid],
            key=lambda r: (r["date"], r["race_id"]),
        )
        print(
            f"\n{rid}: {rule['description']}",
            flush=True,
        )
        print_metric("OVERALL", rows)

        days = sorted({r["date"] for r in rows})
        active_days = len(days)
        total_period_days = (
            datetime.strptime(END_DATE, "%Y-%m-%d").date()
            - datetime.strptime(START_DATE, "%Y-%m-%d").date()
        ).days + 1

        print(
            f"candidate_days={active_days}/{total_period_days} "
            f"candidate_per_calendar_day="
            f"{len(rows)/total_period_days:.3f} "
            f"candidate_per_active_day="
            f"{len(rows)/active_days:.2f}"
            if active_days
            else "candidate_days=0",
            flush=True,
        )

        print("--- monthly ---", flush=True)
        for m in sorted({r["month"] for r in rows}):
            seg = [r for r in rows if r["month"] == m]
            print_metric(m, seg)

    # 7ルールを全部そのまま使った場合の候補頻度
    print("\n=== combined frequency ===", flush=True)
    total_period_days = (
        datetime.strptime(END_DATE, "%Y-%m-%d").date()
        - datetime.strptime(START_DATE, "%Y-%m-%d").date()
    ).days + 1

    unique_races = {
        (r["date"], r["race_id"])
        for r in all_selected
    }
    unique_race_tickets = {
        (r["date"], r["race_id"], r["ticket"])
        for r in all_selected
    }
    candidate_days = {
        r["date"] for r in all_selected
    }

    print(f"rule_candidate_rows={len(all_selected)}", flush=True)
    print(f"unique_candidate_races={len(unique_races)}", flush=True)
    print(f"unique_race_tickets={len(unique_race_tickets)}", flush=True)
    print(f"candidate_days={len(candidate_days)}/{total_period_days}", flush=True)
    print(
        f"unique_races_per_calendar_day="
        f"{len(unique_races)/total_period_days:.3f}",
        flush=True,
    )

    # N01/N02中心の追加特徴量集計
    for rule_id in ("N01", "N02"):
        rows = sorted(
            rows_by_rule.get(rule_id, []),
            key=lambda r: (r["date"], r["race_id"]),
        )
        if not rows:
            continue

        print("\n" + "=" * 92, flush=True)
        print(
            f"FEATURE ANALYSIS {rule_id} "
            f"(候補={len(rows)})",
            flush=True,
        )

        report_feature(
            "head exhibition rank",
            rows,
            "exh_rank_bucket",
            ["1","2","3","4","5","6","missing"],
        )
        report_feature(
            "head exhibition ST rank",
            rows,
            "exh_st_rank_bucket",
            ["1","2","3","4","5","6","missing"],
        )
        report_feature(
            "weather",
            rows,
            "weather",
        )
        report_feature(
            "wind speed",
            rows,
            "wind_bucket",
            ["0-2","2-4","4-6","6+","missing"],
        )
        report_feature(
            "wave height",
            rows,
            "wave_bucket",
            ["0-3","3-6","6-10","11+","missing"],
        )
        report_feature(
            "head weight",
            rows,
            "weight_bucket",
            ["<50","50-53","53-56","56+","missing"],
        )
        report_feature(
            "head previous ST",
            rows,
            "prev_st_bucket",
            ["<0.10","0.10-0.15","0.15-0.20","0.20+","missing"],
        )

    print("\n=== seven-rules feature analysis finished ===", flush=True)


if __name__ == "__main__":
    main()