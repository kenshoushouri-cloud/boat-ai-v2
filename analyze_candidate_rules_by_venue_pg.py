# -*- coding: utf-8 -*-
"""
analyze_candidate_rules_by_venue_pg.py

候補フィルターShadowルール S01～S05 を、
既存のRailway Postgresデータで場別・時系列分割評価します。

目的:
- Shadowだけで数か月待たず、既存の完全オッズを使って候補を絞る
- 場ごとの差を確認する
- TRAIN / TEST の両方で安定している条件だけを抽出する

重要:
- 読み取り専用です。
- DB更新、LINE通知、本番判定、購入処理はありません。
- v2_odds_trifectaに現在保存されている値を使用するため、
  厳密な「当時その時点のオッズ」バックテストではありません。
- 三連単オッズが120/60/24通りの完全集合になっているレースだけを使います。

Start Command:
    python -u analyze_candidate_rules_by_venue_pg.py

必須Variables:
    DATABASE_URL

任意Variables:
    ANALYSIS_START_DATE=2026-06-01
    ANALYSIS_TEST_START_DATE=2026-07-01
    ANALYSIS_END_DATE=2026-08-02
    ANALYSIS_MIN_TRAIN_CANDIDATES=10
    ANALYSIS_MIN_TEST_CANDIDATES=10
    ANALYSIS_MIN_TOTAL_CANDIDATES=25
    ANALYSIS_MIN_TRAIN_ROI=90
    ANALYSIS_MIN_TEST_ROI=100
    ANALYSIS_MAX_SINGLE_HIT_SHARE_PCT=60
    ANALYSIS_TOP_N=100
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))

START_DATE = os.getenv("ANALYSIS_START_DATE", "2026-06-01")
TEST_START_DATE = os.getenv("ANALYSIS_TEST_START_DATE", "2026-07-01")
END_DATE = os.getenv("ANALYSIS_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")

MIN_TRAIN_CANDIDATES = max(
    1, int(os.getenv("ANALYSIS_MIN_TRAIN_CANDIDATES", "10"))
)
MIN_TEST_CANDIDATES = max(
    1, int(os.getenv("ANALYSIS_MIN_TEST_CANDIDATES", "10"))
)
MIN_TOTAL_CANDIDATES = max(
    1, int(os.getenv("ANALYSIS_MIN_TOTAL_CANDIDATES", "25"))
)
MIN_TRAIN_ROI = float(os.getenv("ANALYSIS_MIN_TRAIN_ROI", "90"))
MIN_TEST_ROI = float(os.getenv("ANALYSIS_MIN_TEST_ROI", "100"))
MAX_SINGLE_HIT_SHARE_PCT = float(
    os.getenv("ANALYSIS_MAX_SINGLE_HIT_SHARE_PCT", "60")
)
TOP_N = max(1, int(os.getenv("ANALYSIS_TOP_N", "100")))

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
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _race_group(race_no: int) -> str:
    if race_no <= 3:
        return "R01_03"
    if race_no <= 6:
        return "R04_06"
    if race_no <= 9:
        return "R07_09"
    return "R10_12"


def _new_stat() -> Dict[str, Any]:
    return {
        "candidates": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
    }


def _add_result(stat: Dict[str, Any], hit: bool, payout: int) -> None:
    stat["candidates"] += 1
    stat["investment"] += 100
    if hit:
        stat["hits"] += 1
        stat["return"] += payout
        if payout > 0:
            stat["hit_returns"].append(payout)


def _metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    n = int(stat["candidates"])
    hits = int(stat["hits"])
    inv = int(stat["investment"])
    ret = int(stat["return"])
    profit = ret - inv
    hit_rate = hits / n * 100.0 if n else 0.0
    roi = ret / inv * 100.0 if inv else 0.0
    max_hit = max(stat["hit_returns"]) if stat["hit_returns"] else 0
    single_hit_share = max_hit / ret * 100.0 if ret > 0 else 0.0
    return {
        "n": float(n),
        "hits": float(hits),
        "investment": float(inv),
        "return": float(ret),
        "profit": float(profit),
        "hit_rate": hit_rate,
        "roi": roi,
        "max_hit": float(max_hit),
        "single_hit_share": single_hit_share,
    }


def _fetch_all_data():
    races = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s
          and race_date <= %s
        order by race_date, venue_id, race_no;
        """,
        (START_DATE, END_DATE),
    )

    start_prefix = START_DATE.replace("-", "")
    end_next = (
        datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")

    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s
          and race_id < %s
        order by race_id, lane;
        """,
        (start_prefix, end_next),
    )

    odds = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s
          and race_id < %s
        order by race_id,ticket;
        """,
        (start_prefix, end_next),
    )

    results = fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s
        order by race_id;
        """,
        (start_prefix, end_next),
    )

    entries_by: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries:
        entries_by.setdefault(str(row.get("race_id")), []).append(row)

    odds_by: Dict[str, Dict[str, float]] = {}
    for row in odds:
        rid = str(row.get("race_id") or "")
        ticket = v24._norm_ticket(row.get("ticket"))
        odd = _safe_float(row.get("odds"), 0.0)
        if rid and ticket and odd > 0:
            odds_by.setdefault(rid, {})[ticket] = odd

    results_by = {
        str(row.get("race_id")): row
        for row in results
        if row.get("race_id")
    }

    return races, entries_by, odds_by, results_by


def _result_ticket_and_payout(row: Dict[str, Any]) -> Tuple[str, int]:
    ticket = v24._norm_ticket(
        row.get("trifecta_ticket")
        or row.get("sanrentan_ticket")
        or row.get("result_ticket")
        or row.get("ticket")
    )
    payout = _safe_int(
        row.get("trifecta_payout_yen")
        or row.get("trifecta_payout")
        or row.get("payout_yen")
        or row.get("return_yen"),
        0,
    )
    return ticket, payout


def _match_rule(
    ranked_row: Dict[str, Any],
    rule: Dict[str, Any],
) -> bool:
    pr = _safe_int(ranked_row.get("prob_rank"), 999)
    mr = _safe_int(ranked_row.get("market_rank"), 999)
    odds = _safe_float(ranked_row.get("odds"), 0.0)

    return (
        rule["pr_min"] <= pr <= rule["pr_max"]
        and rule["mr_min"] <= mr <= rule["mr_max"]
        and rule["odds_min"] <= odds < rule["odds_max"]
    )


def _select_one(
    rows: List[Dict[str, Any]],
    mode: str,
) -> Optional[Dict[str, Any]]:
    if not rows:
        return None

    if mode == "ev":
        return max(
            rows,
            key=lambda row: (
                _safe_float(row.get("raw_ev"), 0.0),
                _safe_float(row.get("prob"), 0.0),
            ),
        )

    return max(
        rows,
        key=lambda row: (
            _safe_float(row.get("prob"), 0.0),
            _safe_float(row.get("raw_ev"), 0.0),
        ),
    )


def _print_stat(prefix: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    print(
        f"{prefix}: n={int(m['n'])} hits={int(m['hits'])} "
        f"hit_rate={m['hit_rate']:.2f}% "
        f"investment={int(m['investment'])} "
        f"return={int(m['return'])} "
        f"profit={int(m['profit'])} "
        f"ROI={m['roi']:.2f}% "
        f"max_hit={int(m['max_hit'])} "
        f"single_hit_share={m['single_hit_share']:.2f}%",
        flush=True,
    )


def main() -> None:
    print(
        "✅ analyze_candidate_rules_by_venue_pg.py "
        "VERSION 2026-08-03 venue-walkforward-v1",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    if not (START_DATE < TEST_START_DATE <= END_DATE):
        raise RuntimeError(
            "日付条件が不正です。"
            "START_DATE < TEST_START_DATE <= END_DATE が必要です。"
        )

    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"TRAIN={START_DATE}..{TEST_START_DATE}未満 "
        f"TEST={TEST_START_DATE}..{END_DATE}",
        flush=True,
    )
    print(
        f"MIN_TRAIN={MIN_TRAIN_CANDIDATES} "
        f"MIN_TEST={MIN_TEST_CANDIDATES} "
        f"MIN_TOTAL={MIN_TOTAL_CANDIDATES} "
        f"MIN_TRAIN_ROI={MIN_TRAIN_ROI:.1f}% "
        f"MIN_TEST_ROI={MIN_TEST_ROI:.1f}% "
        f"MAX_SINGLE_HIT_SHARE={MAX_SINGLE_HIT_SHARE_PCT:.1f}%",
        flush=True,
    )
    print(
        "読み取り専用です。DB更新・LINE通知・本番判定変更はありません。",
        flush=True,
    )
    print(
        "注意: 保存済みオッズを使うため、厳密な当時時点バックテストではありません。",
        flush=True,
    )

    races, entries_by, odds_by, results_by = _fetch_all_data()
    event_day_by_date_venue: Dict[Tuple[str, str], int] = {}

    # v24の開催日数計算を日付ごとに呼ぶと重いため、開催日を連続日で数える。
    dates_by_venue: Dict[str, List[str]] = defaultdict(list)
    for race in races:
        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)
        race_date = str(race.get("race_date") or "")[:10]
        if race_date and race_date not in dates_by_venue[venue_id]:
            dates_by_venue[venue_id].append(race_date)

    for venue_id, dates in dates_by_venue.items():
        prev = ""
        day_no = 0
        for race_date in sorted(dates):
            if prev and race_date == (
                datetime.strptime(prev, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d"):
                day_no += 1
            else:
                day_no = 1
            event_day_by_date_venue[(race_date, venue_id)] = day_no
            prev = race_date

    stats: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(_new_stat)
    overall_by_rule: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(_new_stat)

    total_races = len(races)
    ready_races = 0
    skipped_entries = 0
    skipped_odds = 0
    skipped_result = 0
    candidate_count = 0

    for idx, race in enumerate(races, start=1):
        rid = str(race.get("race_id") or "")
        race_date = str(race.get("race_date") or "")[:10]
        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)

        entries = entries_by.get(rid, [])
        if len(v24._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue

        odds = odds_by.get(rid, {})
        odds_ready, _ = v24._validate_odds_snapshot(odds)
        if not odds_ready:
            skipped_odds += 1
            continue

        result = results_by.get(rid)
        if not result:
            skipped_result += 1
            continue

        result_ticket, payout = _result_ticket_and_payout(result)
        if not result_ticket or payout <= 0:
            skipped_result += 1
            continue

        ready_races += 1

        meta_text = v24._metadata_text(race)
        venue_style = v24._infer_venue_style(venue_id)
        event_category = v24._infer_event_category(meta_text)
        event_day_no = event_day_by_date_venue.get(
            (race_date, venue_id),
            1,
        )
        ranked = v24._rank_candidates(entries, venue_id, odds)
        period = "TRAIN" if race_date < TEST_START_DATE else "TEST"

        for rule in RULES:
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

            matched = [
                row for row in ranked
                if _match_rule(row, rule)
            ]
            selected = _select_one(matched, str(rule["select_mode"]))
            if not selected:
                continue

            candidate_count += 1
            ticket = str(selected.get("ticket") or "")
            hit = ticket == result_ticket

            keys = [
                (rule["rule_id"], venue_id, period),
                (rule["rule_id"], f"{venue_id}:{_race_group(race_no)}", period),
                (rule["rule_id"], f"{venue_id}:DAY{event_day_no}", period),
            ]
            for key in keys:
                _add_result(stats[key], hit, payout)

            _add_result(
                overall_by_rule[(rule["rule_id"], period)],
                hit,
                payout,
            )

        if idx % 1000 == 0 or idx == total_races:
            print(
                f"progress={idx}/{total_races} "
                f"ready={ready_races} candidates={candidate_count}",
                flush=True,
            )

    print("\n=== data coverage ===", flush=True)
    print(f"total_races={total_races}", flush=True)
    print(f"ready_races={ready_races}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print(f"skipped_result={skipped_result}", flush=True)
    print(f"candidate_selections={candidate_count}", flush=True)

    print("\n=== overall rule performance ===", flush=True)
    for rule in RULES:
        rule_id = rule["rule_id"]
        _print_stat(
            f"{rule_id} TRAIN",
            overall_by_rule[(rule_id, "TRAIN")],
        )
        _print_stat(
            f"{rule_id} TEST ",
            overall_by_rule[(rule_id, "TEST")],
        )

    shortlist: List[Dict[str, Any]] = []

    # 場別だけをshortlist対象にする。
    for rule in RULES:
        rule_id = rule["rule_id"]
        for venue_no in range(1, 25):
            venue_id = f"{venue_no:02d}"
            train_stat = stats[(rule_id, venue_id, "TRAIN")]
            test_stat = stats[(rule_id, venue_id, "TEST")]
            train = _metrics(train_stat)
            test = _metrics(test_stat)

            total_n = int(train["n"] + test["n"])
            enough = (
                int(train["n"]) >= MIN_TRAIN_CANDIDATES
                and int(test["n"]) >= MIN_TEST_CANDIDATES
                and total_n >= MIN_TOTAL_CANDIDATES
            )
            stable_roi = (
                train["roi"] >= MIN_TRAIN_ROI
                and test["roi"] >= MIN_TEST_ROI
            )
            concentration_ok = (
                train["return"] > 0
                and test["return"] > 0
                and train["single_hit_share"]
                <= MAX_SINGLE_HIT_SHARE_PCT
                and test["single_hit_share"]
                <= MAX_SINGLE_HIT_SHARE_PCT
            )

            if not (enough and stable_roi and concentration_ok):
                continue

            score = (
                min(train["roi"], test["roi"])
                + min(train["hit_rate"], test["hit_rate"]) * 2.0
                + min(int(train["n"]), int(test["n"])) * 0.2
            )

            shortlist.append(
                {
                    "rule_id": rule_id,
                    "venue_id": venue_id,
                    "train": train,
                    "test": test,
                    "score": score,
                }
            )

    shortlist.sort(key=lambda row: row["score"], reverse=True)

    print("\n=== robust venue shortlist ===", flush=True)
    if not shortlist:
        print(
            "現基準では場別の堅牢候補なし。"
            "本番条件は変更しないでください。",
            flush=True,
        )
    else:
        for rank, row in enumerate(shortlist[:TOP_N], start=1):
            tr = row["train"]
            te = row["test"]
            print(
                f"{rank:03d}. {row['rule_id']} venue={row['venue_id']} "
                f"| TRAIN n={int(tr['n'])} hits={int(tr['hits'])} "
                f"ROI={tr['roi']:.2f}% profit={int(tr['profit'])} "
                f"single_hit_share={tr['single_hit_share']:.2f}% "
                f"| TEST n={int(te['n'])} hits={int(te['hits'])} "
                f"ROI={te['roi']:.2f}% profit={int(te['profit'])} "
                f"single_hit_share={te['single_hit_share']:.2f}% "
                f"| score={row['score']:.2f}",
                flush=True,
            )

    print("\n=== detailed venue breakdown ===", flush=True)
    for rule in RULES:
        rule_id = rule["rule_id"]
        print(f"-- {rule_id} --", flush=True)

        venue_rows = []
        for venue_no in range(1, 25):
            venue_id = f"{venue_no:02d}"
            tr = _metrics(stats[(rule_id, venue_id, "TRAIN")])
            te = _metrics(stats[(rule_id, venue_id, "TEST")])
            total_n = int(tr["n"] + te["n"])
            if total_n <= 0:
                continue
            venue_rows.append((total_n, venue_id, tr, te))

        venue_rows.sort(reverse=True)

        for _, venue_id, tr, te in venue_rows:
            print(
                f"venue={venue_id} "
                f"TRAIN n={int(tr['n'])} ROI={tr['roi']:.2f}% "
                f"TEST n={int(te['n'])} ROI={te['roi']:.2f}%",
                flush=True,
            )

    print("=== analysis finished ===", flush=True)


if __name__ == "__main__":
    main()