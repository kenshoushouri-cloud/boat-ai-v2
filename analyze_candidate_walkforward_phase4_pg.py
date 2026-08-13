# -*- coding: utf-8 -*-
"""
analyze_candidate_walkforward_phase4_pg.py

Phase 4: 最終耐久試験
Phase 3で残った2条件だけを徹底検証する読み取り専用スクリプト。

対象:
A_STABLE:
  prob_rank 11-25 / market_rank 2-5 / odds 3-6 / 7-12R / EV選択

B_PROFIT:
  prob_rank 11-20 / market_rank 2-5 / odds 3-6 / 7-10R / EV選択

検証内容:
- TRAIN / VALID / TEST
- 月別
- 競艇場別
- 個別R別
- odds帯 3-4 / 4-5 / 5-6
- market_rank 2 / 3 / 4 / 5
- prob_rank帯
- 開催カテゴリー
- 最大連敗 / 最大DD
- 最大的中1件を除いたROI
- 上位2的中を除いたROI
- Leave-One-Month-Out (1か月除外) 最悪ROI
- Rolling walk-forward（複数境界）
- 直近期間の成績

重要:
- DB更新、LINE通知、本番判定、購入処理なし
- 保存済みオッズを使用するため厳密な当時時点オッズではない
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))

START_DATE = os.getenv("BT_START_DATE", "2025-07-01")
END_DATE = os.getenv(
    "BT_END_DATE",
    datetime.now(JST).strftime("%Y-%m-%d"),
)

MIN_SEGMENT_N = int(os.getenv("BT4_MIN_SEGMENT_N", "8"))
TOP_N = int(os.getenv("BT4_TOP_N", "100"))

CANDIDATES = [
    {
        "id": "A_STABLE",
        "pr": (11, 25),
        "mr": (2, 5),
        "odds": (3.0, 6.0),
        "race_nos": set(range(7, 13)),
        "mode": "ev",
    },
    {
        "id": "B_PROFIT",
        "pr": (11, 20),
        "mr": (2, 5),
        "odds": (3.0, 6.0),
        "race_nos": set(range(7, 11)),
        "mode": "ev",
    },
]

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

ROLLING_SPLITS = [
    ("WF1", "2025-07-01", "2026-01-01", "2026-03-01"),
    ("WF2", "2025-08-01", "2026-02-01", "2026-04-01"),
    ("WF3", "2025-09-01", "2026-03-01", "2026-05-01"),
    ("WF4", "2025-10-01", "2026-04-01", "2026-06-01"),
    ("WF5", "2025-11-01", "2026-05-01", "2026-07-01"),
]

def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d

def si(v: Any, d: int = 0) -> int:
    try:
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

def month_end(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def infer_category(name: str) -> str:
    n = name or ""
    l = n.lower()
    if "オールレディース" in n or "all ladies" in l:
        return "all_ladies"
    if "ヴィーナス" in n or "venus" in l:
        return "venus"
    if "ルーキー" in n or "rookie" in l:
        return "rookie"
    if "マスターズ" in n or "masters" in l:
        return "masters"
    if "レディース" in n or "女子" in n or "ladies" in l:
        return "ladies_other"
    if any(x.lower() in l for x in ("SG", "G1", "GⅠ", "G2", "GⅡ", "G3", "GⅢ")):
        return "G1_like"
    return "category_other"

def odds_bucket(odd: float) -> str:
    if 3.0 <= odd < 4.0:
        return "3-4"
    if 4.0 <= odd < 5.0:
        return "4-5"
    if 5.0 <= odd < 6.0:
        return "5-6"
    return "other"

def prob_bucket(pr: int) -> str:
    if 11 <= pr <= 15:
        return "11-15"
    if 16 <= pr <= 20:
        return "16-20"
    if 21 <= pr <= 25:
        return "21-25"
    return "other"

def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return [], [], [], []

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
        select race_id, ticket, odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id, ticket
        """,
        (ra, rb),
    )
    results = fetch_all(
        """
        select race_id, trifecta_ticket, trifecta_payout_yen
        from v2_results
        where race_id >= %s and race_id < %s
        """,
        (ra, rb),
    )
    return races, entries, odds, results

def best_for_candidate(
    ranked: List[Dict[str, Any]],
    c: Dict[str, Any],
    race_no: int,
) -> Optional[Dict[str, Any]]:
    if race_no not in c["race_nos"]:
        return None

    eligible = []
    for row in ranked:
        pr = si(row.get("prob_rank"), 999)
        mr = si(row.get("market_rank"), 999)
        odd = sf(row.get("odds"), 0.0)
        if (
            c["pr"][0] <= pr <= c["pr"][1]
            and c["mr"][0] <= mr <= c["mr"][1]
            and c["odds"][0] <= odd < c["odds"][1]
        ):
            eligible.append(row)

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda r: (
            sf(r.get("raw_ev"), 0.0),
            sf(r.get("prob"), 0.0),
        ),
    )

def max_losing_streak(rows: List[Dict[str, Any]]) -> int:
    cur = 0
    best = 0
    for r in rows:
        if not r["hit"]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
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

    ret_minus1 = ret - (payouts[0] if payouts else 0)
    ret_minus2 = ret - sum(payouts[:2])

    return {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n * 100 if n else 0.0,
        "roi": ret / inv * 100 if inv else 0.0,
        "profit": profit,
        "single_share": payouts[0] / ret * 100 if ret and payouts else 0.0,
        "roi_minus_top1": ret_minus1 / inv * 100 if inv else 0.0,
        "roi_minus_top2": ret_minus2 / inv * 100 if inv else 0.0,
        "max_losing_streak": max_losing_streak(rows),
        "max_drawdown": max_drawdown(rows),
    }

def print_metric(prefix: str, m: Dict[str, float]) -> None:
    print(
        f"{prefix} n={int(m['n'])} hits={int(m['hits'])} "
        f"hit_rate={m['hit_rate']:.2f}% "
        f"ROI={m['roi']:.2f}% profit={int(m['profit'])} "
        f"single={m['single_share']:.1f}% "
        f"ROI-top1={m['roi_minus_top1']:.2f}% "
        f"ROI-top2={m['roi_minus_top2']:.2f}% "
        f"lose_streak={int(m['max_losing_streak'])} "
        f"maxDD={int(m['max_drawdown'])}",
        flush=True,
    )

def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        "✅ analyze_candidate_walkforward_phase4_pg.py "
        "VERSION 2026-08-13 robustness-final-v1",
        flush=True,
    )
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "読み取り専用です。DB更新・LINE通知・本番判定変更はありません。",
        flush=True,
    )

    rows_by_candidate = defaultdict(list)

    for ms in month_starts(START_DATE, END_DATE):
        races, erows, orows, rrows = fetch_month(ms, month_end(ms))

        entries_by = defaultdict(list)
        for row in erows:
            entries_by[str(row.get("race_id") or "")].append(row)

        odds_by = defaultdict(dict)
        for row in orows:
            rid = str(row.get("race_id") or "")
            ticket = v24._norm_ticket(row.get("ticket"))
            odd = sf(row.get("odds"), 0.0)
            if rid and ticket and odd > 0:
                odds_by[rid][ticket] = odd

        results_by = {}
        for row in rrows:
            rid = str(row.get("race_id") or "")
            ticket = v24._norm_ticket(row.get("trifecta_ticket"))
            payout = si(row.get("trifecta_payout_yen"), 0)
            if rid and ticket and payout > 0:
                results_by[rid] = (ticket, payout)

        month_ready = 0

        for race in races:
            rid = str(race.get("race_id") or "")
            entries = entries_by.get(rid, [])
            odds = odds_by.get(rid, {})
            result = results_by.get(rid)

            if len(v24._entry_by_lane(entries)) != 6 or not result:
                continue

            ok, _ = v24._validate_odds_snapshot(odds)
            if not ok:
                continue

            race_date = str(race.get("race_date") or "")[:10]
            venue = str(
                race.get("venue_id")
                or race.get("venue_code")
                or ""
            ).zfill(2)
            race_no = si(race.get("race_no"), 0)
            category = infer_category(
                str(race.get("race_name") or "")
            )

            ranked = v24._rank_candidates(entries, venue, odds)
            result_ticket, payout = result

            for c in CANDIDATES:
                selected = best_for_candidate(ranked, c, race_no)
                if not selected:
                    continue

                ticket = str(selected.get("ticket") or "")
                hit = ticket == result_ticket
                odd = sf(selected.get("odds"), 0.0)
                pr = si(selected.get("prob_rank"), 999)
                mr = si(selected.get("market_rank"), 999)

                rows_by_candidate[c["id"]].append(
                    {
                        "race_id": rid,
                        "date": race_date,
                        "month": race_date[:7],
                        "venue": venue,
                        "venue_name": VENUE_NAMES.get(venue, venue),
                        "race_no": race_no,
                        "category": category,
                        "ticket": ticket,
                        "odds": odd,
                        "odds_bucket": odds_bucket(odd),
                        "prob_rank": pr,
                        "prob_bucket": prob_bucket(pr),
                        "market_rank": mr,
                        "hit": hit,
                        "return_yen": payout if hit else 0,
                        "profit": payout - 100 if hit else -100,
                    }
                )

            month_ready += 1

        print(
            f"month={ms[:7]} races={len(races)} ready={month_ready}",
            flush=True,
        )

    for c in CANDIDATES:
        cid = c["id"]
        rows = sorted(
            rows_by_candidate[cid],
            key=lambda r: (r["date"], r["race_id"]),
        )

        print("\n" + "=" * 88, flush=True)
        print(
            f"{cid}: pr={c['pr'][0]}-{c['pr'][1]} "
            f"mr={c['mr'][0]}-{c['mr'][1]} "
            f"odds={c['odds'][0]:g}-{c['odds'][1]:g} "
            f"R={min(c['race_nos'])}-{max(c['race_nos'])}",
            flush=True,
        )

        print_metric("OVERALL", metrics(rows))

        print("\n--- yearly / recent slices ---", flush=True)
        slices = [
            ("2025_H2", "2025-07-01", "2026-01-01"),
            ("2026_Q1", "2026-01-01", "2026-04-01"),
            ("2026_Q2+", "2026-04-01", next_day(END_DATE)),
            ("RECENT_90D", max(START_DATE, (
                datetime.strptime(END_DATE, "%Y-%m-%d")
                - timedelta(days=89)
            ).strftime("%Y-%m-%d")), next_day(END_DATE)),
        ]
        for name, a, b in slices:
            seg = [r for r in rows if a <= r["date"] < b]
            if seg:
                print_metric(name, metrics(seg))

        print("\n--- monthly ---", flush=True)
        for month in sorted({r["month"] for r in rows}):
            seg = [r for r in rows if r["month"] == month]
            print_metric(month, metrics(seg))

        print("\n--- venue ---", flush=True)
        venue_rows = []
        for venue in sorted({r["venue"] for r in rows}):
            seg = [r for r in rows if r["venue"] == venue]
            if len(seg) >= MIN_SEGMENT_N:
                m = metrics(seg)
                venue_rows.append((m["roi"], venue, seg, m))
        venue_rows.sort(key=lambda x: x[0])
        for _, venue, seg, m in venue_rows:
            print_metric(
                f"{venue}:{VENUE_NAMES.get(venue,venue)}",
                m,
            )

        print("\n--- race_no ---", flush=True)
        for rno in sorted({r["race_no"] for r in rows}):
            seg = [r for r in rows if r["race_no"] == rno]
            if len(seg) >= MIN_SEGMENT_N:
                print_metric(f"R{rno:02d}", metrics(seg))

        print("\n--- odds buckets ---", flush=True)
        for key in ("3-4", "4-5", "5-6"):
            seg = [r for r in rows if r["odds_bucket"] == key]
            if len(seg) >= MIN_SEGMENT_N:
                print_metric(f"odds {key}", metrics(seg))

        print("\n--- market_rank ---", flush=True)
        for mr in (2, 3, 4, 5):
            seg = [r for r in rows if r["market_rank"] == mr]
            if len(seg) >= MIN_SEGMENT_N:
                print_metric(f"market_rank={mr}", metrics(seg))

        print("\n--- prob buckets ---", flush=True)
        for key in ("11-15", "16-20", "21-25"):
            seg = [r for r in rows if r["prob_bucket"] == key]
            if len(seg) >= MIN_SEGMENT_N:
                print_metric(f"prob {key}", metrics(seg))

        print("\n--- category ---", flush=True)
        for key in sorted({r["category"] for r in rows}):
            seg = [r for r in rows if r["category"] == key]
            if len(seg) >= MIN_SEGMENT_N:
                print_metric(key, metrics(seg))

        print("\n--- leave-one-month-out stress ---", flush=True)
        loo = []
        months = sorted({r["month"] for r in rows})
        for month in months:
            seg = [r for r in rows if r["month"] != month]
            m = metrics(seg)
            loo.append((m["roi"], month, m))
        loo.sort(key=lambda x: x[0])
        for roi, month, m in loo[:10]:
            print_metric(f"exclude {month}", m)

        print("\n--- rolling walk-forward ---", flush=True)
        for name, train_start, valid_start, test_start in ROLLING_SPLITS:
            if test_start > END_DATE:
                continue
            train = [
                r for r in rows
                if train_start <= r["date"] < valid_start
            ]
            valid = [
                r for r in rows
                if valid_start <= r["date"] < test_start
            ]
            test = [
                r for r in rows
                if test_start <= r["date"] <= END_DATE
            ]
            if not train or not valid or not test:
                continue
            print(f"{name}", flush=True)
            print_metric("  TRAIN", metrics(train))
            print_metric("  VALID", metrics(valid))
            print_metric("  TEST ", metrics(test))

        print("\n--- final robustness decision ---", flush=True)
        overall = metrics(rows)
        recent90 = metrics(
            [
                r for r in rows
                if r["date"] >= max(
                    START_DATE,
                    (
                        datetime.strptime(END_DATE, "%Y-%m-%d")
                        - timedelta(days=89)
                    ).strftime("%Y-%m-%d"),
                )
            ]
        )

        positive_months = 0
        evaluated_months = 0
        for month in sorted({r["month"] for r in rows}):
            seg = [r for r in rows if r["month"] == month]
            if len(seg) >= 5:
                evaluated_months += 1
                if metrics(seg)["profit"] > 0:
                    positive_months += 1

        plus_ratio = (
            positive_months / evaluated_months * 100
            if evaluated_months
            else 0.0
        )

        checks = {
            "overall_roi>=110": overall["roi"] >= 110,
            "roi_minus_top1>=100": overall["roi_minus_top1"] >= 100,
            "roi_minus_top2>=95": overall["roi_minus_top2"] >= 95,
            "recent90_roi>=100": recent90["roi"] >= 100,
            "plus_month_ratio>=55": plus_ratio >= 55,
            "maxDD<=1500": overall["max_drawdown"] <= 1500,
            "lose_streak<=12": overall["max_losing_streak"] <= 12,
        }

        for name, ok in checks.items():
            print(f"{name}: {'PASS' if ok else 'WAIT'}", flush=True)

        print(
            f"positive_month_ratio={plus_ratio:.1f}% "
            f"({positive_months}/{evaluated_months})",
            flush=True,
        )
        print(
            "ROBUSTNESS="
            + (
                "PASS"
                if all(checks.values())
                else "COLLECTING/REVIEW"
            ),
            flush=True,
        )

    print("\n=== phase4 analysis finished ===", flush=True)


if __name__ == "__main__":
    main()