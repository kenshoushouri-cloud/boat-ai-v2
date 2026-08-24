# -*- coding: utf-8 -*-
"""
diagnose_v24_low_candidates_pg.py

v24のBランク参考（low_exR10_12_base）候補が出ない原因を、
過去N日分まとめて診断します。LINE送信・DB更新は行いません。

Railway Start Command:
    python -u diagnose_v24_low_candidates_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    DIAG_END_DATE=YYYY-MM-DD   # 未設定ならJST当日
    DIAG_DAYS=5                # 対象日数
    DIAG_SAMPLE_LIMIT=20       # 近似候補サンプル数
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

# 診断では全レースを見る。import前に限定条件を解除する。
os.environ.pop("TARGET_RACE_IDS", None)
os.environ["PRE_SESSION"] = "all"
os.environ["DRY_RUN"] = "1"

import v24_pre_candidate_notifier_pg as v24  # noqa: E402

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-24 low-core-verdict-v2"
END_DATE = os.getenv("DIAG_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
DIAG_DAYS = max(1, int(os.getenv("DIAG_DAYS", "5")))
SAMPLE_LIMIT = max(1, int(os.getenv("DIAG_SAMPLE_LIMIT", "20")))


def shift_day(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def safe_int(v: Any, default: int = 0) -> int:
    return v24._safe_int(v, default)


def safe_float(v: Any, default: float = 0.0) -> float:
    return v24._safe_float(v, default)


def inspect_date(date_str: str) -> Dict[str, Any]:
    races, entries_by_race, odds_by_race = v24._fetch_live_day_rows(date_str)

    c = Counter()
    market1_prob_ranks: Counter[int] = Counter()
    market1_samples: List[Dict[str, Any]] = []
    core_samples: List[Dict[str, Any]] = []

    for race in races:
        c["races"] += 1
        rid = str(race.get("race_id") or "")
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = safe_int(race.get("race_no"), 0)
        entries = entries_by_race.get(rid, [])
        odds = odds_by_race.get(rid, {})

        if len(v24._entry_by_lane(entries)) != 6:
            c["missing_entries"] += 1
            continue
        if len(odds) < v24.MIN_ODDS_ROWS:
            c["missing_odds"] += 1
            continue

        c["ready_races"] += 1
        ranked = v24._rank_candidates(entries, venue_id, odds)

        # 各条件を単独・段階別に集計
        if any(11 <= safe_int(r.get("prob_rank"), 999) <= 20 for r in ranked):
            c["race_has_prob11_20"] += 1
        if any(safe_int(r.get("market_rank"), 999) == 1 for r in ranked):
            c["race_has_market1"] += 1
        if any(3.0 <= safe_float(r.get("odds"), 0.0) < 5.0 for r in ranked):
            c["race_has_odds3_5"] += 1

        market1 = next(
            (r for r in ranked if safe_int(r.get("market_rank"), 999) == 1),
            None,
        )
        if market1:
            pr = safe_int(market1.get("prob_rank"), 999)
            odd = safe_float(market1.get("odds"), 0.0)
            market1_prob_ranks[pr] += 1

            if 3.0 <= odd < 5.0:
                c["market1_odds3_5"] += 1
            if 11 <= pr <= 20:
                c["market1_prob11_20"] += 1

            distance = 0
            if pr < 11:
                distance += 11 - pr
            elif pr > 20:
                distance += pr - 20
            if odd < 3.0:
                distance += int(round((3.0 - odd) * 10))
            elif odd >= 5.0:
                distance += int(round((odd - 5.0) * 10)) + 1

            market1_samples.append(
                {
                    "distance": distance,
                    "date": date_str,
                    "race_id": rid,
                    "venue_id": venue_id,
                    "race_no": race_no,
                    "ticket": market1.get("ticket"),
                    "prob_rank": pr,
                    "odds": odd,
                }
            )

        for row in ranked:
            pr = safe_int(row.get("prob_rank"), 999)
            mr = safe_int(row.get("market_rank"), 999)
            odd = safe_float(row.get("odds"), 0.0)

            if 11 <= pr <= 20:
                c["rows_prob11_20"] += 1
            if mr == 1:
                c["rows_market1"] += 1
            if 3.0 <= odd < 5.0:
                c["rows_odds3_5"] += 1
            if 11 <= pr <= 20 and mr == 1:
                c["rows_prob_market"] += 1
            if mr == 1 and 3.0 <= odd < 5.0:
                c["rows_market_odds"] += 1
            if 11 <= pr <= 20 and 3.0 <= odd < 5.0:
                c["rows_prob_odds"] += 1

            if 11 <= pr <= 20 and mr == 1 and 3.0 <= odd < 5.0:
                c["low_core"] += 1
                if race_no <= 9:
                    c["low_base_candidate"] += 1
                else:
                    c["core_excluded_r10_12"] += 1
                core_samples.append(
                    {
                        "date": date_str,
                        "race_id": rid,
                        "venue_id": venue_id,
                        "race_no": race_no,
                        "ticket": row.get("ticket"),
                        "prob_rank": pr,
                        "market_rank": mr,
                        "odds": odd,
                    }
                )

    market1_samples.sort(key=lambda x: (x["distance"], x["date"], x["race_id"]))
    return {
        "date": date_str,
        "counts": c,
        "market1_prob_ranks": market1_prob_ranks,
        "near_samples": market1_samples[:SAMPLE_LIMIT],
        "core_samples": core_samples[:SAMPLE_LIMIT],
    }


def print_counts(prefix: str, c: Counter) -> None:
    print(
        f"{prefix}"
        f"races={c['races']} ready={c['ready_races']} "
        f"missing_entries={c['missing_entries']} missing_odds={c['missing_odds']} "
        f"low_core={c['low_core']} low_base_candidate={c['low_base_candidate']} "
        f"excluded_r10_12={c['core_excluded_r10_12']}",
        flush=True,
    )
    print(
        f"{prefix}"
        f"rows: prob11_20={c['rows_prob11_20']} market1={c['rows_market1']} odds3_5={c['rows_odds3_5']} "
        f"prob+market={c['rows_prob_market']} market+odds={c['rows_market_odds']} "
        f"prob+odds={c['rows_prob_odds']}",
        flush=True,
    )
    print(
        f"{prefix}"
        f"races: has_prob11_20={c['race_has_prob11_20']} "
        f"has_market1={c['race_has_market1']} has_odds3_5={c['race_has_odds3_5']} "
        f"market1_odds3_5={c['market1_odds3_5']} market1_prob11_20={c['market1_prob11_20']}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(f"✅ diagnose_v24_low_candidates_pg.py VERSION {VERSION}", flush=True)
    print(
        f"DIAG_END_DATE={END_DATE} DIAG_DAYS={DIAG_DAYS} "
        f"MIN_ODDS_ROWS={v24.MIN_ODDS_ROWS} PROB_TEMP={v24.PROB_TEMP}",
        flush=True,
    )
    print("診断のみです。LINE送信・DB更新は行いません。", flush=True)

    dates = [shift_day(END_DATE, -i) for i in range(DIAG_DAYS - 1, -1, -1)]
    total = Counter()
    total_prob_ranks: Counter[int] = Counter()
    all_near: List[Dict[str, Any]] = []
    all_core: List[Dict[str, Any]] = []

    for d in dates:
        result = inspect_date(d)
        c = result["counts"]
        total.update(c)
        total_prob_ranks.update(result["market1_prob_ranks"])
        all_near.extend(result["near_samples"])
        all_core.extend(result["core_samples"])
        print("\n" + "=" * 72, flush=True)
        print(f"DATE={d}", flush=True)
        print_counts("", c)

    print("\n" + "=" * 72, flush=True)
    print("TOTAL", flush=True)
    print_counts("", total)

    print("\nmarket_rank=1 の prob_rank 分布（上位20件）", flush=True)
    print(
        ", ".join(f"{rank}:{n}" for rank, n in total_prob_ranks.most_common(20))
        or "データなし",
        flush=True,
    )

    if all_core:
        print("\nlow_core該当サンプル", flush=True)
        for x in all_core[:SAMPLE_LIMIT]:
            print(
                f"{x['date']} {x['venue_id']}場{x['race_no']}R "
                f"{x['ticket']} prob_rank={x['prob_rank']} market_rank={x['market_rank']} "
                f"odds={x['odds']:.1f}",
                flush=True,
            )
    else:
        print("\nlow_core該当サンプル: なし", flush=True)

    all_near.sort(key=lambda x: (x["distance"], x["date"], x["race_id"]))
    print("\nmarket_rank=1 の近似サンプル", flush=True)
    for x in all_near[:SAMPLE_LIMIT]:
        print(
            f"{x['date']} {x['venue_id']}場{x['race_no']}R "
            f"{x['ticket']} prob_rank={x['prob_rank']} odds={x['odds']:.1f} "
            f"distance={x['distance']}",
            flush=True,
        )

    print("\n判定目安", flush=True)
    if total["low_core"] > 0:
        ready = total["ready_races"]
        low_core = total["low_core"]
        excluded = total["core_excluded_r10_12"]
        rate = low_core / ready * 100.0 if ready else 0.0
        print(
            f"low_core={low_core}/{ready} ({rate:.3f}%) です。",
            flush=True,
        )
        if excluded > 0:
            print(
                f"このうちR10〜12除外は{excluded}件です。low_base_candidateとの差に影響しています。",
                flush=True,
            )
        else:
            print(
                "R10〜12除外は0件です。候補減少の主因はレース番号除外ではなく、"
                "prob_rank 11〜20・market_rank 1・odds 3〜5の同一買い目での交差自体が希少なことです。",
                flush=True,
            )
    elif total["market1_odds3_5"] == 0:
        print(
            "market_rank=1のオッズが3〜5倍に入っていません。主因はオッズ帯です。",
            flush=True,
        )
    elif total["market1_prob11_20"] == 0:
        print(
            "market_rank=1の買い目がprob_rank 11〜20位に入りません。主因は予測順位と市場順位の組み合わせです。",
            flush=True,
        )
    else:
        print(
            "単独条件は通っていますが同一買い目で交差していません。近似サンプルを確認してください。",
            flush=True,
        )

    print("=== v24 low candidate diagnostic finished ===", flush=True)


if __name__ == "__main__":
    main()
