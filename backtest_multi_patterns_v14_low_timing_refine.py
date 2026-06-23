# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v12_stage_diagnostics.py

競艇AI v2用・v11有望条件に対する開催ステージ診断。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python backtest_multi_patterns_v14_low_timing_refine.py

必要Variables:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY もしくは SUPABASE_KEY
    RAILPACK_PYTHON_VERSION=3.11 推奨
"""

from __future__ import annotations

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

RUN_CONFIG = {
    "start_date": "2025-03-13",
    "end_date": "2026-05-31",
    "venues": [f"{i:02d}" for i in range(1, 25)],
    "unit_yen": 100,
    "daily_budget_yen": 1000,
    "fair_budget": False,
    "strict_seed": True,
    "prob_temp": 2.20,
    "odds_page_size": 1000,
    "page_size": 1000,
    "http_timeout": 25,
    "retry_max": 2,
    "retry_sleep": 2.0,
    "day_sleep": 0.0,
    "log_every_days": 14,
    "summary_top_n": 25,
    # v8診断では購入せず、全期間をポケット集計に使う。
    "burn_in_days": 0,
    # 補正ROI計算で1本の大穴に引っ張られないよう払戻を上限クリップする。
    "calib_payout_clip_yen": 30000,
    # 低調場除外テスト。v6でbottom寄りだった場。
    "bad_venues": ["01", "04", "05", "06", "23"],
    # 耐久チェック対象月
    "focus_exclude_months": ["2026-05", "2025-05"],
}

START_DATE = RUN_CONFIG["start_date"]
END_DATE = RUN_CONFIG["end_date"]
TARGET_VENUES = [str(v).zfill(2) for v in RUN_CONFIG["venues"]]
UNIT_YEN = int(RUN_CONFIG["unit_yen"])
DAILY_BUDGET_YEN = int(RUN_CONFIG["daily_budget_yen"])
DAILY_MAX_POINTS = DAILY_BUDGET_YEN // UNIT_YEN if DAILY_BUDGET_YEN > 0 else 10**9
FAIR_BUDGET = bool(RUN_CONFIG["fair_budget"])
STRICT_SEED = bool(RUN_CONFIG["strict_seed"])
PROB_TEMP = float(RUN_CONFIG["prob_temp"])
ODDS_PAGE_SIZE = int(RUN_CONFIG["odds_page_size"])
PAGE_SIZE = int(RUN_CONFIG["page_size"])
HTTP_TIMEOUT = int(RUN_CONFIG["http_timeout"])
RETRY_MAX = int(RUN_CONFIG["retry_max"])
RETRY_SLEEP = float(RUN_CONFIG["retry_sleep"])
DAY_SLEEP = float(RUN_CONFIG["day_sleep"])
LOG_EVERY_DAYS = int(RUN_CONFIG["log_every_days"])
SUMMARY_TOP_N = int(RUN_CONFIG["summary_top_n"])
BURN_IN_DAYS = int(RUN_CONFIG["burn_in_days"])
CALIB_PAYOUT_CLIP_YEN = int(RUN_CONFIG["calib_payout_clip_yen"])
BAD_VENUES = tuple(str(v).zfill(2) for v in RUN_CONFIG["bad_venues"])
FOCUS_EXCLUDE_MONTHS = [str(x) for x in RUN_CONFIG["focus_exclude_months"]]
PAYOUT_BASE_YEN = 100

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

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
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY が必要です。")


def _daterange(start_str: str, end_str: str) -> Iterable[str]:
    d = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def _next_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _shift_day(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def _rid_prefix(date_str: str) -> str:
    return date_str.replace("-", "")


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
    if ticket is None:
        return ""
    s = unicodedata.normalize("NFKC", str(ticket))
    nums = re.findall(r"[1-6]", s)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return s.strip()


def _get_actual_ticket(result: Dict[str, Any]) -> str:
    t = _norm_ticket(result.get("trifecta_ticket"))
    if t:
        return t
    a = result.get("first_lane")
    b = result.get("second_lane")
    c = result.get("third_lane")
    if a is not None and b is not None and c is not None:
        return f"{_safe_int(a)}-{_safe_int(b)}-{_safe_int(c)}"
    return ""


def _http_get_with_retry(url: str) -> List[Dict[str, Any]]:
    last_err: Optional[Exception] = None
    for attempt in range(1, RETRY_MAX + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            return r.json()
        except Exception as e:
            last_err = e
            if attempt < RETRY_MAX:
                print(f"  [retry {attempt}/{RETRY_MAX}] {e} — {RETRY_SLEEP}s後に再試行", flush=True)
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
        offset += len(part)
    return rows


def _rest_get_range(table: str, select: str, col: str, gte: str, lt: str, page_size: int = PAGE_SIZE) -> List[Dict[str, Any]]:
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
        offset += len(part)
    return rows


def _fetch_day_rows(date_str: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, float]]]:
    day_prefix = _rid_prefix(date_str)
    next_prefix = _rid_prefix(_next_day(date_str))

    # 現DBでは v2_races.race_name が存在しない環境があるため、
    # v12 fix1では schema-safe に基本列だけ取得する。
    # 準優/優勝戦などの「レース名分類」は unavailable になり、
    # 代わりに会場別の連続開催日 + レース番号で推定ステージを見る。
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
    entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries_rows:
        entries_by_race.setdefault(e.get("race_id"), []).append(e)

    odds_rows = _rest_get_range(
        "v2_odds_trifecta",
        select="race_id,ticket,odds",
        col="race_id",
        gte=day_prefix,
        lt=next_prefix,
        page_size=ODDS_PAGE_SIZE,
    )
    odds_by_race: Dict[str, Dict[str, float]] = {}
    for o in odds_rows:
        rid = o.get("race_id")
        t = _norm_ticket(o.get("ticket"))
        odd = _safe_float(o.get("odds"), 0.0)
        if rid and t and odd > 0:
            odds_by_race.setdefault(rid, {})[t] = odd

    return races, results, entries_by_race, odds_by_race


def _entry_by_lane(entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    by_lane: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        lane = _safe_int(e.get("lane"), 0)
        if 1 <= lane <= 6:
            by_lane[lane] = e
    return by_lane


def _is_backtest_ready(result: Optional[Dict[str, Any]], entries: List[Dict[str, Any]], odds: Dict[str, float]) -> bool:
    if not result:
        return False
    if result.get("result_status") not in ("official", "parse_incomplete"):
        return False
    actual = _get_actual_ticket(result)
    if not actual:
        return False
    if _safe_int(result.get("trifecta_payout_yen"), 0) <= 0:
        return False
    by_lane = _entry_by_lane(entries)
    if len(by_lane) != 6:
        return False
    for lane in range(1, 7):
        e = by_lane.get(lane, {})
        if e.get("racer_number") is None or e.get("racer_class") is None:
            return False
    return len(odds) == 120


def _is_seed_race(entries: List[Dict[str, Any]], strict: bool = STRICT_SEED) -> bool:
    by_lane = _entry_by_lane(entries)
    if len(by_lane) != 6:
        return False
    lane1_cls = _safe_int(by_lane[1].get("racer_class"), 0)
    if lane1_cls not in (3, 4):
        return False
    if not strict:
        return True
    for lane in range(2, 7):
        if _safe_int(by_lane[lane].get("racer_class"), 0) not in (1, 2):
            return False
    return True


def _lane_raw_strength(entry: Dict[str, Any], lane: int, venue_id: str) -> float:
    cls = _safe_int(entry.get("racer_class"), 2)
    cls_w = CLASS_WEIGHT.get(cls, 0.55)
    win_rate = _safe_float(entry.get("national_win_rate"), 0.0)
    nat2 = _safe_float(entry.get("national_place2_rate"), 32.0)
    loc2 = _safe_float(entry.get("local_place2_rate"), 30.0)
    mot2 = 33.0
    boat2 = 34.0
    avg_st = _safe_float(entry.get("avg_st"), 0.18)
    course_bias = VENUE_COURSE_BIAS.get(venue_id, DEFAULT_COURSE_BIAS).get(lane, DEFAULT_COURSE_BIAS[lane])
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        cls_w * 1.00
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def _ticket_probabilities(entries: List[Dict[str, Any]], venue_id: str) -> Dict[str, float]:
    by_lane = _entry_by_lane(entries)
    raw = {lane: _lane_raw_strength(by_lane[lane], lane, venue_id) for lane in range(1, 7)}
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
                if c == a or c == b:
                    continue
                pc = weights[c] / total_c
                probs[f"{a}-{b}-{c}"] = pa * pb * pc
    return probs


def _rank_candidates(entries: List[Dict[str, Any]], venue_id: str, odds: Dict[str, float]) -> List[Dict[str, Any]]:
    probs = _ticket_probabilities(entries, venue_id)
    rows: List[Dict[str, Any]] = []
    for ticket, prob in probs.items():
        odd = _safe_float(odds.get(ticket), 0.0)
        if odd <= 0:
            continue
        row = {"ticket": ticket, "prob": prob, "odds": odd, "raw_ev": prob * odd}
        rows.append(row)

    for rank, row in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), start=1):
        row["market_rank"] = rank
    for rank, row in enumerate(sorted(rows, key=lambda x: x["prob"], reverse=True), start=1):
        row["prob_rank"] = rank
    for rank, row in enumerate(sorted(rows, key=lambda x: x["raw_ev"], reverse=True), start=1):
        row["ev_rank"] = rank

    rows.sort(key=lambda x: x["prob"], reverse=True)
    return rows



def _head_lane(ticket: str) -> str:
    s = _norm_ticket(ticket)
    if not s:
        return "?"
    return s.split("-")[0]


def _race_group(race_no: int) -> str:
    if race_no <= 3:
        return "R01_03"
    if race_no <= 6:
        return "R04_06"
    if race_no <= 9:
        return "R07_09"
    return "R10_12"


def _normalize_jp_text(s: Any) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).strip()


def _race_title_stage(race_name: Any) -> str:
    """
    race_nameからレース種別を分類する。
    優先順位は 準優 > 優勝 > ドリーム > 選抜/特選 > 一般 > 予選 > その他。
    """
    name = _normalize_jp_text(race_name)

    if not name:
        return "stage_unknown"

    # 準優勝戦は「優勝戦」より先に判定する
    if "準優" in name:
        return "semifinal"

    # 「優勝戦」は最終12Rが多いが、優勝戦出場者選抜などのノイズもあるため完全ではない
    if "優勝" in name and "準優" not in name:
        return "final"

    if "ドリーム" in name or "DR" in name.upper():
        return "dream"

    if "選抜" in name or "特選" in name or "特賞" in name:
        return "selection"

    if "一般" in name:
        return "general"

    if "予選" in name:
        return "qualifying"

    if "シーボー" in name or "シード" in name:
        return "seed_named"

    return "stage_other"


def _event_day_group(day_no: int) -> str:
    if day_no <= 0:
        return "event_unknown"
    if day_no == 1:
        return "event_day1"
    if day_no == 2:
        return "event_day2"
    if day_no == 3:
        return "event_day3"
    if day_no == 4:
        return "event_day4"
    if day_no == 5:
        return "event_day5"
    return "event_day6plus"


def _event_day_broad(day_no: int) -> str:
    if day_no <= 0:
        return "event_unknown"
    if day_no == 1:
        return "event_day1"
    if 2 <= day_no <= 3:
        return "event_day2_3"
    if 4 <= day_no <= 5:
        return "event_day4_5"
    return "event_day6plus"


def _stage_combo(title_stage: str, day_no: int, race_no: int = 0) -> str:
    # レース名が取れる場合はそれを優先。
    if title_stage in ("semifinal", "final", "dream", "selection", "general", "qualifying"):
        return title_stage

    # 現DBでは race_name が無いので、開催日数とレース番号で推定分類する。
    # 完全な準優/優勝判定ではないが、初日・終盤後半Rの影響を見るための診断として使う。
    if day_no <= 0:
        return "inferred_unknown"
    if day_no == 1:
        return "inferred_day1"
    if 2 <= day_no <= 3:
        return "inferred_day2_3"
    if 4 <= day_no <= 5 and race_no >= 10:
        return "inferred_late_r10_12"
    if 4 <= day_no <= 5:
        return "inferred_day4_5_other"
    if day_no >= 6 and race_no == 12:
        return "inferred_finalday_r12"
    if day_no >= 6 and race_no >= 10:
        return "inferred_finalday_r10_12"
    if day_no >= 6:
        return "inferred_finalday_other"
    return "inferred_other"


@dataclass
class V14Strategy:
    name: str
    description: str
    include_mid: bool = False
    include_low: bool = False

    # LOW: prob_rank11-20 × market_rank1 × odds3-5 に対する追加条件
    low_filter: str = "all"
    low_stage_filter: str = "all"

    # MID: 比較用。v14では主役ではないが、通常+馬王の接続確認に使う
    mid_max_points: int = 1
    low_max_points: int = 1
    mid_non_head1: bool = True
    mid_race_filter: str = "all"
    mid_stage_filter: str = "all"

    mid_priority: str = "prob"
    low_priority: str = "prob"
    prefer_mid: bool = True


# v14は通常モード本命の「低オッズ」をさらに絞る。
# 目的: ROI維持ではなく、最大連敗を短くしつつ採用数を残すこと。
V14_STRATEGIES: List[V14Strategy] = [
    # ---- 基準 ----
    V14Strategy(
        "low_exR10_12_base",
        "基準: 低オッズ 10〜12R除外",
        include_low=True,
        low_filter="exclude_r10_12",
    ),

    # ---- 初日を扱うか ----
    V14Strategy(
        "low_exR10_12_no_day1",
        "低オッズ 10〜12R除外 + 初日除外",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="not_day1",
    ),
    V14Strategy(
        "low_exR10_12_day2_3",
        "低オッズ 10〜12R除外 + 2〜3日目だけ",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_3",
    ),
    V14Strategy(
        "low_exR10_12_day2_4",
        "低オッズ 10〜12R除外 + 2〜4日目だけ",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_4",
    ),
    V14Strategy(
        "low_exR10_12_day2_3_or_day6plus",
        "低オッズ 10〜12R除外 + 2〜3日目 or 終盤日",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_3_or_day6plus",
    ),
    V14Strategy(
        "low_exR10_12_day2_4_or_day6plus",
        "低オッズ 10〜12R除外 + 2〜4日目 or 終盤日",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_4_or_day6plus",
    ),

    # ---- R04〜09との組み合わせ ----
    V14Strategy(
        "low_r04_09_base",
        "比較: 低オッズ 4〜9R",
        include_low=True,
        low_filter="r04_09",
    ),
    V14Strategy(
        "low_r04_09_no_day1",
        "低オッズ 4〜9R + 初日除外",
        include_low=True,
        low_filter="r04_09",
        low_stage_filter="not_day1",
    ),
    V14Strategy(
        "low_r04_09_day2_3",
        "低オッズ 4〜9R + 2〜3日目だけ",
        include_low=True,
        low_filter="r04_09",
        low_stage_filter="day2_3",
    ),
    V14Strategy(
        "low_r04_09_day2_4",
        "低オッズ 4〜9R + 2〜4日目だけ",
        include_low=True,
        low_filter="r04_09",
        low_stage_filter="day2_4",
    ),
    V14Strategy(
        "low_r04_09_day2_3_or_day6plus",
        "低オッズ 4〜9R + 2〜3日目 or 終盤日",
        include_low=True,
        low_filter="r04_09",
        low_stage_filter="day2_3_or_day6plus",
    ),

    # ---- レース帯の切り分け ----
    V14Strategy(
        "low_r01_03_day2_3",
        "低オッズ 1〜3R + 2〜3日目",
        include_low=True,
        low_filter="r01_03",
        low_stage_filter="day2_3",
    ),
    V14Strategy(
        "low_r04_06_day2_3",
        "低オッズ 4〜6R + 2〜3日目",
        include_low=True,
        low_filter="r04_06",
        low_stage_filter="day2_3",
    ),
    V14Strategy(
        "low_r07_09_day2_3",
        "低オッズ 7〜9R + 2〜3日目",
        include_low=True,
        low_filter="r07_09",
        low_stage_filter="day2_3",
    ),
    V14Strategy(
        "low_r07_09_day2_3_or_day6plus",
        "低オッズ 7〜9R + 2〜3日目 or 終盤日",
        include_low=True,
        low_filter="r07_09",
        low_stage_filter="day2_3_or_day6plus",
    ),

    # ---- combo接続確認: 低オッズを絞った上で中穴終盤日を足す ----
    V14Strategy(
        "combo_low_exR10_12_day2_3_or_final_plus_mid_final",
        "低オッズexR10〜12 2〜3日目/終盤日 + 中穴終盤日",
        include_low=True,
        include_mid=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_3_or_day6plus",
        mid_stage_filter="day6plus",
        mid_race_filter="not_r04_06",
        mid_non_head1=True,
    ),
    V14Strategy(
        "combo_low_r04_09_day2_3_or_final_plus_mid_final",
        "低オッズR04〜09 2〜3日目/終盤日 + 中穴終盤日",
        include_low=True,
        include_mid=True,
        low_filter="r04_09",
        low_stage_filter="day2_3_or_day6plus",
        mid_stage_filter="day6plus",
        mid_race_filter="not_r04_06",
        mid_non_head1=True,
    ),

    # ---- 馬王モード接続確認: 中穴だけ ----
    V14Strategy(
        "bao_mid_finalday_nonhead_no_r04_06",
        "馬王比較: 中穴 終盤日 + 1頭除外 + R04〜06除外",
        include_mid=True,
        mid_stage_filter="day6plus",
        mid_race_filter="not_r04_06",
        mid_non_head1=True,
    ),
    V14Strategy(
        "bao_mid_day1_r01_03_nonhead",
        "馬王比較: 中穴 初日 + R01〜03 + 1頭除外",
        include_mid=True,
        mid_stage_filter="day1",
        mid_race_filter="r01_03",
        mid_non_head1=True,
    ),
]


@dataclass
class RaceCandidate:
    race_id: str
    race_date: str
    venue_id: str
    race_no: int
    race_name: str
    title_stage: str
    event_day_no: int
    event_day_group: str
    event_day_broad: str
    stage_combo: str
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
    adopted_races: int = 0
    hit_races: int = 0
    total_points: int = 0
    total_stake_yen: int = 0
    total_payout_yen: int = 0
    profit_yen: int = 0
    max_losing_streak: int = 0
    _cur_losing_streak: int = field(default=0, repr=False)

    def add_eligible_before_budget(self) -> None:
        self.eligible_before_budget += 1

    def adopt(self, rc: RaceCandidate) -> None:
        points = len(rc.bets)
        stake = points * UNIT_YEN
        payout = 0
        hit = False
        for b in rc.bets:
            if b["ticket"] == rc.actual_ticket:
                payout = int(rc.actual_payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
                hit = True
                break

        self.adopted_races += 1
        self.total_points += points
        self.total_stake_yen += stake
        self.total_payout_yen += payout
        self.profit_yen += payout - stake

        if hit:
            self.hit_races += 1
            self._cur_losing_streak = 0
        else:
            self._cur_losing_streak += 1
            self.max_losing_streak = max(self.max_losing_streak, self._cur_losing_streak)

    def row(self) -> Dict[str, Any]:
        roi = self.total_payout_yen / self.total_stake_yen * 100.0 if self.total_stake_yen else 0.0
        hit_rate = self.hit_races / self.adopted_races * 100.0 if self.adopted_races else 0.0
        return {
            "strategy": self.name,
            "description": self.description,
            "eligible_before_budget": self.eligible_before_budget,
            "adopted_races": self.adopted_races,
            "hit_races": self.hit_races,
            "hit_rate": hit_rate,
            "total_points": self.total_points,
            "total_stake_yen": self.total_stake_yen,
            "total_payout_yen": self.total_payout_yen,
            "profit_yen": self.profit_yen,
            "roi": roi,
            "max_losing_streak": self.max_losing_streak,
        }


def _match_stage_filter(filter_name: str, event_day_no: int, race_no: int, stage_combo: str) -> bool:
    if filter_name == "all":
        return True
    if filter_name == "day1":
        return event_day_no == 1
    if filter_name == "not_day1":
        return event_day_no != 1
    if filter_name == "day2_3":
        return event_day_no in (2, 3)
    if filter_name == "day2_4":
        return event_day_no in (2, 3, 4)
    if filter_name == "day6plus":
        return event_day_no >= 6
    if filter_name == "day1_or_day6plus":
        return event_day_no == 1 or event_day_no >= 6
    if filter_name == "day2_3_or_day6plus":
        return event_day_no in (2, 3) or event_day_no >= 6
    if filter_name == "day2_4_or_day6plus":
        return event_day_no in (2, 3, 4) or event_day_no >= 6
    if filter_name == "not_day5":
        return event_day_no != 5
    if filter_name == "not_day4_5":
        return event_day_no not in (4, 5)
    if filter_name == "not_day4_5_late":
        return not (event_day_no in (4, 5) and race_no >= 10)
    raise ValueError(f"unknown stage_filter: {filter_name}")


def _match_race_filter(filter_name: str, race_no: int) -> bool:
    if filter_name == "all":
        return True
    if filter_name == "r01_03":
        return 1 <= race_no <= 3
    if filter_name == "r04_06":
        return 4 <= race_no <= 6
    if filter_name == "r07_09":
        return 7 <= race_no <= 9
    if filter_name == "r04_09":
        return 4 <= race_no <= 9
    if filter_name == "not_r04_06":
        return not (4 <= race_no <= 6)
    if filter_name == "not_r10_12":
        return race_no <= 9
    raise ValueError(f"unknown race_filter: {filter_name}")


def _is_mid_candidate(
    row: Dict[str, Any],
    st: V14Strategy,
    race_no: int,
    event_day_no: int,
    stage_combo: str,
) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)
    if not (4 <= pr <= 5 and 21 <= mr <= 30 and 30.0 <= odds < 50.0):
        return False
    if st.mid_non_head1 and _head_lane(str(row.get("ticket", ""))) == "1":
        return False
    if not _match_stage_filter(st.mid_stage_filter, event_day_no, race_no, stage_combo):
        return False
    if not _match_race_filter(st.mid_race_filter, race_no):
        return False
    return True


def _is_low_candidate(
    row: Dict[str, Any],
    venue_id: str,
    race_no: int,
    low_filter: str,
    low_stage_filter: str,
    event_day_no: int,
    stage_combo: str,
) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)
    if not (11 <= pr <= 20 and mr == 1 and 3.0 <= odds < 5.0):
        return False

    is_bad5 = venue_id in BAD_VENUES

    if low_filter == "all":
        base_ok = True
    elif low_filter == "bad5":
        base_ok = is_bad5
    elif low_filter == "r01_03":
        base_ok = 1 <= race_no <= 3
    elif low_filter == "r04_06":
        base_ok = 4 <= race_no <= 6
    elif low_filter == "r07_09":
        base_ok = 7 <= race_no <= 9
    elif low_filter == "r04_09":
        base_ok = 4 <= race_no <= 9
    elif low_filter == "exclude_r10_12":
        base_ok = race_no <= 9
    else:
        raise ValueError(f"unknown low_filter: {low_filter}")

    if not base_ok:
        return False
    if not _match_stage_filter(low_stage_filter, event_day_no, race_no, stage_combo):
        return False
    return True


def _priority(row: Dict[str, Any], mode: str, label: str, prefer_mid: bool) -> float:
    prob = _safe_float(row.get("prob"), 0.0)
    odds = _safe_float(row.get("odds"), 0.0)
    ev = _safe_float(row.get("raw_ev"), 0.0)
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)

    label_boost = 100000.0 if (prefer_mid and label == "mid") else 0.0

    if mode == "odds":
        return label_boost + odds * 100.0 + prob * 10.0
    if mode == "ev":
        return label_boost + ev * 10000.0 + prob * 100.0 - pr * 0.01
    return label_boost + prob * 10000.0 + ev * 100.0 - pr * 0.01 - mr * 0.001


def _select_bets(
    rows: List[Dict[str, Any]],
    st: V14Strategy,
    venue_id: str,
    race_no: int,
    event_day_no: int,
    stage_combo: str,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []

    if st.include_mid:
        mids = []
        for r in rows:
            if _is_mid_candidate(r, st, race_no, event_day_no, stage_combo):
                x = dict(r)
                x["label"] = "mid"
                x["select_priority"] = _priority(x, st.mid_priority, "mid", st.prefer_mid)
                mids.append(x)
        mids.sort(key=lambda x: x["select_priority"], reverse=True)
        selected.extend(mids[:st.mid_max_points])

    if st.include_low:
        lows = []
        used = {x.get("ticket") for x in selected}
        for r in rows:
            if r.get("ticket") in used:
                continue
            if _is_low_candidate(r, venue_id, race_no, st.low_filter, st.low_stage_filter, event_day_no, stage_combo):
                x = dict(r)
                x["label"] = "low"
                x["select_priority"] = _priority(x, st.low_priority, "low", st.prefer_mid)
                lows.append(x)
        lows.sort(key=lambda x: x["select_priority"], reverse=True)
        selected.extend(lows[:st.low_max_points])

    return selected


def _apply_daily_budget(candidates: List[RaceCandidate]) -> List[RaceCandidate]:
    if not candidates:
        return []
    candidates = candidates[:]
    candidates.sort(key=lambda x: (x.priority, -len(x.bets)), reverse=True)
    selected: List[RaceCandidate] = []
    used_points = 0
    for rc in candidates:
        pts = len(rc.bets)
        if pts <= 0:
            continue
        if used_points + pts > DAILY_MAX_POINTS:
            continue
        selected.append(rc)
        used_points += pts
    return selected


def _record_from_rc(rc: RaceCandidate) -> Dict[str, Any]:
    points = len(rc.bets)
    stake = points * UNIT_YEN
    payout = 0
    hit = 0
    hit_label = ""
    for b in rc.bets:
        if b["ticket"] == rc.actual_ticket:
            payout = int(rc.actual_payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
            hit = 1
            hit_label = str(b.get("label", ""))
            break
    return {
        "strategy": rc.strategy,
        "race_id": rc.race_id,
        "race_date": rc.race_date,
        "month": rc.race_date[:7],
        "venue_id": rc.venue_id,
        "race_no": rc.race_no,
        "racegrp": _race_group(rc.race_no),
        "race_name": rc.race_name,
        "title_stage": rc.title_stage,
        "event_day_no": rc.event_day_no,
        "event_day_group": rc.event_day_group,
        "event_day_broad": rc.event_day_broad,
        "stage_combo": rc.stage_combo,
        "points": points,
        "stake_yen": stake,
        "payout_yen": payout,
        "profit_yen": payout - stake,
        "hit": hit,
        "hit_label": hit_label,
        "actual_ticket": rc.actual_ticket,
        "actual_payout_yen": rc.actual_payout_yen,
        "bet_tickets": "|".join(str(b.get("ticket", "")) for b in rc.bets),
        "bet_labels": "|".join(str(b.get("label", "")) for b in rc.bets),
        "bet_odds": "|".join(str(round(_safe_float(b.get("odds"), 0.0), 1)) for b in rc.bets),
        "bet_prob_rank": "|".join(str(_safe_int(b.get("prob_rank"), 0)) for b in rc.bets),
        "bet_market_rank": "|".join(str(_safe_int(b.get("market_rank"), 0)) for b in rc.bets),
    }


def _summarize_records(records: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    races = len(records)
    points = sum(_safe_int(r.get("points"), 0) for r in records)
    stake = sum(_safe_int(r.get("stake_yen"), 0) for r in records)
    payout = sum(_safe_int(r.get("payout_yen"), 0) for r in records)
    profit = payout - stake
    hits = sum(1 for r in records if r.get("hit") == 1)
    max_losing = 0
    cur = 0
    for r in sorted(records, key=lambda x: (x.get("race_date", ""), x.get("venue_id", ""), _safe_int(x.get("race_no"), 0))):
        if r.get("hit") == 1:
            cur = 0
        else:
            cur += 1
            max_losing = max(max_losing, cur)
    return {
        "label": label,
        "races": races,
        "points": points,
        "stake": stake,
        "payout": payout,
        "profit": profit,
        "roi": payout / stake * 100.0 if stake else 0.0,
        "hits": hits,
        "hit_rate": hits / races * 100.0 if races else 0.0,
        "max_losing": max_losing,
    }


def _exclude_top_hits(records: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    hits = [r for r in records if r.get("hit") == 1]
    hits.sort(key=lambda x: _safe_int(x.get("payout_yen"), 0), reverse=True)
    remove_ids = set()
    for r in hits[:k]:
        remove_ids.add((r.get("race_id"), r.get("strategy")))
    return [r for r in records if (r.get("race_id"), r.get("strategy")) not in remove_ids]


def _print_total_row(row: Dict[str, Any]) -> None:
    print(
        f"{row['strategy'][:42]:42s} "
        f"採用{row['adopted_races']:5d}R/{row['total_points']:5d}点 "
        f"的中{row['hit_races']:4d}R({row['hit_rate']:5.1f}%) "
        f"投資{row['total_stake_yen']:>9,}円 回収{row['total_payout_yen']:>9,}円 "
        f"損益{row['profit_yen']:>+9,}円 ROI{row['roi']:6.1f}% "
        f"最大連敗{row['max_losing_streak']:4d} 予算前eligible{row['eligible_before_budget']:5d}",
        flush=True,
    )


def _print_focus(strategy: str, records: List[Dict[str, Any]]) -> None:
    all_row = _summarize_records(records, "all")
    ex25 = _summarize_records([r for r in records if r.get("month") != "2025-05"], "ex25")
    ex26 = _summarize_records([r for r in records if r.get("month") != "2026-05"], "ex26")
    both = _summarize_records([r for r in records if r.get("month") not in ("2025-05", "2026-05")], "both")
    top1 = _summarize_records(_exclude_top_hits(records, 1), "top1")
    top3 = _summarize_records(_exclude_top_hits(records, 3), "top3")

    print(
        f"FOCUS {strategy[:42]:42s} "
        f"allROI={all_row['roi']:6.1f}% profit={all_row['profit']:>+9,} "
        f"ex25={ex25['roi']:6.1f}% ex26={ex26['roi']:6.1f}% "
        f"both={both['roi']:6.1f}% top1={top1['roi']:6.1f}% top3={top3['roi']:6.1f}% "
        f"maxLose={all_row['max_losing']:4d}",
        flush=True,
    )


def _group_summaries(records: List[Dict[str, Any]], field: str, min_n: int = 5) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        key = str(r.get(field, ""))
        groups.setdefault(key, []).append(r)
    out = []
    for key, recs in groups.items():
        s = _summarize_records(recs, key)
        if s["races"] >= min_n:
            out.append(s)
    out.sort(key=lambda x: (x["roi"], x["profit"]), reverse=True)
    return out


def _print_group_table(title: str, records: List[Dict[str, Any]], field: str, min_n: int = 5, limit: int = 30) -> None:
    print(f"\n--- {title} / field={field} / n>={min_n} ---", flush=True)
    rows = _group_summaries(records, field, min_n=min_n)
    if not rows:
        print("該当なし", flush=True)
        return
    for s in rows[:limit]:
        print(
            f"{str(s['label'])[:32]:32s} "
            f"n={s['races']:5d} hit={s['hits']:4d}({s['hit_rate']:5.1f}%) "
            f"ROI={s['roi']:6.1f}% profit={s['profit']:>+8,} "
            f"maxL={s['max_losing']:4d}",
            flush=True,
        )


def _print_stage_diagnostics(strategy: str, records: List[Dict[str, Any]]) -> None:
    print("\n" + "-" * 92, flush=True)
    print(f"STAGE DIAG: {strategy}", flush=True)
    _print_focus(strategy, records)
    _print_group_table("レース名ステージ別", records, "title_stage", min_n=5)
    _print_group_table("開催日数 broad 別", records, "event_day_broad", min_n=5)
    _print_group_table("開催日数 day別", records, "event_day_group", min_n=5)
    _print_group_table("stage_combo別", records, "stage_combo", min_n=5)
    _print_group_table("レース番号帯別", records, "racegrp", min_n=5)


def main() -> None:
    _require_settings()
    print("✅ backtest_multi_patterns_v14_low_timing_refine.py VERSION 2026-06-23 low-timing-racegrp-refine", flush=True)
    print("=== v14 低オッズ日程・レース帯チューニング開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"daily_budget={DAILY_BUDGET_YEN}円 unit={UNIT_YEN}円 max_points={DAILY_MAX_POINTS}", flush=True)
    print("対象: 低オッズ通常モードの開催日数・レース帯を追加チューニング。曜日・月内日付は不使用。", flush=True)
    print("目標: low_exR10_12_baseを超える、最大連敗短縮・ROI105%以上・採用数確保。", flush=True)
    print("分類: 現DBにrace_name列が無いため、venue連続開催日 + レース番号で初日/終盤R/最終日Rを推定。", flush=True)

    stats: Dict[str, StrategyStats] = {s.name: StrategyStats(s.name, s.description) for s in V14_STRATEGIES}
    records_by_strategy: Dict[str, List[Dict[str, Any]]] = {s.name: [] for s in V14_STRATEGIES}
    monthly: Dict[str, Dict[str, int]] = {}

    total_races = 0
    ready_races = 0
    seed_ready = 0

    # venueごとの連続開催日を推定する。日付順に処理している前提。
    venue_prev_date: Dict[str, str] = {}
    venue_event_day: Dict[str, int] = {}

    dates = list(_daterange(START_DATE, END_DATE))
    for idx, race_date in enumerate(dates, start=1):
        t0 = time.time()
        races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)

        active_venues = sorted({str(r.get("venue_id", "")).zfill(2) for r in races})
        day_no_by_venue: Dict[str, int] = {}
        yesterday = _shift_day(race_date, -1)
        for v in active_venues:
            if venue_prev_date.get(v) == yesterday:
                venue_event_day[v] = venue_event_day.get(v, 0) + 1
            else:
                venue_event_day[v] = 1
            venue_prev_date[v] = race_date
            day_no_by_venue[v] = venue_event_day[v]

        day_candidates: Dict[str, List[RaceCandidate]] = {s.name: [] for s in V14_STRATEGIES}
        day_ready = 0
        day_seed = 0

        for race in races:
            total_races += 1
            rid = race.get("race_id")
            venue_id = str(race.get("venue_id", "")).zfill(2)
            race_no = _safe_int(race.get("race_no"), 0)
            race_name = _normalize_jp_text(race.get("race_name", ""))
            title_stage = _race_title_stage(race_name)
            event_day_no = day_no_by_venue.get(venue_id, 0)
            event_day_group = _event_day_group(event_day_no)
            event_day_broad = _event_day_broad(event_day_no)
            combo_stage = _stage_combo(title_stage, event_day_no, race_no)

            result = results.get(rid)
            entries = entries_by_race.get(rid, [])
            odds = odds_by_race.get(rid, {})

            if not _is_backtest_ready(result, entries, odds):
                continue

            actual = _get_actual_ticket(result)
            payout_yen = _safe_int(result.get("trifecta_payout_yen"), 0)
            is_seed = _is_seed_race(entries, STRICT_SEED)

            ready_races += 1
            day_ready += 1
            if is_seed:
                seed_ready += 1
                day_seed += 1

            ranked_rows = _rank_candidates(entries, venue_id, odds)

            for st in V14_STRATEGIES:
                bets = _select_bets(ranked_rows, st, venue_id, race_no, event_day_no, combo_stage)
                if not bets:
                    continue
                stats[st.name].add_eligible_before_budget()
                priority = max(_safe_float(b.get("select_priority"), 0.0) for b in bets)
                rc = RaceCandidate(
                    race_id=str(rid),
                    race_date=str(race_date),
                    venue_id=venue_id,
                    race_no=race_no,
                    race_name=race_name,
                    title_stage=title_stage,
                    event_day_no=event_day_no,
                    event_day_group=event_day_group,
                    event_day_broad=event_day_broad,
                    stage_combo=combo_stage,
                    strategy=st.name,
                    bets=bets,
                    actual_ticket=actual,
                    actual_payout_yen=payout_yen,
                    is_seed=is_seed,
                    priority=priority,
                )
                day_candidates[st.name].append(rc)

        for st in V14_STRATEGIES:
            selected = _apply_daily_budget(day_candidates[st.name])
            for rc in selected:
                stats[st.name].adopt(rc)
                records_by_strategy[st.name].append(_record_from_rc(rc))

        mm = race_date[:7]
        m = monthly.setdefault(mm, {"races": 0, "ready": 0, "seed": 0})
        m["races"] += len(races)
        m["ready"] += day_ready
        m["seed"] += day_seed

        if idx == 1 or idx % LOG_EVERY_DAYS == 0 or idx == len(dates):
            adopted = sum(len(day_candidates[s.name]) for s in V14_STRATEGIES)
            print(
                f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={day_ready} seed={day_seed} "
                f"eligible_candidates={adopted} elapsed={time.time()-t0:.1f}s",
                flush=True,
            )
        if DAY_SLEEP > 0:
            time.sleep(DAY_SLEEP)

    print("\n" + "=" * 92, flush=True)
    print("v14 低オッズ日程・レース帯チューニング 最終結果", flush=True)
    print("=" * 92, flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"読み込みレース数: {total_races}", flush=True)
    print(f"backtest_ready: {ready_races}", flush=True)
    print(f"seed_ready: {seed_ready}", flush=True)
    print(f"日次上限: {DAILY_BUDGET_YEN}円", flush=True)

    print("--- 月別 ready / seed ---", flush=True)
    for mm in sorted(monthly):
        m = monthly[mm]
        print(f"{mm} races={m['races']:5d} ready={m['ready']:5d} seed={m['seed']:4d}", flush=True)

    print("--- v14低オッズチューニング戦略サマリー ROI順 ---", flush=True)
    rows = [stats[s.name].row() for s in V14_STRATEGIES]
    rows.sort(key=lambda r: r["roi"], reverse=True)
    for r in rows:
        _print_total_row(r)

    print("\n--- v14 条件別確認 ---", flush=True)
    for r in rows:
        _print_stage_diagnostics(r["strategy"], records_by_strategy.get(r["strategy"], []))

    print("\n=== v14 低オッズ日程・レース帯チューニング終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise