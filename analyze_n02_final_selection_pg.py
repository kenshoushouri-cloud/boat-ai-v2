# -*- coding: utf-8 -*-
"""
analyze_n02_final_selection_pg.py

N02 最終選定専用・読み取り専用分析。

比較する条件は固定:
  A) N02_BASE
     pr=11-20, mr=2-5, odds=3-6, R07-10

  B) N02_WIND_LT4
     上記 + wind_speed_m < 4

新しい条件探索は行わない。
2026-08-01以降の結果を見て条件を追加・変更しない。

期間:
  TRAIN : 2025-07-01 .. 2026-02-28
  VALID : 2026-03-01 .. 2026-04-30
  TEST  : 2026-05-01 .. 2026-06-30
  OOS1  : 2026-07-01 .. 2026-07-31
  OOS2  : 2026-08-01 .. 2026-08-15

目的:
- BASE と WIND_LT4 のどちらを本番採用すべきか決める
- wind>=4 / wind欠損を除外する価値を直接確認する
- 候補頻度、ROI、的中率、利益、最大連敗、最大DDを比較する
- 月別、会場別、レース番号別を確認する
- OOS2 を完全未使用の第二OOSとして評価する

DB更新・LINE通知・本番判定・購入処理なし。
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-16 n02-final-selection-v1"

START_DATE = os.getenv("N02_START_DATE", "2025-07-01")
END_DATE = os.getenv("N02_END_DATE", "2026-08-15")

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"
OOS2_END = "2026-08-15"

N02 = {
    "pr": (11, 20),
    "mr": (2, 5),
    "odds": (3.0, 6.0),
    "rnos": {7, 8, 9, 10},
    "mode": "ev",
}

LABEL_PRIORITY = [
    "historical",
    "final_ab",
    "final",
    "manual",
    "beforeinfo",
    "pre",
    "day",
    "night",
    "morning",
]

def sf(v: Any, d=None):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def si(v: Any, d=0):
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def next_day(s: str) -> str:
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

def month_starts(a: str, b: str):
    cur = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-01")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

def month_end(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def _label_priority(label: str) -> int:
    s = str(label or "").strip().lower()
    try:
        return LABEL_PRIORITY.index(s)
    except ValueError:
        return len(LABEL_PRIORITY) + 100

def choose_snapshot_label(exh_labels, weather_labels, cond_labels):
    common = []
    for label, lanes in exh_labels.items():
        if len(lanes) != 6:
            continue
        if label not in weather_labels:
            continue
        if len(cond_labels.get(label, {})) != 6:
            continue
        common.append(label)
    if not common:
        return None
    return sorted(common, key=lambda x: (_label_priority(x), str(x)))[0]

def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return ([], [], [], [], [], [], [])
    ra = a.replace("-", "")
    rb = b.replace("-", "")

    races = fetch_all(
        "select * from v2_races where race_date >= %s and race_date < %s "
        "order by race_date,venue_id,race_no",
        (a, b),
    )
    entries = fetch_all(
        "select * from v2_race_entries where race_id >= %s and race_id < %s "
        "order by race_id,lane",
        (ra, rb),
    )
    odds = fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta "
        "where race_id >= %s and race_id < %s order by race_id,ticket",
        (ra, rb),
    )
    results = fetch_all(
        "select race_id,trifecta_ticket,"
        "coalesce(trifecta_payout_yen,trifecta_payout) payout "
        "from v2_results where race_id >= %s and race_id < %s",
        (ra, rb),
    )
    exh = fetch_all(
        "select * from v2_realtime_exhibition_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,lane",
        (ra, rb),
    )
    weather = fetch_all(
        "select * from v2_realtime_weather_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,snapshot_at",
        (ra, rb),
    )
    cond = fetch_all(
        "select * from v2_realtime_racer_condition_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,lane",
        (ra, rb),
    )
    return races, entries, odds, results, exh, weather, cond

def match_n02(row):
    return (
        N02["pr"][0] <= si(row.get("prob_rank"), 999) <= N02["pr"][1]
        and N02["mr"][0] <= si(row.get("market_rank"), 999) <= N02["mr"][1]
        and N02["odds"][0] <= (sf(row.get("odds"), 0) or 0) < N02["odds"][1]
    )

def select_one(rows):
    if not rows:
        return None
    return max(
        rows,
        key=lambda r: (
            sf(r.get("raw_ev"), 0) or 0,
            sf(r.get("prob"), 0) or 0,
        ),
    )

def metrics(rows):
    n = len(rows)
    hits = sum(int(r["hit"]) for r in rows)
    returned = sum(int(r["ret"]) for r in rows)
    invested = n * 100

    lose_streak = 0
    cur = 0
    for r in sorted(rows, key=lambda x: (x["date"], x["race_id"])):
        if r["hit"]:
            cur = 0
        else:
            cur += 1
            lose_streak = max(lose_streak, cur)

    bankroll = 0
    peak = 0
    max_dd = 0
    for r in sorted(rows, key=lambda x: (x["date"], x["race_id"])):
        bankroll += int(r["ret"]) - 100
        peak = max(peak, bankroll)
        max_dd = max(max_dd, peak - bankroll)

    days = len({r["date"] for r in rows})
    return {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n * 100 if n else 0.0,
        "roi": returned / invested * 100 if invested else 0.0,
        "profit": returned - invested,
        "lose_streak": lose_streak,
        "max_dd": max_dd,
        "days": days,
    }

def period_name(ds: str) -> str:
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1_2026_07"
    return "OOS2_2026_08_01_15"

def print_metrics(label, rows, days_den=None):
    m = metrics(rows)
    suffix = ""
    if days_den:
        suffix = (
            f" per_calendar_day={m['n']/days_den:.3f}"
            f" active_days={m['days']}/{days_den}"
        )
    print(
        f"{label} n={m['n']} hits={m['hits']} "
        f"hit_rate={m['hit_rate']:.2f}% ROI={m['roi']:.2f}% "
        f"profit={m['profit']} lose_streak={m['lose_streak']} "
        f"maxDD={m['max_dd']}{suffix}",
        flush=True,
    )

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(
        f"✅ analyze_n02_final_selection_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "固定比較: N02_BASE vs N02_WIND_LT4。新しい条件探索はしません。",
        flush=True,
    )
    print(
        "OOS2=2026-08-01..2026-08-15 は第二OOSとしてのみ評価します。",
        flush=True,
    )

    base_rows = []
    ready_total = 0

    for ms in month_starts(START_DATE, END_DATE):
        races, er, orr, rr, xr, wr, cr = fetch_month(ms, month_end(ms))

        eb = defaultdict(list)
        for x in er:
            eb[str(x.get("race_id") or "")].append(x)

        ob = defaultdict(dict)
        for x in orr:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("ticket"))
            o = sf(x.get("odds"), 0)
            if rid and t and o and o > 0:
                ob[rid][t] = o

        rb = {}
        for x in rr:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("trifecta_ticket"))
            p = si(x.get("payout"), 0)
            if rid and t and p > 0:
                rb[rid] = (t, p)

        xb = defaultdict(lambda: defaultdict(dict))
        for x in xr:
            rid = str(x.get("race_id") or "")
            label = str(x.get("snapshot_label") or "").strip()
            lane = si(x.get("lane"))
            if rid and label and 1 <= lane <= 6 and x.get("exhibition_time") is not None:
                xb[rid][label][lane] = x

        wb = defaultdict(dict)
        for x in wr:
            rid = str(x.get("race_id") or "")
            label = str(x.get("snapshot_label") or "").strip()
            if rid and label:
                wb[rid][label] = x

        cb = defaultdict(lambda: defaultdict(dict))
        for x in cr:
            rid = str(x.get("race_id") or "")
            label = str(x.get("snapshot_label") or "").strip()
            lane = si(x.get("lane"))
            if rid and label and 1 <= lane <= 6:
                cb[rid][label][lane] = x

        month_ready = 0
        month_n02 = 0

        for race in races:
            rid = str(race.get("race_id") or "")
            entries = eb.get(rid, [])
            odds = ob.get(rid, {})
            result = rb.get(rid)

            if len(v24._entry_by_lane(entries)) != 6 or not result:
                continue
            ok, _ = v24._validate_odds_snapshot(odds)
            if not ok:
                continue

            chosen_label = choose_snapshot_label(
                xb.get(rid, {}),
                wb.get(rid, {}),
                cb.get(rid, {}),
            )
            if not chosen_label:
                continue

            month_ready += 1
            ready_total += 1

            rno = si(race.get("race_no"))
            if rno not in N02["rnos"]:
                continue

            venue = str(
                race.get("venue_id")
                or race.get("venue_code")
                or ""
            ).zfill(2)

            ranked = v24._rank_candidates(entries, venue, odds)
            sel = select_one([z for z in ranked if match_n02(z)])
            if not sel:
                continue

            month_n02 += 1
            ticket = str(sel.get("ticket") or "")
            head = si(ticket.split("-")[0], 0)

            we = wb[rid][chosen_label]
            wind = sf(we.get("wind_speed_m"), None)

            rt, payout = result
            hit = ticket == rt

            base_rows.append({
                "race_id": rid,
                "date": str(race.get("race_date") or "")[:10],
                "venue": venue,
                "venue_name": str(race.get("venue_name") or ""),
                "race_no": rno,
                "ticket": ticket,
                "head": head,
                "wind": wind,
                "weather": str(we.get("weather") or ""),
                "hit": hit,
                "ret": payout if hit else 0,
            })

        print(
            f"month={ms[:7]} races={len(races)} "
            f"ready={month_ready} n02={month_n02}",
            flush=True,
        )

    wind_rows = [
        r for r in base_rows
        if r["wind"] is not None and r["wind"] < 4
    ]
    excluded_rows = [
        r for r in base_rows
        if not (r["wind"] is not None and r["wind"] < 4)
    ]
    wind_ge4 = [
        r for r in base_rows
        if r["wind"] is not None and r["wind"] >= 4
    ]
    wind_missing = [
        r for r in base_rows
        if r["wind"] is None
    ]

    print("\n" + "=" * 92, flush=True)
    print("=== OVERALL COMPARISON ===", flush=True)
    print_metrics("N02_BASE", base_rows, 411)
    print_metrics("N02_WIND_LT4", wind_rows, 411)
    print_metrics("EXCLUDED_FROM_WIND_LT4", excluded_rows)
    print_metrics("  WIND_GE4", wind_ge4)
    print_metrics("  WIND_MISSING", wind_missing)

    print("\n=== PERIOD COMPARISON ===", flush=True)
    for p in (
        "TRAIN",
        "VALID",
        "TEST",
        "OOS1_2026_07",
        "OOS2_2026_08_01_15",
    ):
        b = [r for r in base_rows if period_name(r["date"]) == p]
        w = [r for r in wind_rows if period_name(r["date"]) == p]
        x = [r for r in excluded_rows if period_name(r["date"]) == p]
        print(f"\n--- {p} ---", flush=True)
        print_metrics("BASE", b)
        print_metrics("WIND_LT4", w)
        print_metrics("EXCLUDED", x)

    print("\n=== MONTHLY COMPARISON ===", flush=True)
    months = sorted({r["date"][:7] for r in base_rows})
    base_plus = 0
    wind_plus = 0
    for mo in months:
        b = [r for r in base_rows if r["date"].startswith(mo)]
        w = [r for r in wind_rows if r["date"].startswith(mo)]
        mb, mw = metrics(b), metrics(w)
        if mb["profit"] > 0:
            base_plus += 1
        if mw["profit"] > 0:
            wind_plus += 1
        print(
            f"{mo} "
            f"BASE n={mb['n']} ROI={mb['roi']:.1f}% profit={mb['profit']} | "
            f"WIND_LT4 n={mw['n']} ROI={mw['roi']:.1f}% profit={mw['profit']}",
            flush=True,
        )

    print(
        f"positive_month_ratio BASE={base_plus}/{len(months)} "
        f"({base_plus/len(months)*100 if months else 0:.1f}%) "
        f"WIND_LT4={wind_plus}/{len(months)} "
        f"({wind_plus/len(months)*100 if months else 0:.1f}%)",
        flush=True,
    )

    print("\n=== VENUE COMPARISON (n>=5 in BASE) ===", flush=True)
    venues = sorted({r["venue"] for r in base_rows})
    for v in venues:
        b = [r for r in base_rows if r["venue"] == v]
        if len(b) < 5:
            continue
        w = [r for r in wind_rows if r["venue"] == v]
        mb, mw = metrics(b), metrics(w)
        name = next((r["venue_name"] for r in b if r["venue_name"]), "")
        print(
            f"{v}:{name} "
            f"BASE n={mb['n']} ROI={mb['roi']:.1f}% "
            f"WIND_LT4 n={mw['n']} ROI={mw['roi']:.1f}%",
            flush=True,
        )

    print("\n=== RACE_NO COMPARISON ===", flush=True)
    for rno in (7, 8, 9, 10):
        b = [r for r in base_rows if r["race_no"] == rno]
        w = [r for r in wind_rows if r["race_no"] == rno]
        mb, mw = metrics(b), metrics(w)
        print(
            f"R{rno:02d} "
            f"BASE n={mb['n']} ROI={mb['roi']:.1f}% "
            f"WIND_LT4 n={mw['n']} ROI={mw['roi']:.1f}%",
            flush=True,
        )

    print("\n=== FINAL FIXED DECISION CHECK ===", flush=True)
    base_oos1 = metrics([r for r in base_rows if period_name(r["date"]) == "OOS1_2026_07"])
    base_oos2 = metrics([r for r in base_rows if period_name(r["date"]) == "OOS2_2026_08_01_15"])
    wind_oos1 = metrics([r for r in wind_rows if period_name(r["date"]) == "OOS1_2026_07"])
    wind_oos2 = metrics([r for r in wind_rows if period_name(r["date"]) == "OOS2_2026_08_01_15"])
    base_all = metrics(base_rows)
    wind_all = metrics(wind_rows)

    base_pass = (
        base_oos1["n"] >= 5
        and base_oos2["n"] >= 3
        and base_oos1["roi"] >= 100
        and base_oos2["roi"] >= 100
        and base_all["roi"] >= 120
    )
    wind_pass = (
        wind_oos1["n"] >= 5
        and wind_oos2["n"] >= 3
        and wind_oos1["roi"] >= 100
        and wind_oos2["roi"] >= 100
        and wind_all["roi"] >= 120
    )

    print(
        f"N02_BASE: OOS1 n={base_oos1['n']} ROI={base_oos1['roi']:.1f}% "
        f"OOS2 n={base_oos2['n']} ROI={base_oos2['roi']:.1f}% "
        f"OVERALL ROI={base_all['roi']:.1f}% "
        f"DECISION={'PASS' if base_pass else 'WAIT'}",
        flush=True,
    )
    print(
        f"N02_WIND_LT4: OOS1 n={wind_oos1['n']} ROI={wind_oos1['roi']:.1f}% "
        f"OOS2 n={wind_oos2['n']} ROI={wind_oos2['roi']:.1f}% "
        f"OVERALL ROI={wind_all['roi']:.1f}% "
        f"DECISION={'PASS' if wind_pass else 'WAIT'}",
        flush=True,
    )

    if base_pass and wind_pass:
        # 採用判断は頻度と安定性を優先し、ROIだけで決めない。
        if wind_all["roi"] >= base_all["roi"] + 10 and len(wind_rows) >= int(len(base_rows) * 0.60):
            recommendation = "N02_WIND_LT4"
        else:
            recommendation = "N02_BASE"
    elif wind_pass:
        recommendation = "N02_WIND_LT4"
    elif base_pass:
        recommendation = "N02_BASE"
    else:
        recommendation = "WAIT"

    print(f"RECOMMENDATION={recommendation}", flush=True)
    print("=== n02 final selection finished ===", flush=True)


if __name__ == "__main__":
    main()