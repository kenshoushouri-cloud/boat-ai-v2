# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v12_stage_diagnostics.py

競艇AI v2用・当日買い目出力。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python v24_pre_candidate_notifier_fix2.py

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    SELECTOR_MODE=balanced|wide|strict|all

必要Variables:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY もしくは SUPABASE_KEY
    RAILPACK_PYTHON_VERSION=3.11 推奨
"""

from __future__ import annotations

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
    "http_timeout": 75,
    "retry_max": 3,
    "retry_sleep": 5.0,
    "day_sleep": 0.03,
    "log_every_days": 60,
    "summary_top_n": 15,
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

TARGET_DATE = os.getenv("TARGET_DATE") or (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "balanced").strip().lower()
PRE_SESSION = os.getenv("PRE_SESSION", "day").strip().lower()  # day/night/all
DRY_RUN = os.getenv("DRY_RUN", "0").strip() in ("1", "true", "True", "yes", "YES")
TEST_MODE = os.getenv("TEST_MODE", "1").strip() not in ("0", "false", "False", "no", "NO")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (os.getenv("LINE_TO") or os.getenv("LINE_USER_ID") or os.getenv("LINE_GROUP_ID") or "").strip()
BATCH_NOTIFY = True
MAX_ITEMS_PER_MESSAGE = int(os.getenv("MAX_ITEMS_PER_MESSAGE", "6"))
MIN_ODDS_ROWS = int(os.getenv("MIN_ODDS_ROWS", "100"))
DAILY_LINE_LIMIT = int(os.getenv("DAILY_LINE_LIMIT", "3"))
MONTHLY_LINE_LIMIT = int(os.getenv("MONTHLY_LINE_LIMIT", "180"))
# balanced: 本命候補だけ / wide: unionも含める / strict: 超厳選だけ / all: 全候補表示
INCLUDE_CLOSED = os.getenv("INCLUDE_CLOSED", "1").strip() not in ("0", "false", "False", "no", "NO")
EVENT_DAY_LOOKBACK = int(os.getenv("EVENT_DAY_LOOKBACK", "10"))


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
                # Railwayログ制限対策: retryごとの詳細ログは出さない。
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

    # v15ではグレード/女子/一般などの列が存在するか確認するため select=*。
    # v2_racesにイベント名やグレード列が無い場合は unknown として集計される。
    races = _rest_get(
        "v2_races",
        {
            "select": "*",
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

def _fetch_live_day_rows(date_str: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, float]]]:
    """当日買い目出力用。結果は不要なので races/entries/odds だけ取る。"""
    day_prefix = _rid_prefix(date_str)
    next_prefix = _rid_prefix(_next_day(date_str))

    races = _rest_get(
        "v2_races",
        {
            "select": "*",
            "race_date": f"eq.{date_str}",
            "order": "venue_id.asc,race_no.asc",
        },
    )
    races = [r for r in races if str(r.get("venue_id", "")).zfill(2) in TARGET_VENUES]

    entries_rows = _rest_get_range(
        "v2_race_entries",
        select="race_id,lane,racer_number,racer_class,racer_name,national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,motor_no,boat_no,avg_st",
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

    return races, entries_by_race, odds_by_race


def _fetch_race_rows_for_event_day(target_date: str, lookback_days: int = 10) -> List[Dict[str, Any]]:
    start = _shift_day(target_date, -lookback_days)
    rows = _rest_get(
        "v2_races",
        {
            "select": "race_id,race_date,venue_id,race_no,race_title,session_type",
            "race_date": f"gte.{start}",
            "order": "race_date.asc,venue_id.asc,race_no.asc",
        },
    )
    return [r for r in rows if start <= str(r.get("race_date", "")) <= target_date]


def _compute_event_day_by_venue(target_date: str) -> Dict[str, int]:
    rows = _fetch_race_rows_for_event_day(target_date, EVENT_DAY_LOOKBACK)
    dates_by_venue: Dict[str, List[str]] = {}
    for r in rows:
        v = str(r.get("venue_id", "")).zfill(2)
        d = str(r.get("race_date", ""))
        if not v or not d:
            continue
        dates_by_venue.setdefault(v, [])
        if d not in dates_by_venue[v]:
            dates_by_venue[v].append(d)

    out: Dict[str, int] = {}
    for v, ds in dates_by_venue.items():
        ds = sorted(ds)
        cur = 0
        prev = ""
        for d in ds:
            if prev and d == _shift_day(prev, 1):
                cur += 1
            else:
                cur = 1
            prev = d
            if d == target_date:
                out[v] = cur
    return out


def _is_live_ready(entries: List[Dict[str, Any]], odds: Dict[str, float]) -> bool:
    by_lane = _entry_by_lane(entries)
    if len(by_lane) != 6:
        return False
    for lane in range(1, 7):
        e = by_lane.get(lane, {})
        if e.get("racer_number") is None or e.get("racer_class") is None:
            return False
    return len(odds) >= MIN_ODDS_ROWS


def _format_entries(entries: List[Dict[str, Any]]) -> str:
    by = _entry_by_lane(entries)
    parts = []
    for lane in range(1, 7):
        e = by.get(lane, {})
        name = _normalize_jp_text(e.get("racer_name")) or str(e.get("racer_number", "?"))
        cls = _safe_int(e.get("racer_class"), 0)
        cls_s = {4: "A1", 3: "A2", 2: "B1", 1: "B2"}.get(cls, str(cls))
        parts.append(f"{lane}:{name}({cls_s})")
    return " / ".join(parts)


def _selector_strategy_names(mode: str) -> List[str]:
    if mode == "strict":
        return [
            "mode_intersection_day_and_venue",
            "mode_general_cup_bad5_r04_09",
            "mode_strict_bad5_r04_09",
        ]
    if mode == "wide":
        return [
            "mode_balanced_venue_best",
            "mode_union_day_or_venue",
            "mode_wide_not_standard",
            "mode_intersection_day_and_venue",
            "mode_general_cup_bad5_r04_09",
            "mode_strict_bad5_r04_09",
        ]
    if mode == "all":
        return [s.name for s in V17_STRATEGIES if s.include_low]
    # default balanced
    return [
        "mode_balanced_venue_best",
        "mode_intersection_day_and_venue",
        "mode_general_cup_bad5_r04_09",
        "mode_strict_bad5_r04_09",
    ]


def _mode_rank(mode_names: List[str]) -> int:
    s = set(mode_names)
    if "mode_intersection_day_and_venue" in s or "mode_general_cup_bad5_r04_09" in s or "mode_strict_bad5_r04_09" in s:
        return 4
    if "mode_balanced_venue_best" in s:
        return 3
    if "mode_union_day_or_venue" in s or "mode_wide_not_standard" in s:
        return 2
    return 1


def _mode_label(mode_names: List[str]) -> str:
    rank = _mode_rank(mode_names)
    if rank >= 4:
        return "強化/厳選"
    if rank == 3:
        return "通常本命"
    if rank == 2:
        return "広め候補"
    return "参考"





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
    return len(odds) >= MIN_ODDS_ROWS


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



META_TEXT_KEYS = (
    "race_title", "race_name", "title", "event_title", "event_name",
    "series_title", "series_name", "tournament_title", "tournament_name",
    "meeting_title", "meet_title", "grade", "grade_type", "category",
    "race_category", "race_type", "program_name", "subtitle", "session_type",
)

# 会場タイプは仮説分類。最終判断は診断結果優先。
# 01桐生, 04平和島, 05多摩川, 06浜名湖, 23唐津 は低オッズbad5で強かったグループ。
BAD5_VENUES = {"01", "04", "05", "06", "23"}

# イン強イメージの強い場。通常モード/低オッズ向きかを確認する。
IN_STRONG_VENUES = {"12", "15", "18", "21", "24"}  # 住之江, 丸亀, 下関, 芦屋, 大村

# 荒れやすい/中穴向き仮説の場。
ROUGH_VENUES = {"02", "03", "04", "05", "06"}  # 戸田, 江戸川, 平和島, 多摩川, 浜名湖


def _metadata_text(row: Dict[str, Any]) -> str:
    vals: List[str] = []
    for k in META_TEXT_KEYS:
        v = row.get(k)
        if v is None:
            continue
        s = _normalize_jp_text(v)
        if s:
            vals.append(f"{k}={s}")
    return " / ".join(vals)


def _best_race_name(row: Dict[str, Any]) -> str:
    for k in ("race_name", "race_title", "title", "program_name"):
        s = _normalize_jp_text(row.get(k))
        if s:
            return s
    return ""


def _infer_grade(meta_text: str) -> str:
    t = _normalize_jp_text(meta_text).upper()
    if not t:
        return "grade_unknown"

    if (
        "SG" in t
        or "グランプリ" in t
        or "ボートレースクラシック" in t
        or "ボートレースオールスター" in t
        or "グランドチャンピオン" in t
        or "オーシャンカップ" in t
        or "メモリアル" in t
        or "ダービー" in t
        or "チャレンジカップ" in t
    ):
        return "SG_like"

    if (
        "G1" in t or "GⅠ" in t or "GI" in t
        or "周年" in t
        or ("開設" in t and "周年" in t)
        or "地区選" in t
        or "ダイヤモンドカップ" in t
        or "高松宮記念" in t
        or "モーターボート大賞" in t
        or "BBCトーナメント" in t
        or "クイーンズクライマックス" in t
        or "レディースチャンピオン" in t
        or "ヤングダービー" in t
        or "マスターズチャンピオン" in t
    ):
        return "G1_like"

    if "G2" in t or "GⅡ" in t or "GII" in t:
        return "G2_like"
    if "G3" in t or "GⅢ" in t or "GIII" in t or "オールレディース" in t or "企業杯" in t:
        return "G3_like"
    if "一般" in t:
        return "GENERAL"
    return "grade_other"


def _infer_gender_category(meta_text: str) -> str:
    t = _normalize_jp_text(meta_text)
    if not t:
        return "gender_unknown"
    if "オールレディース" in t:
        return "all_ladies"
    if "ヴィーナス" in t or "ビーナス" in t:
        return "venus"
    if "レディース" in t or "女子" in t or "女流" in t:
        return "ladies_other"
    return "mixed_or_unknown"


def _infer_event_category(meta_text: str) -> str:
    t = _normalize_jp_text(meta_text)
    tu = t.upper()
    if not t:
        return "category_unknown"

    if "オールレディース" in t:
        return "all_ladies"
    if "ヴィーナス" in t or "ビーナス" in t:
        return "venus"
    if "レディース" in t or "女子" in t or "女流" in t:
        return "ladies_other"

    if "ルーキー" in t:
        return "rookie"
    if "新人" in t or "若獅子" in t:
        return "newcomer"
    if "ヤング" in t or "新鋭" in t:
        return "young"
    if "マスターズ" in t or "名人" in t or "匠" in t:
        return "masters"

    if "SG" in tu or "グランプリ" in t or "クラシック" in t or "オールスター" in t or "ダービー" in t:
        return "SG_like"
    if "周年" in t or "開設" in t or "地区選" in t or "モーターボート大賞" in t or "ダイヤモンドカップ" in t:
        return "G1_like"
    if "G2" in tu or "GⅡ" in t:
        return "G2_like"
    if "G3" in tu or "GⅢ" in t or "企業杯" in t:
        return "G3_like"

    if "モーニング" in t:
        return "morning_named"
    if "ミッドナイト" in t:
        return "midnight_named"
    if "ナイター" in t:
        return "night_named"
    if "サマータイム" in t:
        return "summertime_named"

    if "一般" in t:
        return "general_named"
    if "杯" in t or "カップ" in t or "CUP" in tu or "賞" in t or "記念" in t:
        return "general_cup_award"

    return "category_other"


def _infer_session_type(row: Dict[str, Any]) -> str:
    s = _normalize_jp_text(row.get("session_type")).lower()
    if s in ("day", "night", "morning", "midnight", "summer", "summertime"):
        return s
    if not s:
        return "session_unknown"
    return s


def _infer_venue_style(venue_id: str) -> str:
    v = str(venue_id).zfill(2)
    if v in BAD5_VENUES:
        return "bad5"
    if v in ROUGH_VENUES:
        return "rough"
    if v in IN_STRONG_VENUES:
        return "in_strong"
    return "standard"


def _meta_info_status(meta_text: str) -> str:
    return "meta_known" if "race_title=" in _normalize_jp_text(meta_text) else "meta_unknown"


def _collect_meta_samples(row: Dict[str, Any], samples: Dict[str, List[str]], limit: int = 6) -> None:
    for k in META_TEXT_KEYS:
        s = _normalize_jp_text(row.get(k))
        if not s:
            continue
        arr = samples.setdefault(k, [])
        if s not in arr and len(arr) < limit:
            arr.append(s)




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
class V17Strategy:
    name: str
    description: str
    include_mid: bool = False
    include_low: bool = False

    low_filter: str = "all"
    low_stage_filter: str = "all"

    # v17: race_title/session/venue/event_day/racegrpを使った実運用フィルター
    extra_filter: str = "all"

    mid_max_points: int = 1
    low_max_points: int = 1
    mid_non_head1: bool = True
    mid_race_filter: str = "all"
    mid_stage_filter: str = "all"

    mid_priority: str = "prob"
    low_priority: str = "prob"
    prefer_mid: bool = True


# v18は通常モードの最終候補を比較する。
# v17結果から有望だった:
# - 開催日×レース帯
# - 会場タイプ×レース帯
# - standard除外
# - 一般カップ×bad5
# を実運用候補として並べる。
V17_STRATEGIES: List[V17Strategy] = [
    V17Strategy(
        "low_exR10_12_base",
        "基準: 低オッズ 10〜12R除外",
        include_low=True,
        low_filter="exclude_r10_12",
    ),
    V17Strategy(
        "low_exR10_12_day2_3_or_day6plus",
        "基準厳選: 低オッズ 10〜12R除外 + 2〜3日目 or 終盤日",
        include_low=True,
        low_filter="exclude_r10_12",
        low_stage_filter="day2_3_or_day6plus",
    ),
    V17Strategy(
        "mode_balanced_venue_best",
        "本命候補: bad5×R04〜09 + イン強×R01〜03/R07〜09",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="venue_best_combo",
    ),
    V17Strategy(
        "mode_wide_not_standard",
        "広め候補: standard会場を除外",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="not_standard",
    ),
    V17Strategy(
        "mode_strict_bad5_r04_09",
        "厳選候補: bad5会場 × R04〜09",
        include_low=True,
        low_filter="r04_09",
        extra_filter="venue_bad5",
    ),
    V17Strategy(
        "mode_day_race_best",
        "日程候補: day2_3×R04〜09 + day6plus×R01〜03/R07〜09",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="day_race_best",
    ),
    V17Strategy(
        "mode_day_race_no_standard",
        "日程候補からstandard除外",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="day_race_no_standard",
    ),
    V17Strategy(
        "mode_union_day_or_venue",
        "広め複合: 日程ベスト OR 会場ベスト",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="day_or_venue_best",
    ),
    V17Strategy(
        "mode_intersection_day_and_venue",
        "超厳選: 日程ベスト AND 会場ベスト",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="day_and_venue_best",
    ),
    V17Strategy(
        "mode_venue_best_day2_3_or_6plus",
        "会場ベスト + 2〜3日目/終盤日",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="venue_best_day2_3_or_day6plus",
    ),
    V17Strategy(
        "mode_general_cup_bad5_r04_09",
        "カテゴリ厳選: 一般カップ系 × bad5 × R04〜09",
        include_low=True,
        low_filter="r04_09",
        extra_filter="general_cup_bad5",
    ),
    V17Strategy(
        "mode_ladies_rookie",
        "カテゴリ比較: ヴィーナス/女子/ルーキー系",
        include_low=True,
        low_filter="exclude_r10_12",
        extra_filter="ladies_rookie",
    ),
    V17Strategy(
        "bao_mid_finalday_nonhead_no_r04_06",
        "馬王比較: 中穴 終盤日 + 1頭除外 + R04〜06除外",
        include_mid=True,
        mid_stage_filter="day6plus",
        mid_race_filter="not_r04_06",
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
    meta_text: str
    meta_info: str
    meta_grade: str
    meta_gender: str
    meta_event_category: str
    meta_session: str
    meta_venue_style: str
    meta_grade_event: str
    meta_gender_event: str
    meta_event_venue: str
    meta_grade_venue: str
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



def _match_extra_filter(
    filter_name: str,
    meta_venue_style: str,
    meta_event_category: str,
    meta_gender: str,
    meta_grade: str,
    meta_session: str,
    event_day_no: int,
    race_no: int,
) -> bool:
    if filter_name == "all":
        return True

    # day2_3 × R04_06/R07_09 と day6plus × R01_03/R07_09
    if filter_name == "day_race_best":
        return (
            (event_day_no in (2, 3) and 4 <= race_no <= 9)
            or (event_day_no >= 6 and (1 <= race_no <= 3 or 7 <= race_no <= 9))
        )

    day_race_best = (
        (event_day_no in (2, 3) and 4 <= race_no <= 9)
        or (event_day_no >= 6 and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )
    venue_best = (
        (meta_venue_style == "bad5" and 4 <= race_no <= 9)
        or (meta_venue_style == "in_strong" and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )

    if filter_name == "day_race_no_standard":
        return day_race_best and meta_venue_style != "standard"
    if filter_name == "day_or_venue_best":
        return day_race_best or venue_best
    if filter_name == "day_and_venue_best":
        return day_race_best and venue_best
    if filter_name == "venue_best_day2_3_or_day6plus":
        return venue_best and (event_day_no in (2, 3) or event_day_no >= 6)

    if filter_name == "venue_bad5":
        return meta_venue_style == "bad5"
    if filter_name == "venue_instrong":
        return meta_venue_style == "in_strong"
    if filter_name == "not_standard":
        return meta_venue_style != "standard"

    # bad5×R04〜09 + イン強×R01〜03/R07〜09
    if filter_name == "venue_best_combo":
        return (
            (meta_venue_style == "bad5" and 4 <= race_no <= 9)
            or (meta_venue_style == "in_strong" and (1 <= race_no <= 3 or 7 <= race_no <= 9))
        )

    if filter_name == "general_cup_bad5":
        return meta_event_category == "general_cup_award" and meta_venue_style == "bad5"

    if filter_name == "ladies_rookie":
        return (
            meta_event_category in {"venus", "all_ladies", "ladies_other", "rookie", "newcomer", "young"}
            or meta_gender in {"venus", "all_ladies", "ladies_other"}
        )

    if filter_name == "g1_instrong":
        return meta_grade == "G1_like" and meta_venue_style == "in_strong"

    raise ValueError(f"unknown extra_filter: {filter_name}")


def _is_mid_candidate(
    row: Dict[str, Any],
    st: V17Strategy,
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
    st: V17Strategy,
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
        "meta_text": rc.meta_text,
        "meta_info": rc.meta_info,
        "meta_grade": rc.meta_grade,
        "meta_gender": rc.meta_gender,
        "meta_event_category": rc.meta_event_category,
        "meta_session": rc.meta_session,
        "meta_venue_style": rc.meta_venue_style,
        "meta_grade_event": rc.meta_grade_event,
        "meta_gender_event": rc.meta_gender_event,
        "meta_event_venue": rc.meta_event_venue,
        "meta_grade_venue": rc.meta_grade_venue,
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


def _print_group_table(title: str, records: List[Dict[str, Any]], field: str, min_n: int = 5, limit: int = 6) -> None:
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



def _group_cross_summaries(records: List[Dict[str, Any]], fields: List[str], min_n: int = 5) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        vals = [str(r.get(f, "")) for f in fields]
        key = " × ".join(vals)
        groups.setdefault(key, []).append(r)
    out = []
    for key, recs in groups.items():
        s = _summarize_records(recs, key)
        if s["races"] >= min_n:
            out.append(s)
    out.sort(key=lambda x: (x["roi"], x["profit"]), reverse=True)
    return out


def _print_cross_table(title: str, records: List[Dict[str, Any]], fields: List[str], min_n: int = 5, limit: int = 6) -> None:
    print(f"\n--- {title} / fields={'+'.join(fields)} / n>={min_n} ---", flush=True)
    rows = _group_cross_summaries(records, fields, min_n=min_n)
    if not rows:
        print("該当なし", flush=True)
        return
    for s in rows[:limit]:
        print(
            f"{str(s['label'])[:58]:58s} "
            f"n={s['races']:5d} hit={s['hits']:4d}({s['hit_rate']:5.1f}%) "
            f"ROI={s['roi']:6.1f}% profit={s['profit']:>+8,} "
            f"maxL={s['max_losing']:4d}",
            flush=True,
        )


FOCUS_DIAG_STRATEGIES = {
    "mode_balanced_venue_best",
    "mode_wide_not_standard",
    "mode_day_race_best",
    "mode_union_day_or_venue",
    "mode_intersection_day_and_venue",
    "low_exR10_12_base",
}


def _print_stage_diagnostics(strategy: str, records: List[Dict[str, Any]]) -> None:
    print("\n" + "-" * 80, flush=True)
    print(f"QUIET DIAG: {strategy}", flush=True)
    _print_focus(strategy, records)

    # 単独条件は必要最低限だけ。
    _print_group_table("イベントカテゴリ別", records, "meta_event_category", min_n=5, limit=6)
    _print_group_table("会場タイプ別", records, "meta_venue_style", min_n=5, limit=6)
    _print_group_table("開催日 broad 別", records, "event_day_broad", min_n=5, limit=6)
    _print_group_table("レース番号帯別", records, "racegrp", min_n=5, limit=6)

    # クロス条件の本命だけ。Railwayログ制限対策として各8行まで。
    _print_cross_table("開催日×レース番号帯", records, ["event_day_broad", "racegrp"], min_n=5, limit=6)
    _print_cross_table("会場タイプ×レース番号帯", records, ["meta_venue_style", "racegrp"], min_n=5, limit=6)
    _print_cross_table("イベントカテゴリ×レース番号帯", records, ["meta_event_category", "racegrp"], min_n=3, limit=6)
    _print_cross_table("イベントカテゴリ×会場タイプ×レース帯", records, ["meta_event_category", "meta_venue_style", "racegrp"], min_n=3, limit=6)



# ============================================================
# v24 LINE helpers
# ============================================================

def _month_start(date_str: str) -> str:
    return date_str[:7] + "-01"


def _rest_post(table: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = dict(HEADERS)
    headers["Prefer"] = "return=representation"
    r = requests.post(
        url,
        headers=headers,
        data=json.dumps(row, ensure_ascii=False),
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"INSERT {table} failed {r.status_code}: {r.text[:800]}")
    try:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        pass
    return None


def _count_sent_notifications() -> Dict[str, int]:
    day_rows = _rest_get("v2_line_notifications", {
        "select": "id",
        "race_date": f"eq.{TARGET_DATE}",
        "status": "eq.sent",
        "limit": "10000",
    })
    month_rows = _rest_get("v2_line_notifications", {
        "select": "id,race_date",
        "race_date": f"gte.{_month_start(TARGET_DATE)}",
        "status": "eq.sent",
        "limit": "10000",
    })
    month_rows = [r for r in month_rows if str(r.get("race_date", ""))[:7] == TARGET_DATE[:7]]
    return {"day": len(day_rows), "month": len(month_rows)}


def _usage_guard() -> Optional[str]:
    counts = _count_sent_notifications()
    if counts["day"] >= DAILY_LINE_LIMIT:
        return f"daily_limit_reached {counts['day']}/{DAILY_LINE_LIMIT}"
    if counts["month"] >= MONTHLY_LINE_LIMIT:
        return f"monthly_limit_reached {counts['month']}/{MONTHLY_LINE_LIMIT}"
    return None


NIGHT_VENUE_IDS = {"01", "07", "12", "15", "18", "20", "24"}  # 桐生,蒲郡,住之江,丸亀,下関,若松,大村
MIDNIGHT_KEYWORDS = ("ミッドナイト", "MIDNIGHT")
NIGHT_KEYWORDS = ("ナイター", "NIGHT", "ブルーナイター", "ムーンライト", "シティーナイター")


def _is_night_like_session(session: str, venue_id: str = "", title: str = "") -> bool:
    s = (session or "").lower()
    if s in ("night", "midnight"):
        return True
    t = title or ""
    if any(k in t for k in MIDNIGHT_KEYWORDS + NIGHT_KEYWORDS):
        return True
    # v2_races.session_type が day 固定で入っている日があるため、ナイター開催場は夜側にも拾う。
    # 厳密な締切時刻分割は後で start_time 取得を追加して対応。
    return str(venue_id).zfill(2) in NIGHT_VENUE_IDS


def _session_match(session: str, venue_id: str = "", title: str = "") -> bool:
    if PRE_SESSION == "all":
        return True
    is_night = _is_night_like_session(session, venue_id, title)
    if PRE_SESSION == "night":
        return is_night
    # day: ナイター開催場は昼側から除外し、朝/昼配信の重複を避ける
    return not is_night


def _send_line_message(text: str) -> Dict[str, Any]:
    if DRY_RUN:
        return {"dry_run": True, "status_code": 200, "body": "DRY_RUN"}
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_TO:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_TO/LINE_USER_ID が必要です。")
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": LINE_TO, "messages": [{"type": "text", "text": text[:4900]}]}
    r = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=HTTP_TIMEOUT)
    return {"dry_run": False, "status_code": r.status_code, "body": r.text[:1000]}


def _build_pre_message(selected: List[Dict[str, Any]]) -> str:
    title = "【競艇AI テスト仮候補・購入しない】" if TEST_MODE else "【競艇AI 仮候補】"
    if PRE_SESSION == "night":
        title += " ナイター"
    elif PRE_SESSION == "day":
        title += " 昼間"
    else:
        title += " 全体"

    lines = [
        title,
        f"{TARGET_DATE} / {SELECTOR_MODE}",
        f"候補: {len(selected)}件",
        "※直前情報確認後に最終BUY/見送りを再通知",
        "",
    ]
    for i, r in enumerate(selected[:MAX_ITEMS_PER_MESSAGE], start=1):
        lines.append(
            f"{i}. {r['venue_id']}場{r['race_no']}R {r['ticket']} / {r['odds']:.1f}倍"
        )
        lines.append(
            f"   {r['mode_label']} / prob_rank={r['prob_rank']} market_rank={r['market_rank']}"
        )
        lines.append(
            f"   {r['racegrp']} / venue={r['venue_style']} / cat={r['event_category']}"
        )
        if r.get("race_title"):
            lines.append(f"   {str(r['race_title'])[:42]}")
        lines.append("")
    if len(selected) > MAX_ITEMS_PER_MESSAGE:
        lines.append(f"他 {len(selected)-MAX_ITEMS_PER_MESSAGE}件あり")
    if TEST_MODE:
        lines.append("※テスト期間中：購入しない")
    return "\n".join(lines)[:4900]


def _save_pre_notification(message: str, status: str, resp: Dict[str, Any], selected: List[Dict[str, Any]]) -> None:
    first = selected[0] if selected else {}
    row = {
        "race_id": first.get("race_id"),
        "race_date": TARGET_DATE,
        "venue_id": first.get("venue_id"),
        "race_no": first.get("race_no"),
        "decision_id": None,
        "sent_at": datetime.now().isoformat() if status == "sent" else None,
        "status": status,
        "line_to": LINE_TO if not DRY_RUN else "DRY_RUN",
        "message_type": "push_pre_candidate",
        "message_text": message,
        "selector_version": "v24_pre_candidate_notifier",
        "selector_mode": SELECTOR_MODE,
        "mode_name": f"pre_{PRE_SESSION}",
        "ticket": first.get("ticket"),
        "odds": first.get("odds"),
        "line_response_status": resp.get("status_code"),
        "line_response_body": resp.get("body"),
        "error_message": "",
        "raw": {"selected": selected, "pre_session": PRE_SESSION, "test_mode": TEST_MODE, "dry_run": DRY_RUN},
    }
    _rest_post("v2_line_notifications", row)

def main() -> None:
    _require_settings()
    print("✅ v24_pre_candidate_notifier_fix2.py VERSION 2026-06-25 pre-candidate-notifier-fix2", flush=True)
    print("=== v24 仮買い目LINE通知開始 ===", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} PRE_SESSION={PRE_SESSION} SELECTOR_MODE={SELECTOR_MODE} "
        f"DRY_RUN={DRY_RUN} TEST_MODE={TEST_MODE} MIN_ODDS_ROWS={MIN_ODDS_ROWS}",
        flush=True,
    )

    guard = _usage_guard()
    if guard:
        print(f"LINE送信上限ガード: {guard}", flush=True)
        print("=== v24 仮買い目LINE通知終了 ===", flush=True)
        return

    strategies_by_name = {s.name: s for s in V17_STRATEGIES}
    strategy_names = [n for n in _selector_strategy_names(SELECTOR_MODE) if n in strategies_by_name]
    print("対象モード: " + ", ".join(strategy_names), flush=True)

    event_day_by_venue = _compute_event_day_by_venue(TARGET_DATE)
    races, entries_by_race, odds_by_race = _fetch_live_day_rows(TARGET_DATE)

    if not races:
        print("対象日のv2_racesがありません。先に当日補修を実行してください。", flush=True)
        print("=== v24 仮買い目LINE通知終了 ===", flush=True)
        return

    rows_out: List[Dict[str, Any]] = []
    skipped_not_ready = 0
    skipped_entries = 0
    skipped_odds = 0
    ready_races = 0
    low_core_total = 0
    skipped_session = 0

    for race in races:
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id", "")).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)
        entries = entries_by_race.get(rid, [])
        odds = odds_by_race.get(rid, {})

        by_lane = _entry_by_lane(entries)
        if len(by_lane) != 6:
            skipped_not_ready += 1
            skipped_entries += 1
            continue
        if len(odds) < MIN_ODDS_ROWS:
            skipped_not_ready += 1
            skipped_odds += 1
            continue
        ready_races += 1

        meta_text = _metadata_text(race)
        meta_grade = _infer_grade(meta_text)
        meta_gender = _infer_gender_category(meta_text)
        meta_event_category = _infer_event_category(meta_text)
        meta_session = _infer_session_type(race)
        if not _session_match(meta_session, venue_id, meta_text):
            skipped_session += 1
            continue

        meta_venue_style = _infer_venue_style(venue_id)
        race_name = _best_race_name(race)

        event_day_no = event_day_by_venue.get(venue_id, 1)
        title_stage = _race_title_stage(race_name)
        combo_stage = _stage_combo(title_stage, event_day_no, race_no)
        ranked_rows = _rank_candidates(entries, venue_id, odds)

        # 仮候補ゼロ時の診断: 通常モードの中核条件が存在するか確認
        for rr in ranked_rows:
            pr = _safe_int(rr.get("prob_rank"), 999)
            mr = _safe_int(rr.get("market_rank"), 999)
            od = _safe_float(rr.get("odds"), 0.0)
            if 11 <= pr <= 20 and mr == 1 and 3.0 <= od < 5.0:
                low_core_total += 1

        by_ticket: Dict[str, Dict[str, Any]] = {}
        for st_name in strategy_names:
            st = strategies_by_name[st_name]
            if not _match_extra_filter(
                st.extra_filter, meta_venue_style, meta_event_category, meta_gender,
                meta_grade, meta_session, event_day_no, race_no,
            ):
                continue

            bets = _select_bets(ranked_rows, st, venue_id, race_no, event_day_no, combo_stage)
            for b in bets:
                ticket = str(b.get("ticket", ""))
                if not ticket:
                    continue
                rec = by_ticket.setdefault(ticket, {
                    "race_id": rid,
                    "race_date": TARGET_DATE,
                    "venue_id": venue_id,
                    "race_no": race_no,
                    "race_title": race_name,
                    "session": meta_session,
                    "event_day_no": event_day_no,
                    "racegrp": _race_group(race_no),
                    "venue_style": meta_venue_style,
                    "event_category": meta_event_category,
                    "grade": meta_grade,
                    "gender": meta_gender,
                    "ticket": ticket,
                    "odds": _safe_float(b.get("odds"), 0.0),
                    "prob_rank": _safe_int(b.get("prob_rank"), 999),
                    "market_rank": _safe_int(b.get("market_rank"), 999),
                    "prob": _safe_float(b.get("prob"), 0.0),
                    "raw_ev": _safe_float(b.get("raw_ev"), 0.0),
                    "priority": _safe_float(b.get("select_priority"), 0.0),
                    "modes": [],
                    "entries": _format_entries(entries),
                })
                rec["modes"].append(st_name)
                rec["priority"] = max(rec["priority"], _safe_float(b.get("select_priority"), 0.0))

        for rec in by_ticket.values():
            rec["mode_rank"] = _mode_rank(rec["modes"])
            rec["mode_label"] = _mode_label(rec["modes"])
            rows_out.append(rec)

    rows_out.sort(key=lambda r: (r["mode_rank"], r["priority"], -r["race_no"]), reverse=True)
    selected = rows_out[:DAILY_MAX_POINTS]

    print(f"races={len(races)} ready_races={ready_races} candidates={len(rows_out)} selected={len(selected)} skipped_not_ready={skipped_not_ready} skipped_entries={skipped_entries} skipped_odds={skipped_odds} skipped_session={skipped_session}", flush=True)
    print(f"low_core_total={low_core_total}", flush=True)

    if not selected:
        print("仮候補はありません。通知しません。", flush=True)
        print("=== v24 仮買い目LINE通知終了 ===", flush=True)
        return

    msg = _build_pre_message(selected)
    print("\n--- pre message ---", flush=True)
    print(msg, flush=True)

    resp = _send_line_message(msg)
    ok = 200 <= int(resp.get("status_code", 0)) < 300
    status = "sent" if ok else "failed"
    _save_pre_notification(msg, status, resp, selected)

    print("\n=== v24 仮買い目LINE通知 summary ===", flush=True)
    print(f"status={status} dry_run={DRY_RUN} response_status={resp.get('status_code')}", flush=True)
    print("=== v24 仮買い目LINE通知終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise