# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v3.py

競艇AI v2用・複数パターン一括バックテスト。

目的:
- 2025-03-13〜2026-05-31 など、Supabaseに保存済みの v2_* データで検証する
- 全候補 / シード戦限定 / 1点 / 2点 / 本線+保険 / 保険6倍以上 を同じ条件で比較する
- 1日1,000円上限を標準適用し、実運用に近い形で比較する
- v3では人気順位帯・オッズ帯別の追加検証を行う

前提テーブル:
- public.v2_races
- public.v2_results
- public.v2_race_entries
- public.v2_odds_trifecta

Railway Start Command:
    python backtest_multi_patterns_v3_loglite_pagingfix.py

主な環境変数:
    BACKTEST_START_DATE=2025-03-13
    BACKTEST_END_DATE=2026-05-31
    BACKTEST_VENUES=01,02,...,24
    BACKTEST_DAILY_BUDGET_YEN=1000
    BACKTEST_UNIT_YEN=100
    BACKTEST_MIN_EV=0.0
    BACKTEST_MIN_ODDS=1.0
    BACKTEST_MAX_ODDS=9999
    BACKTEST_INSURANCE_MIN_ODDS=6.0
    BACKTEST_STRICT_SEED=1
    BACKTEST_WRITE_CSV=1
    BACKTEST_TEMP=2.20
    BACKTEST_ODDS_PAGE_SIZE=5000
    BACKTEST_RETRY_MAX=3
    BACKTEST_RETRY_SLEEP=2.0
    BACKTEST_DAY_SLEEP=0.0
    BACKTEST_FAIR_BUDGET=0

注意:
- ここでの予測は、既存の predictor_v2 に依存しない簡易スコアです。
- まず「買い方パターン比較」の土台を作る目的です。
- 後で predictor_v2 の確率を使う版に差し替え可能です。

[修正履歴 2026-06-16]
  FIX-1: actual_ticket 復元ロジックを _get_actual_ticket() に共通化。
  FIX-2: 払戻換算を actual_payout_yen * UNIT_YEN / 100 に統一。
  FIX-3: eligible_before_budget / eligible_after_budget を分離。
  FIX-4: fav_rank フィルタ後に fav_rank_in_scope を再付番。
  FIX-5: _norm_ticket に unicodedata.normalize("NFKC") を導入し、全角数字も吸収。
  FIX-6: BACKTEST_FAIR_BUDGET を追加。
  FIX-7: EV戦略の説明を「30倍以下」に統一。
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# ============================================================
# Settings
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

START_DATE = os.getenv("BACKTEST_START_DATE", "2025-03-13")
END_DATE = os.getenv("BACKTEST_END_DATE", "2026-05-31")

ALL_VENUES = [f"{i:02d}" for i in range(1, 25)]
TARGET_VENUES = [
    v.strip().zfill(2)
    for v in os.getenv("BACKTEST_VENUES", ",".join(ALL_VENUES)).split(",")
    if v.strip()
]

UNIT_YEN = int(os.getenv("BACKTEST_UNIT_YEN", "100"))
DAILY_BUDGET_YEN = int(os.getenv("BACKTEST_DAILY_BUDGET_YEN", "1000"))
DAILY_MAX_POINTS = DAILY_BUDGET_YEN // UNIT_YEN if DAILY_BUDGET_YEN > 0 else 10**9

MIN_EV = float(os.getenv("BACKTEST_MIN_EV", "0.0"))
MIN_ODDS = float(os.getenv("BACKTEST_MIN_ODDS", "1.0"))
MAX_ODDS = float(os.getenv("BACKTEST_MAX_ODDS", "9999"))
INSURANCE_MIN_ODDS = float(os.getenv("BACKTEST_INSURANCE_MIN_ODDS", "6.0"))
STRICT_SEED = os.getenv("BACKTEST_STRICT_SEED", "1") == "1"
WRITE_CSV = os.getenv("BACKTEST_WRITE_CSV", "1") == "1"
CSV_DIR = os.getenv("BACKTEST_CSV_DIR", "/tmp/backtest_reports")

# 1=点数ではなく採用レース数で上限を揃える。実運用検証では通常0推奨。
FAIR_BUDGET = os.getenv("BACKTEST_FAIR_BUDGET", "0") == "1"

PROB_TEMP = float(os.getenv("BACKTEST_TEMP", "2.20"))
ODDS_PAGE_SIZE = int(os.getenv("BACKTEST_ODDS_PAGE_SIZE", "5000"))
RETRY_MAX = int(os.getenv("BACKTEST_RETRY_MAX", "3"))
RETRY_SLEEP = float(os.getenv("BACKTEST_RETRY_SLEEP", "2.0"))
DAY_SLEEP = float(os.getenv("BACKTEST_DAY_SLEEP", "0.0"))

# Railwayログ制限対策
# 0=日次ログをかなり抑制、1=従来寄り
VERBOSE_LOG = os.getenv("BACKTEST_VERBOSE_LOG", "0") == "1"
# 何日ごとに進捗ログを出すか。0なら日次進捗ログなし。
LOG_EVERY_DAYS = int(os.getenv("BACKTEST_LOG_EVERY_DAYS", "7"))
# adopted_counts の長い内訳を出すか
PRINT_ADOPTED_COUNTS = os.getenv("BACKTEST_PRINT_ADOPTED_COUNTS", "0") == "1"
# JSON summary 全文を出すか。CSVがあるので通常0推奨。
PRINT_JSON_SUMMARY = os.getenv("BACKTEST_PRINT_JSON_SUMMARY", "0") == "1"
# コンソールに表示する上位戦略数
SUMMARY_TOP_N = int(os.getenv("BACKTEST_SUMMARY_TOP_N", "12"))

HTTP_TIMEOUT = int(os.getenv("BACKTEST_HTTP_TIMEOUT", "40"))
PAGE_SIZE = int(os.getenv("BACKTEST_PAGE_SIZE", "1000"))

# DB上の3連単払戻額は100円購入基準。
PAYOUT_BASE_YEN = 100

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

CLASS_NAME = {1: "B2", 2: "B1", 3: "A2", 4: "A1"}
CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}

VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}


# ============================================================
# Utility
# ============================================================

def _require_settings() -> None:
    print("✅ backtest_multi_patterns_v3_loglite_pagingfix.py VERSION 2026-06-16 odds-band-favrank [log-lite-pagingfix]", flush=True)
    print(f"SUPABASE_URL: {SUPABASE_URL}", flush=True)
    print(f"SUPABASE_KEY: {'OK' if bool(SUPABASE_KEY) else 'MISSING'}", flush=True)
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY が未設定です")


def _daterange(start_str: str, end_str: str) -> Iterable[str]:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    cur = start
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def _next_day(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _rid_prefix(date_str: str) -> str:
    return date_str.replace("-", "")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", ""))
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default


def _yen(v: Any) -> str:
    return f"{_safe_int(v):,}円"


def _norm_ticket(ticket: Any) -> str:
    """
    3連単チケット表記を 1-2-3 形式に正規化する。

    NFKC正規化により、全角数字・全角ハイフン・一部記号を吸収する。
    例:
      １－２－３ -> 1-2-3
      1ー2ー3   -> 1-2-3相当に抽出
      123       -> 1-2-3
      1=2=3     -> 1-2-3
    """
    if ticket is None:
        return ""

    s = unicodedata.normalize("NFKC", str(ticket).strip())
    nums = re.findall(r"[1-6]", s)
    if len(nums) >= 3:
        a, b, c = nums[:3]
        if len({a, b, c}) == 3:
            return f"{a}-{b}-{c}"
    return ""


def _ticket_tuple(ticket: str) -> Tuple[int, int, int]:
    a, b, c = _norm_ticket(ticket).split("-")
    return int(a), int(b), int(c)


def _get_actual_ticket(result: Dict[str, Any]) -> str:
    """
    result レコードから確定3連単チケットを復元する。
    trifecta_ticket が空の場合は first/second/third_lane から補完する。
    """
    t = _norm_ticket(result.get("trifecta_ticket"))
    if not t:
        fl = result.get("first_lane")
        sl = result.get("second_lane")
        tl = result.get("third_lane")
        if fl and sl and tl:
            t = _norm_ticket(f"{fl}-{sl}-{tl}")
    return t


# ============================================================
# Supabase REST
# ============================================================

def _http_get_with_retry(url: str) -> List[Dict[str, Any]]:
    """Supabase REST GET with simple retry."""
    last_err: Optional[Exception] = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            if not res.ok:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:500]}")
            return res.json()
        except Exception as e:
            last_err = e
            if attempt < RETRY_MAX:
                print(f"  [retry {attempt}/{RETRY_MAX}] {e} — {RETRY_SLEEP}s 後に再試行", flush=True)
                time.sleep(RETRY_SLEEP)
    raise RuntimeError(f"リトライ上限到達: {last_err}")


def _rest_get(table: str, params: Dict[str, str], page_size: int = PAGE_SIZE) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        p = dict(params)
        p["limit"] = str(page_size)
        p["offset"] = str(offset)
        query = urllib.parse.urlencode(p, safe=",.*()")
        url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
        part = _http_get_with_retry(url)
        if not part:
            break
        rows.extend(part)

        # Supabase/PostgREST側の最大返却件数が limit より小さい場合がある。
        # 例: limit=5000 を指定しても 1000件しか返らない環境では、
        # len(part) < page_size で break すると1ページ目だけで止まってしまう。
        # そのため「返ってきた件数ぶん offset を進め、空ページまで取り続ける」方式にする。
        offset += len(part)
    return rows


def _rest_get_range(
    table: str,
    select: str,
    col: str,
    gte: str,
    lt: str,
    page_size: int = PAGE_SIZE,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        parts = [
            ("select", select),
            (col, f"gte.{gte}"),
            (col, f"lt.{lt}"),
            ("order", f"{col}.asc"),
            ("limit", str(page_size)),
            ("offset", str(offset)),
        ]
        query = urllib.parse.urlencode(parts, safe=",.*()")
        url = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
        part = _http_get_with_retry(url)
        if not part:
            break
        rows.extend(part)

        # Supabase/PostgREST側の最大返却件数が limit より小さい場合がある。
        # 例: limit=5000 を指定しても 1000件しか返らない環境では、
        # len(part) < page_size で break すると1ページ目だけで止まってしまう。
        # そのため「返ってきた件数ぶん offset を進め、空ページまで取り続ける」方式にする。
        offset += len(part)
    return rows


def _fetch_day_rows(date_str: str) -> Tuple[
    List[Dict[str, Any]],
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, Dict[str, float]],
]:
    """1日分の races/results/entries/odds を取得する。"""
    day_prefix = _rid_prefix(date_str)
    next_prefix = _rid_prefix(_next_day(date_str))

    races = _rest_get(
        "v2_races",
        {
            "select": "race_id,race_date,venue_id,race_no",
            "race_date": f"eq.{date_str}",
            "order": "venue_id.asc,race_no.asc",
        },
    )
    races = [r for r in races if str(r.get("venue_id", "")).zfill(2) in TARGET_VENUES]

    results_rows = _rest_get_range(
        "v2_results",
        select="race_id,result_status,trifecta_ticket,trifecta_payout_yen,first_lane,second_lane,third_lane",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
    )
    results = {r["race_id"]: r for r in results_rows}

    entries_rows = _rest_get_range(
        "v2_race_entries",
        select="race_id,lane,racer_number,racer_class,national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,motor_no,boat_no",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
    )
    entries: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries_rows:
        entries.setdefault(e["race_id"], []).append(e)

    odds_rows = _rest_get_range(
        "v2_odds_trifecta",
        select="race_id,ticket,odds",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
        page_size=ODDS_PAGE_SIZE,
    )
    odds: Dict[str, Dict[str, float]] = {}
    for o in odds_rows:
        rid = o.get("race_id")
        ticket = _norm_ticket(o.get("ticket"))
        if not rid or not ticket:
            continue
        odds.setdefault(rid, {})[ticket] = _safe_float(o.get("odds"), 0.0)

    return races, results, entries, odds


# ============================================================
# Race model / scoring
# ============================================================

def _entry_by_lane(entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    d: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        lane = _safe_int(e.get("lane"), 0)
        if 1 <= lane <= 6:
            d[lane] = e
    return d


def _is_backtest_ready(
    result: Optional[Dict[str, Any]],
    entries: List[Dict[str, Any]],
    odds: Dict[str, float],
) -> bool:
    if not result:
        return False
    if result.get("result_status") not in ("official", "parse_incomplete"):
        return False
    actual_ticket = _get_actual_ticket(result)
    if not actual_ticket:
        return False
    if _safe_int(result.get("trifecta_payout_yen"), 0) <= 0:
        return False

    by_lane = _entry_by_lane(entries)
    if len(by_lane) != 6:
        return False
    for lane in range(1, 7):
        e = by_lane.get(lane, {})
        if not e.get("racer_number") or e.get("racer_class") is None:
            return False

    if len(odds) != 120:
        return False
    return True


def _is_seed_race(entries: List[Dict[str, Any]], strict: bool = STRICT_SEED) -> bool:
    by_lane = _entry_by_lane(entries)
    if len(by_lane) != 6:
        return False

    c1 = _safe_int(by_lane[1].get("racer_class"), 0)
    others = [_safe_int(by_lane[l].get("racer_class"), 0) for l in range(2, 7)]
    if c1 not in (3, 4):
        return False
    if strict:
        return all(c in (1, 2) for c in others)
    return sum(1 for c in others if c in (1, 2)) >= 4


def _lane_raw_strength(entry: Dict[str, Any], lane: int, venue_id: str) -> float:
    racer_class = _safe_int(entry.get("racer_class"), 0)
    nat_win = _safe_float(entry.get("national_win_rate"), 0.0)
    nat_p2 = _safe_float(entry.get("national_place2_rate"), 0.0)
    loc_win = _safe_float(entry.get("local_win_rate"), 0.0)
    loc_p2 = _safe_float(entry.get("local_place2_rate"), 0.0)

    course_bias = VENUE_COURSE_BIAS.get(str(venue_id).zfill(2), DEFAULT_COURSE_BIAS).get(lane, 2.0)

    return (
        CLASS_WEIGHT.get(racer_class, 0.3)
        + nat_win * 0.11
        + loc_win * 0.07
        + nat_p2 * 0.012
        + loc_p2 * 0.008
        + course_bias * 0.22
    )


def _ticket_probabilities(entries: List[Dict[str, Any]], venue_id: str) -> Dict[str, float]:
    by_lane = _entry_by_lane(entries)
    raw = {lane: _lane_raw_strength(by_lane[lane], lane, venue_id) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / PROB_TEMP) for lane in range(1, 7)}

    probs: Dict[str, float] = {}
    total = sum(weights.values())
    for a in range(1, 7):
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in range(1, 7):
                if c == a or c == b:
                    continue
                pc = weights[c] / total_c
                probs[f"{a}-{b}-{c}"] = pa * pb * pc
    return probs


def _rank_candidates(
    entries: List[Dict[str, Any]],
    venue_id: str,
    odds: Dict[str, float],
) -> List[Dict[str, Any]]:
    probs = _ticket_probabilities(entries, venue_id)
    rows: List[Dict[str, Any]] = []
    for ticket, prob in probs.items():
        odd = _safe_float(odds.get(ticket), 0.0)
        if odd <= 0:
            continue
        ev = prob * odd
        rows.append({"ticket": ticket, "prob": prob, "odds": odd, "ev": ev})

    # 全120点内の市場人気順位
    for rank, row in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), start=1):
        row["market_rank"] = rank

    rows.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
    return rows


# ============================================================
# Strategies
# ============================================================

@dataclass
class Strategy:
    name: str
    description: str
    seed_only: bool = False
    first_fixed: Optional[int] = None
    main_count: int = 1
    insurance_count: int = 0
    insurance_min_odds: float = INSURANCE_MIN_ODDS
    require_insurance_no_trigami: bool = True
    min_ev: float = MIN_EV
    min_odds: float = MIN_ODDS
    max_odds: float = MAX_ODDS
    score_mode: str = "prob"  # prob / ev / favorite
    fav_rank_min: Optional[int] = None
    fav_rank_max: Optional[int] = None


STRATEGIES: List[Strategy] = [
    # v2継続: 基準線
    Strategy("all_prob_1pt", "全候補・予測確率上位1点", seed_only=False, main_count=1, score_mode="prob"),
    Strategy("all_prob_2pt", "全候補・予測確率上位2点", seed_only=False, main_count=2, score_mode="prob"),
    Strategy("all_ev_1pt", "全候補・EV上位1点・30倍以下", seed_only=False, main_count=1, score_mode="ev", max_odds=30.0),
    Strategy("all_ev_2pt", "全候補・EV上位2点・30倍以下", seed_only=False, main_count=2, score_mode="ev", max_odds=30.0),
    Strategy("all_fav_1pt", "全候補・市場人気1点", seed_only=False, main_count=1, score_mode="favorite"),
    Strategy("all_fav_2pt", "全候補・市場人気2点", seed_only=False, main_count=2, score_mode="favorite"),

    # v3追加: 人気順位帯
    Strategy("all_fav_rank1_3", "全候補・市場人気1〜3番人気を3点買い", seed_only=False, main_count=3, score_mode="favorite", fav_rank_min=1, fav_rank_max=3),
    Strategy("all_fav_rank1_5", "全候補・市場人気1〜5番人気を5点買い", seed_only=False, main_count=5, score_mode="favorite", fav_rank_min=1, fav_rank_max=5),
    Strategy("all_fav_rank1_3_prob1", "全候補・市場人気1〜3番人気から予測確率1点", seed_only=False, main_count=1, score_mode="prob", fav_rank_min=1, fav_rank_max=3),
    Strategy("all_fav_rank1_5_prob1", "全候補・市場人気1〜5番人気から予測確率1点", seed_only=False, main_count=1, score_mode="prob", fav_rank_min=1, fav_rank_max=5),

    # v3追加: オッズ帯別
    Strategy("all_odds3_15_prob1", "全候補・オッズ3〜15倍・確率1点", seed_only=False, main_count=1, score_mode="prob", min_odds=3.0, max_odds=15.0),
    Strategy("all_odds4_25_prob1", "全候補・オッズ4〜25倍・確率1点", seed_only=False, main_count=1, score_mode="prob", min_odds=4.0, max_odds=25.0),
    Strategy("all_odds6_30_prob1", "全候補・オッズ6〜30倍・確率1点", seed_only=False, main_count=1, score_mode="prob", min_odds=6.0, max_odds=30.0),
    Strategy("all_odds3_15_prob2", "全候補・オッズ3〜15倍・確率2点", seed_only=False, main_count=2, score_mode="prob", min_odds=3.0, max_odds=15.0),
    Strategy("all_odds4_25_prob2", "全候補・オッズ4〜25倍・確率2点", seed_only=False, main_count=2, score_mode="prob", min_odds=4.0, max_odds=25.0),

    # シード戦限定
    Strategy("seed_prob_1pt", "シード戦限定・1頭固定・予測確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob"),
    Strategy("seed_prob_2pt", "シード戦限定・1頭固定・予測確率2点", seed_only=True, first_fixed=1, main_count=2, score_mode="prob"),
    Strategy("seed_ev_1pt", "シード戦限定・1頭固定・EV1点・30倍以下", seed_only=True, first_fixed=1, main_count=1, score_mode="ev", max_odds=30.0),
    Strategy("seed_ev_2pt", "シード戦限定・1頭固定・EV2点・30倍以下", seed_only=True, first_fixed=1, main_count=2, score_mode="ev", max_odds=30.0),
    Strategy("seed_fav_1pt", "シード戦限定・1頭固定・市場人気1点", seed_only=True, first_fixed=1, main_count=1, score_mode="favorite"),
    Strategy("seed_fav_2pt", "シード戦限定・1頭固定・市場人気2点", seed_only=True, first_fixed=1, main_count=2, score_mode="favorite"),

    # v3追加: シード戦×人気順位帯
    Strategy("seed_fav_rank1_3", "シード戦・1頭固定・候補内人気1〜3番人気を3点買い", seed_only=True, first_fixed=1, main_count=3, score_mode="favorite", fav_rank_min=1, fav_rank_max=3),
    Strategy("seed_fav_rank1_5", "シード戦・1頭固定・候補内人気1〜5番人気を5点買い", seed_only=True, first_fixed=1, main_count=5, score_mode="favorite", fav_rank_min=1, fav_rank_max=5),
    Strategy("seed_fav_rank1_3_prob1", "シード戦・1頭固定・候補内人気1〜3から確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob", fav_rank_min=1, fav_rank_max=3),
    Strategy("seed_fav_rank1_5_prob1", "シード戦・1頭固定・候補内人気1〜5から確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob", fav_rank_min=1, fav_rank_max=5),

    # v3追加: シード戦×オッズ帯
    Strategy("seed_odds3_15_prob1", "シード戦・1頭固定・オッズ3〜15倍・確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob", min_odds=3.0, max_odds=15.0),
    Strategy("seed_odds4_25_prob1", "シード戦・1頭固定・オッズ4〜25倍・確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob", min_odds=4.0, max_odds=25.0),
    Strategy("seed_odds6_30_prob1", "シード戦・1頭固定・オッズ6〜30倍・確率1点", seed_only=True, first_fixed=1, main_count=1, score_mode="prob", min_odds=6.0, max_odds=30.0),
    Strategy("seed_odds3_15_prob2", "シード戦・1頭固定・オッズ3〜15倍・確率2点", seed_only=True, first_fixed=1, main_count=2, score_mode="prob", min_odds=3.0, max_odds=15.0),
    Strategy("seed_odds4_25_prob2", "シード戦・1頭固定・オッズ4〜25倍・確率2点", seed_only=True, first_fixed=1, main_count=2, score_mode="prob", min_odds=4.0, max_odds=25.0),

    # 暫定運用ルール: 本線+保険
    Strategy("seed_main1_ins1_prob", "シード戦限定・本線1点＋保険1点・確率順", seed_only=True, first_fixed=1, main_count=1, insurance_count=1, score_mode="prob"),
    Strategy("seed_main2_ins1_prob", "シード戦限定・本線2点＋保険1点・確率順", seed_only=True, first_fixed=1, main_count=2, insurance_count=1, score_mode="prob"),
    Strategy("seed_rule_v1_prob", "シード戦限定・本線2点＋保険6倍以上・確率順", seed_only=True, first_fixed=1, main_count=2, insurance_count=1, insurance_min_odds=INSURANCE_MIN_ODDS, score_mode="prob"),
]


def _filter_candidates(candidates: List[Dict[str, Any]], st: Strategy) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for c in candidates:
        ticket = c["ticket"]
        if st.first_fixed is not None:
            if int(ticket.split("-")[0]) != int(st.first_fixed):
                continue
        if c["odds"] < st.min_odds or c["odds"] > st.max_odds:
            continue
        if c["ev"] < st.min_ev:
            continue
        rows.append(dict(c))

    # 絞り込み後の候補内人気順位を付与
    rows_by_fav = sorted(rows, key=lambda x: (x["odds"], -x["prob"]))
    for rank, row in enumerate(rows_by_fav, start=1):
        row["fav_rank_in_scope"] = rank

    # fav_rank フィルタ適用
    if st.fav_rank_min is not None:
        rows_by_fav = [r for r in rows_by_fav if r.get("fav_rank_in_scope", 9999) >= st.fav_rank_min]
    if st.fav_rank_max is not None:
        rows_by_fav = [r for r in rows_by_fav if r.get("fav_rank_in_scope", 9999) <= st.fav_rank_max]

    # フィルタ後に再付番
    for rank, row in enumerate(rows_by_fav, start=1):
        row["fav_rank_in_scope"] = rank

    rows = rows_by_fav

    if st.score_mode == "favorite":
        rows.sort(key=lambda x: (x["fav_rank_in_scope"], -x["prob"]))
    elif st.score_mode == "ev":
        rows.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
    else:
        rows.sort(key=lambda x: (x["prob"], x["ev"]), reverse=True)
    return rows


def _select_bets_for_strategy(candidates: List[Dict[str, Any]], st: Strategy) -> List[Dict[str, Any]]:
    rows = _filter_candidates(candidates, st)
    if not rows:
        return []

    bets: List[Dict[str, Any]] = []

    for c in rows:
        if len(bets) >= st.main_count:
            break
        b = dict(c)
        b["label"] = "main"
        bets.append(b)

    if not bets:
        return []

    if st.insurance_count > 0:
        used = {b["ticket"] for b in bets}
        insurance_candidates = [
            c for c in rows
            if c["ticket"] not in used and c["odds"] >= st.insurance_min_odds
        ]
        insurance_candidates.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)

        ins_added = 0
        main_points = len(bets)
        for c in insurance_candidates:
            if ins_added >= st.insurance_count:
                break
            projected_points = main_points + ins_added + 1
            projected_stake = projected_points * UNIT_YEN
            projected_payout = c["odds"] * UNIT_YEN
            if st.require_insurance_no_trigami and projected_payout < projected_stake:
                continue
            b = dict(c)
            b["label"] = "insurance"
            bets.append(b)
            ins_added += 1

    return bets


@dataclass
class RaceCandidate:
    race_id: str
    race_date: str
    venue_id: str
    race_no: int
    strategy: str
    bets: List[Dict[str, Any]]
    actual_ticket: str
    actual_payout_yen: int
    is_seed: bool
    priority: float


@dataclass
class StrategyStats:
    name: str
    description: str
    eligible_before_budget: int = 0
    eligible_races: int = 0
    adopted_races: int = 0
    hit_races: int = 0
    main_hits: int = 0
    insurance_hits: int = 0
    trigami_hits: int = 0
    total_points: int = 0
    total_stake_yen: int = 0
    total_payout_yen: int = 0
    profit_yen: int = 0
    max_losing_streak: int = 0
    _cur_losing_streak: int = field(default=0, repr=False)
    daily: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def add_eligible_before_budget(self) -> None:
        self.eligible_before_budget += 1

    def adopt(self, rc: RaceCandidate) -> None:
        points = len(rc.bets)
        stake = points * UNIT_YEN

        payout = 0
        hit = False
        hit_label = None
        for b in rc.bets:
            if b["ticket"] == rc.actual_ticket:
                payout = int(rc.actual_payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
                hit = True
                hit_label = b.get("label")
                break
        profit = payout - stake

        self.eligible_races += 1
        self.adopted_races += 1
        self.total_points += points
        self.total_stake_yen += stake
        self.total_payout_yen += payout
        self.profit_yen += profit

        if hit:
            self.hit_races += 1
            if hit_label == "insurance":
                self.insurance_hits += 1
            else:
                self.main_hits += 1
            if payout < stake:
                self.trigami_hits += 1
            self._cur_losing_streak = 0
        else:
            self._cur_losing_streak += 1
            self.max_losing_streak = max(self.max_losing_streak, self._cur_losing_streak)

        d = self.daily.setdefault(
            rc.race_date,
            {"races": 0, "points": 0, "stake": 0, "payout": 0, "profit": 0, "hits": 0},
        )
        d["races"] += 1
        d["points"] += points
        d["stake"] += stake
        d["payout"] += payout
        d["profit"] += profit
        if hit:
            d["hits"] += 1

    def summary_row(self) -> Dict[str, Any]:
        roi = (self.total_payout_yen / self.total_stake_yen * 100.0) if self.total_stake_yen else 0.0
        hit_rate = (self.hit_races / self.adopted_races * 100.0) if self.adopted_races else 0.0
        trigami_rate = (self.trigami_hits / self.hit_races * 100.0) if self.hit_races else 0.0
        days = len(self.daily)
        avg_points = self.total_points / days if days else 0.0
        avg_profit = self.profit_yen / days if days else 0.0
        worst_day = min((d["profit"] for d in self.daily.values()), default=0)
        best_day = max((d["profit"] for d in self.daily.values()), default=0)
        return {
            "strategy": self.name,
            "description": self.description,
            "eligible_before_budget": self.eligible_before_budget,
            "eligible_races": self.eligible_races,
            "adopted_races": self.adopted_races,
            "hit_races": self.hit_races,
            "hit_rate": round(hit_rate, 2),
            "main_hits": self.main_hits,
            "insurance_hits": self.insurance_hits,
            "trigami_hits": self.trigami_hits,
            "trigami_rate": round(trigami_rate, 2),
            "total_points": self.total_points,
            "total_stake_yen": self.total_stake_yen,
            "total_payout_yen": self.total_payout_yen,
            "profit_yen": self.profit_yen,
            "roi": round(roi, 2),
            "max_losing_streak": self.max_losing_streak,
            "active_days": days,
            "avg_points_per_day": round(avg_points, 2),
            "avg_profit_per_day": round(avg_profit, 2),
            "best_day_profit": best_day,
            "worst_day_profit": worst_day,
        }


# ============================================================
# Backtest main
# ============================================================

def _build_day_candidates(
    race_date: str,
    races: List[Dict[str, Any]],
    results: Dict[str, Dict[str, Any]],
    entries_by_race: Dict[str, List[Dict[str, Any]]],
    odds_by_race: Dict[str, Dict[str, float]],
    stats: Dict[str, StrategyStats],
) -> Dict[str, List[RaceCandidate]]:
    by_strategy: Dict[str, List[RaceCandidate]] = {s.name: [] for s in STRATEGIES}

    for r in races:
        rid = r.get("race_id")
        venue_id = str(r.get("venue_id", "")).zfill(2)
        race_no = _safe_int(r.get("race_no"), 0)
        result = results.get(rid)
        entries = entries_by_race.get(rid, [])
        odds = odds_by_race.get(rid, {})

        if not _is_backtest_ready(result, entries, odds):
            continue

        is_seed = _is_seed_race(entries)
        candidates = _rank_candidates(entries, venue_id, odds)
        if not candidates:
            continue

        actual_ticket = _get_actual_ticket(result)
        actual_payout = _safe_int(result.get("trifecta_payout_yen"), 0)

        for st in STRATEGIES:
            if st.seed_only and not is_seed:
                continue

            bets = _select_bets_for_strategy(candidates, st)
            if not bets:
                continue

            stats[st.name].add_eligible_before_budget()

            if st.score_mode == "favorite":
                priority = max(
                    (1.0 / max(_safe_float(b.get("odds"), 9999.0), 1.0) for b in bets),
                    default=0.0,
                )
            elif st.score_mode == "ev":
                priority = max((_safe_float(b.get("ev"), 0.0) for b in bets), default=0.0)
            else:
                priority = max((_safe_float(b.get("prob"), 0.0) for b in bets), default=0.0)

            by_strategy[st.name].append(
                RaceCandidate(
                    race_id=rid,
                    race_date=race_date,
                    venue_id=venue_id,
                    race_no=race_no,
                    strategy=st.name,
                    bets=bets,
                    actual_ticket=actual_ticket,
                    actual_payout_yen=actual_payout,
                    is_seed=is_seed,
                    priority=priority,
                )
            )

    return by_strategy


def _apply_daily_budget(candidates: List[RaceCandidate], fair_budget: bool = FAIR_BUDGET) -> List[RaceCandidate]:
    """
    FAIR_BUDGET=False:
      点数合計で日次上限を管理。実運用検証はこちら推奨。

    FAIR_BUDGET=True:
      採用レース数で日次上限を管理。戦略間のレース数比較用。
      5点買い戦略は投資額が増える点に注意。
    """
    if DAILY_BUDGET_YEN <= 0:
        return candidates

    rows = sorted(candidates, key=lambda x: (-x.priority, len(x.bets)))
    selected: List[RaceCandidate] = []

    if fair_budget:
        for rc in rows:
            if len(selected) >= DAILY_MAX_POINTS:
                break
            selected.append(rc)
    else:
        used_points = 0
        for rc in rows:
            points = len(rc.bets)
            if used_points + points > DAILY_MAX_POINTS:
                continue
            selected.append(rc)
            used_points += points

    selected.sort(key=lambda x: (x.race_date, x.venue_id, x.race_no))
    return selected


def _write_csv(summary_rows: List[Dict[str, Any]], stats: Dict[str, StrategyStats]) -> None:
    if not WRITE_CSV:
        return
    os.makedirs(CSV_DIR, exist_ok=True)
    stamp = f"{START_DATE}_{END_DATE}".replace("-", "")
    summary_path = os.path.join(CSV_DIR, f"backtest_summary_{stamp}.csv")
    daily_path = os.path.join(CSV_DIR, f"backtest_daily_{stamp}.csv")

    if summary_rows:
        with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader()
            w.writerows(summary_rows)
        print(f"CSV summary: {summary_path}", flush=True)

    daily_rows: List[Dict[str, Any]] = []
    for name, st in stats.items():
        for d, row in sorted(st.daily.items()):
            r = {"strategy": name, "race_date": d}
            r.update(row)
            daily_rows.append(r)

    if daily_rows:
        with open(daily_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(daily_rows[0].keys()))
            w.writeheader()
            w.writerows(daily_rows)
        print(f"CSV daily: {daily_path}", flush=True)


def main() -> None:
    assert PAYOUT_BASE_YEN > 0, f"PAYOUT_BASE_YEN must be > 0, got {PAYOUT_BASE_YEN}"

    _require_settings()
    print("=== 複数パターン・バックテスト開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"venues: {','.join(TARGET_VENUES)}", flush=True)
    print(f"unit: {UNIT_YEN}円 / payout_base: {PAYOUT_BASE_YEN}円", flush=True)
    print(f"daily_budget: {DAILY_BUDGET_YEN}円 / max_points={DAILY_MAX_POINTS} fair_budget={FAIR_BUDGET}", flush=True)
    print(f"min_ev={MIN_EV} min_odds={MIN_ODDS} max_odds={MAX_ODDS} insurance_min_odds={INSURANCE_MIN_ODDS}", flush=True)
    print(f"strict_seed={STRICT_SEED} prob_temp={PROB_TEMP}", flush=True)
    print(f"odds_page_size={ODDS_PAGE_SIZE} retry_max={RETRY_MAX} day_sleep={DAY_SLEEP}s", flush=True)
    print(f"log: verbose={VERBOSE_LOG} every_days={LOG_EVERY_DAYS} adopted_counts={PRINT_ADOPTED_COUNTS} json_summary={PRINT_JSON_SUMMARY} top_n={SUMMARY_TOP_N}", flush=True)

    stats: Dict[str, StrategyStats] = {s.name: StrategyStats(s.name, s.description) for s in STRATEGIES}

    total_ready = 0
    total_races_seen = 0
    total_seed_ready = 0
    dates = list(_daterange(START_DATE, END_DATE))

    for idx, race_date in enumerate(dates, start=1):
        t0 = time.time()
        races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)
        total_races_seen += len(races)

        ready_today = 0
        seed_today = 0
        for r in races:
            rid = r.get("race_id")
            if _is_backtest_ready(results.get(rid), entries_by_race.get(rid, []), odds_by_race.get(rid, {})):
                ready_today += 1
                if _is_seed_race(entries_by_race.get(rid, [])):
                    seed_today += 1
        total_ready += ready_today
        total_seed_ready += seed_today

        day_candidates = _build_day_candidates(race_date, races, results, entries_by_race, odds_by_race, stats)

        adopted_total = 0
        adopted_counts = []
        for st in STRATEGIES:
            selected = _apply_daily_budget(day_candidates[st.name])
            for rc in selected:
                stats[st.name].adopt(rc)
            adopted_total += len(selected)
            if PRINT_ADOPTED_COUNTS:
                adopted_counts.append(f"{st.name}:{len(selected)}R")

        should_log = False
        if VERBOSE_LOG:
            should_log = True
        elif LOG_EVERY_DAYS > 0 and (idx == 1 or idx == len(dates) or idx % LOG_EVERY_DAYS == 0):
            should_log = True

        if should_log:
            if PRINT_ADOPTED_COUNTS:
                adopted_text = f" adopted({', '.join(adopted_counts)})"
            else:
                adopted_text = f" adopted_total={adopted_total}"
            print(
                f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={ready_today} seed={seed_today}"
                f"{adopted_text} elapsed={time.time() - t0:.1f}s",
                flush=True,
            )

        if DAY_SLEEP > 0 and idx < len(dates):
            time.sleep(DAY_SLEEP)

    print("\n" + "=" * 88, flush=True)
    print("バックテスト最終結果", flush=True)
    print("=" * 88, flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"読み込みレース数: {total_races_seen}", flush=True)
    print(f"backtest_ready: {total_ready}", flush=True)
    print(f"seed_ready: {total_seed_ready}", flush=True)
    print(f"日次上限: {DAILY_BUDGET_YEN}円 / fair_budget={FAIR_BUDGET}", flush=True)

    summary_rows = [stats[s.name].summary_row() for s in STRATEGIES]
    summary_rows.sort(key=lambda r: (r["roi"], r["profit_yen"]), reverse=True)

    print(f"\n--- 戦略別サマリー ROI順 Top {SUMMARY_TOP_N} ---", flush=True)
    for r in summary_rows[:SUMMARY_TOP_N]:
        print(
            f"{r['strategy']:<22} "
            f"採用{r['adopted_races']:>5}R/{r['total_points']:>5}点 "
            f"的中{r['hit_races']:>4}R({r['hit_rate']:>5.1f}%) "
            f"投資{r['total_stake_yen']:>9,}円 "
            f"回収{r['total_payout_yen']:>9,}円 "
            f"損益{r['profit_yen']:>+9,}円 "
            f"ROI{r['roi']:>6.1f}% "
            f"保険的中{r['insurance_hits']:>3} "
            f"最大連敗{r['max_losing_streak']:>3} "
            f"予算前eligible{r['eligible_before_budget']:>5}",
            flush=True,
        )

    if PRINT_JSON_SUMMARY:
        print("\n--- JSON summary ---", flush=True)
        print(json.dumps(summary_rows, ensure_ascii=False, indent=2), flush=True)
    else:
        print("\nJSON summary: skipped. CSV summary を確認してください。", flush=True)

    _write_csv(summary_rows, stats)
    print("=== 複数パターン・バックテスト終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        raise