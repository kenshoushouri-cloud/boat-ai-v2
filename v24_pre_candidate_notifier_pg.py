# -*- coding: utf-8 -*-
"""
v24_pre_candidate_notifier_pg.py

Railway Postgres版・仮候補LINE通知。
Supabase REST API版 v24_pre_candidate_notifier_ab.py を
DATABASE_URL + PostgreSQL直接接続で動かす移行版です。

Railway Start Command:
    python v24_pre_candidate_notifier_pg.py

必要Variables:
    DATABASE_URL
    LINE_CHANNEL_ACCESS_TOKEN
    LINE_TO

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    PRE_SESSION=day|night|all
    SELECTOR_MODE=ab|balanced|wide|strict|all
    TEST_MODE=1
    DRY_RUN=0
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from psycopg.types.json import Jsonb

from db_pg import execute, fetch_all, fetch_one


# ============================================================
# Settings
# ============================================================

RUN_CONFIG = {
    "venues": [f"{i:02d}" for i in range(1, 25)],
    "unit_yen": 100,
    "daily_budget_yen": 1000,
    "strict_seed": True,
    "prob_temp": 2.20,
    "odds_page_size": 1000,
    "page_size": 1000,
    "http_timeout": 75,
    "bad_venues": ["01", "04", "05", "06", "23"],
}

TARGET_VENUES = [str(v).zfill(2) for v in RUN_CONFIG["venues"]]
UNIT_YEN = int(RUN_CONFIG["unit_yen"])
DAILY_BUDGET_YEN = int(RUN_CONFIG["daily_budget_yen"])
DAILY_MAX_POINTS = DAILY_BUDGET_YEN // UNIT_YEN if DAILY_BUDGET_YEN > 0 else 10**9
STRICT_SEED = bool(RUN_CONFIG["strict_seed"])
PROB_TEMP = float(RUN_CONFIG["prob_temp"])
HTTP_TIMEOUT = int(RUN_CONFIG["http_timeout"])
BAD_VENUES = tuple(str(v).zfill(2) for v in RUN_CONFIG["bad_venues"])

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "balanced").strip().lower()
PRE_SESSION = os.getenv("PRE_SESSION", "day").strip().lower()
DRY_RUN = os.getenv("DRY_RUN", "0").strip() in ("1", "true", "True", "yes", "YES")
TEST_MODE = os.getenv("TEST_MODE", "1").strip() not in ("0", "false", "False", "no", "NO")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (os.getenv("LINE_TO") or os.getenv("LINE_USER_ID") or os.getenv("LINE_GROUP_ID") or "").strip()
MAX_ITEMS_PER_MESSAGE = int(os.getenv("MAX_ITEMS_PER_MESSAGE", "6"))
MIN_ODDS_ROWS = int(os.getenv("MIN_ODDS_ROWS", "100"))
DAILY_LINE_LIMIT = int(os.getenv("DAILY_LINE_LIMIT", "3"))
MONTHLY_LINE_LIMIT = int(os.getenv("MONTHLY_LINE_LIMIT", "100"))
EVENT_DAY_LOOKBACK = int(os.getenv("EVENT_DAY_LOOKBACK", "10"))

CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}

META_TEXT_KEYS = (
    "race_title", "race_name", "title", "event_title", "event_name",
    "series_title", "series_name", "tournament_title", "tournament_name",
    "meeting_title", "meet_title", "grade", "grade_type", "category",
    "race_category", "race_type", "program_name", "subtitle", "session_type",
)

BAD5_VENUES = {"01", "04", "05", "06", "23"}
IN_STRONG_VENUES = {"12", "15", "18", "21", "24"}
ROUGH_VENUES = {"02", "03", "04", "05", "06"}

NIGHT_VENUE_IDS = {"01", "07", "12", "15", "18", "20", "24"}
MIDNIGHT_KEYWORDS = ("ミッドナイト", "MIDNIGHT")
NIGHT_KEYWORDS = ("ナイター", "NIGHT", "ブルーナイター", "ムーンライト", "シティーナイター")


# ============================================================
# Utility
# ============================================================

def _require_settings() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")


def _next_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _shift_day(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def _month_start(date_str: str) -> str:
    return date_str[:7] + "-01"


def _next_month_start(date_str: str) -> str:
    d = datetime.strptime(_month_start(date_str), "%Y-%m-%d")
    if d.month == 12:
        nd = datetime(d.year + 1, 1, 1)
    else:
        nd = datetime(d.year, d.month + 1, 1)
    return nd.strftime("%Y-%m-%d")


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


def _normalize_jp_text(s: Any) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).strip()


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


# ============================================================
# PG schema helper for notifications
# ============================================================

def _ensure_line_notification_columns() -> None:
    ddl_list = [
        "alter table v2_line_notifications add column if not exists race_date date;",
        "alter table v2_line_notifications add column if not exists venue_id text;",
        "alter table v2_line_notifications add column if not exists venue_code text;",
        "alter table v2_line_notifications add column if not exists race_no integer;",
        "alter table v2_line_notifications add column if not exists decision_id bigint;",
        "alter table v2_line_notifications add column if not exists line_to text;",
        "alter table v2_line_notifications add column if not exists message_type text;",
        "alter table v2_line_notifications add column if not exists message_text text;",
        "alter table v2_line_notifications add column if not exists selector_version text;",
        "alter table v2_line_notifications add column if not exists selector_mode text;",
        "alter table v2_line_notifications add column if not exists mode_name text;",
        "alter table v2_line_notifications add column if not exists ticket text;",
        "alter table v2_line_notifications add column if not exists odds numeric;",
        "alter table v2_line_notifications add column if not exists line_response_status integer;",
        "alter table v2_line_notifications add column if not exists line_response_body text;",
        "alter table v2_line_notifications add column if not exists error_message text;",
    ]
    for ddl in ddl_list:
        execute(ddl)


# ============================================================
# PG fetch
# ============================================================

def _fetch_live_day_rows(date_str: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, float]]]:
    day_prefix = _rid_prefix(date_str)
    next_prefix = _rid_prefix(_next_day(date_str))

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date = %s
        order by venue_id asc, race_no asc;
        """,
        (date_str,),
    )
    races = [
        r for r in races
        if str(r.get("venue_id") or r.get("venue_code") or "").zfill(2) in TARGET_VENUES
    ]

    entries_rows = fetch_all(
        """
        select race_id,lane,racer_number,racer_class,racer_name,
               national_win_rate,national_place2_rate,
               local_win_rate,local_place2_rate,
               motor_no,boat_no,avg_st
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id asc, lane asc;
        """,
        (day_prefix, next_prefix),
    )
    entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries_rows:
        entries_by_race.setdefault(e.get("race_id"), []).append(e)

    odds_rows = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id asc, ticket asc;
        """,
        (day_prefix, next_prefix),
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
    rows = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s and race_date <= %s
        order by race_date asc, venue_id asc, race_no asc;
        """,
        (start, target_date),
    )
    return rows


def _compute_event_day_by_venue(target_date: str) -> Dict[str, int]:
    rows = _fetch_race_rows_for_event_day(target_date, EVENT_DAY_LOOKBACK)
    dates_by_venue: Dict[str, List[str]] = {}
    for r in rows:
        v = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
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


# ============================================================
# Race logic
# ============================================================

def _entry_by_lane(entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    by_lane: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        lane = _safe_int(e.get("lane"), 0)
        if 1 <= lane <= 6:
            by_lane[lane] = e
    return by_lane


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


def _selector_strategy_names(mode: str) -> List[str]:
    if mode == "strict":
        return [
            "mode_intersection_day_and_venue",
            "mode_general_cup_bad5_r04_09",
            "mode_strict_bad5_r04_09",
        ]
    if mode in ("ab", "a_b", "rank_ab", "test_ab"):
        return [
            "mode_balanced_venue_best",
            "mode_intersection_day_and_venue",
            "mode_general_cup_bad5_r04_09",
            "mode_strict_bad5_r04_09",
            "low_exR10_12_base",
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
    return [
        "mode_balanced_venue_best",
        "mode_intersection_day_and_venue",
        "mode_general_cup_bad5_r04_09",
        "mode_strict_bad5_r04_09",
    ]


def _mode_rank(mode_names: List[str]) -> int:
    s = set(mode_names)
    if "mode_intersection_day_and_venue" in s or "mode_general_cup_bad5_r04_09" in s or "mode_strict_bad5_r04_09" in s:
        return 40
    if "mode_balanced_venue_best" in s:
        return 30
    if "mode_union_day_or_venue" in s or "mode_wide_not_standard" in s:
        return 20
    if "low_exR10_12_base" in s:
        return 10
    return 1


def _mode_label(mode_names: List[str]) -> str:
    s = set(mode_names)
    rank = _mode_rank(mode_names)
    if rank >= 40:
        return "Aランク強化"
    if rank == 30:
        return "Aランク本命"
    if rank == 20:
        return "広め候補"
    if "low_exR10_12_base" in s:
        return "Bランク参考"
    return "参考"


# ============================================================
# Metadata
# ============================================================

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
    if "SG" in t or "グランプリ" in t or "クラシック" in t or "オールスター" in t or "ダービー" in t:
        return "SG_like"
    if "G1" in t or "GⅠ" in t or "GI" in t or "周年" in t or "地区選" in t or "モーターボート大賞" in t:
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


def _race_title_stage(race_name: Any) -> str:
    name = _normalize_jp_text(race_name)
    if not name:
        return "stage_unknown"
    if "準優" in name:
        return "semifinal"
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


def _stage_combo(title_stage: str, day_no: int, race_no: int = 0) -> str:
    if title_stage in ("semifinal", "final", "dream", "selection", "general", "qualifying"):
        return title_stage
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


# ============================================================
# Strategies
# ============================================================

@dataclass
class V17Strategy:
    name: str
    description: str
    include_mid: bool = False
    include_low: bool = False
    low_filter: str = "all"
    low_stage_filter: str = "all"
    extra_filter: str = "all"
    mid_max_points: int = 1
    low_max_points: int = 1
    mid_non_head1: bool = True
    mid_race_filter: str = "all"
    mid_stage_filter: str = "all"
    mid_priority: str = "prob"
    low_priority: str = "prob"
    prefer_mid: bool = True


V17_STRATEGIES: List[V17Strategy] = [
    V17Strategy("low_exR10_12_base", "基準: 低オッズ 10〜12R除外", include_low=True, low_filter="exclude_r10_12"),
    V17Strategy("mode_balanced_venue_best", "本命候補: bad5×R04〜09 + イン強×R01〜03/R07〜09", include_low=True, low_filter="exclude_r10_12", extra_filter="venue_best_combo"),
    V17Strategy("mode_wide_not_standard", "広め候補: standard会場を除外", include_low=True, low_filter="exclude_r10_12", extra_filter="not_standard"),
    V17Strategy("mode_strict_bad5_r04_09", "厳選候補: bad5会場 × R04〜09", include_low=True, low_filter="r04_09", extra_filter="venue_bad5"),
    V17Strategy("mode_union_day_or_venue", "広め複合: 日程ベスト OR 会場ベスト", include_low=True, low_filter="exclude_r10_12", extra_filter="day_or_venue_best"),
    V17Strategy("mode_intersection_day_and_venue", "超厳選: 日程ベスト AND 会場ベスト", include_low=True, low_filter="exclude_r10_12", extra_filter="day_and_venue_best"),
    V17Strategy("mode_general_cup_bad5_r04_09", "カテゴリ厳選: 一般カップ系 × bad5 × R04〜09", include_low=True, low_filter="r04_09", extra_filter="general_cup_bad5"),
]


def _match_stage_filter(filter_name: str, event_day_no: int, race_no: int, stage_combo: str) -> bool:
    if filter_name == "all":
        return True
    if filter_name == "day1":
        return event_day_no == 1
    if filter_name == "not_day1":
        return event_day_no != 1
    if filter_name == "day2_3":
        return event_day_no in (2, 3)
    if filter_name == "day6plus":
        return event_day_no >= 6
    if filter_name == "day2_3_or_day6plus":
        return event_day_no in (2, 3) or event_day_no >= 6
    return True


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
    return True


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

    day_race_best = (
        (event_day_no in (2, 3) and 4 <= race_no <= 9)
        or (event_day_no >= 6 and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )
    venue_best = (
        (meta_venue_style == "bad5" and 4 <= race_no <= 9)
        or (meta_venue_style == "in_strong" and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    )

    if filter_name == "day_or_venue_best":
        return day_race_best or venue_best
    if filter_name == "day_and_venue_best":
        return day_race_best and venue_best
    if filter_name == "venue_bad5":
        return meta_venue_style == "bad5"
    if filter_name == "not_standard":
        return meta_venue_style != "standard"
    if filter_name == "venue_best_combo":
        return venue_best
    if filter_name == "general_cup_bad5":
        return meta_event_category == "general_cup_award" and meta_venue_style == "bad5"
    return True


def _is_mid_candidate(row: Dict[str, Any], st: V17Strategy, race_no: int, event_day_no: int, stage_combo: str) -> bool:
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


def _is_low_candidate(row: Dict[str, Any], venue_id: str, race_no: int, low_filter: str, low_stage_filter: str, event_day_no: int, stage_combo: str) -> bool:
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
        base_ok = True

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


def _select_bets(rows: List[Dict[str, Any]], st: V17Strategy, venue_id: str, race_no: int, event_day_no: int, stage_combo: str) -> List[Dict[str, Any]]:
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


# ============================================================
# LINE helpers
# ============================================================

def _count_sent_notifications() -> Dict[str, int]:
    day_row = fetch_one(
        """
        select count(*) as c
        from v2_line_notifications
        where race_date = %s
          and status = 'sent';
        """,
        (TARGET_DATE,),
    )
    month_row = fetch_one(
        """
        select count(*) as c
        from v2_line_notifications
        where race_date >= %s
          and race_date < %s
          and status = 'sent';
        """,
        (_month_start(TARGET_DATE), _next_month_start(TARGET_DATE)),
    )
    return {"day": _safe_int(day_row.get("c") if day_row else 0), "month": _safe_int(month_row.get("c") if month_row else 0)}


def _usage_guard() -> Optional[str]:
    counts = _count_sent_notifications()
    if counts["day"] >= DAILY_LINE_LIMIT:
        return f"daily_limit_reached {counts['day']}/{DAILY_LINE_LIMIT}"
    if counts["month"] >= MONTHLY_LINE_LIMIT:
        return f"monthly_limit_reached {counts['month']}/{MONTHLY_LINE_LIMIT}"
    return None


def _is_night_like_session(session: str, venue_id: str = "", title: str = "") -> bool:
    s = (session or "").lower()
    if s in ("night", "midnight"):
        return True
    t = title or ""
    if any(k in t for k in MIDNIGHT_KEYWORDS + NIGHT_KEYWORDS):
        return True
    return str(venue_id).zfill(2) in NIGHT_VENUE_IDS


def _session_match(session: str, venue_id: str = "", title: str = "") -> bool:
    if PRE_SESSION == "all":
        return True
    is_night = _is_night_like_session(session, venue_id, title)
    if PRE_SESSION == "night":
        return is_night
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
        lines.append(f"{i}. {r['venue_id']}場{r['race_no']}R {r['ticket']} / {r['odds']:.1f}倍")
        lines.append(f"   {r['mode_label']} / prob_rank={r['prob_rank']} market_rank={r['market_rank']}")
        lines.append(f"   {r['racegrp']} / venue={r['venue_style']} / cat={r['event_category']}")
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
    execute(
        """
        insert into v2_line_notifications (
            sent_at,
            notification_type,
            race_id,
            message,
            status,
            raw,
            race_date,
            venue_id,
            venue_code,
            race_no,
            decision_id,
            line_to,
            message_type,
            message_text,
            selector_version,
            selector_mode,
            mode_name,
            ticket,
            odds,
            line_response_status,
            line_response_body,
            error_message
        )
        values (
            now(), %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        );
        """,
        (
            "push_pre_candidate",
            first.get("race_id"),
            message,
            status,
            Jsonb({"selected": selected, "pre_session": PRE_SESSION, "test_mode": TEST_MODE, "dry_run": DRY_RUN}),
            TARGET_DATE,
            first.get("venue_id"),
            first.get("venue_id"),
            first.get("race_no"),
            None,
            LINE_TO if not DRY_RUN else "DRY_RUN",
            "push_pre_candidate",
            message,
            "v24_pre_candidate_notifier_pg",
            SELECTOR_MODE,
            f"pre_{PRE_SESSION}",
            first.get("ticket"),
            first.get("odds"),
            resp.get("status_code"),
            resp.get("body"),
            "",
        ),
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    _require_settings()
    _ensure_line_notification_columns()

    print("✅ v24_pre_candidate_notifier_pg.py VERSION 2026-07-05 railway-postgres", flush=True)
    print("=== v24 PG 仮買い目LINE通知開始 ===", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} PRE_SESSION={PRE_SESSION} SELECTOR_MODE={SELECTOR_MODE} "
        f"DRY_RUN={DRY_RUN} TEST_MODE={TEST_MODE} MIN_ODDS_ROWS={MIN_ODDS_ROWS}",
        flush=True,
    )

    guard = _usage_guard()
    if guard:
        print(f"LINE送信上限ガード: {guard}", flush=True)
        print("=== v24 PG 仮買い目LINE通知終了 ===", flush=True)
        return

    strategies_by_name = {s.name: s for s in V17_STRATEGIES}
    strategy_names = [n for n in _selector_strategy_names(SELECTOR_MODE) if n in strategies_by_name]
    print("対象モード: " + ", ".join(strategy_names), flush=True)

    event_day_by_venue = _compute_event_day_by_venue(TARGET_DATE)
    races, entries_by_race, odds_by_race = _fetch_live_day_rows(TARGET_DATE)

    if not races:
        print("対象日のv2_racesがありません。先に当日補修を実行してください。", flush=True)
        print("=== v24 PG 仮買い目LINE通知終了 ===", flush=True)
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
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
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
                st.extra_filter,
                meta_venue_style,
                meta_event_category,
                meta_gender,
                meta_grade,
                meta_session,
                event_day_no,
                race_no,
            ):
                continue

            bets = _select_bets(ranked_rows, st, venue_id, race_no, event_day_no, combo_stage)
            for b in bets:
                ticket = str(b.get("ticket", ""))
                if not ticket:
                    continue
                rec = by_ticket.setdefault(
                    ticket,
                    {
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
                    },
                )
                rec["modes"].append(st_name)
                rec["priority"] = max(rec["priority"], _safe_float(b.get("select_priority"), 0.0))

        for rec in by_ticket.values():
            rec["mode_rank"] = _mode_rank(rec["modes"])
            rec["mode_label"] = _mode_label(rec["modes"])
            rows_out.append(rec)

    rows_out.sort(key=lambda r: (r["mode_rank"], r["priority"], -r["race_no"]), reverse=True)
    selected = rows_out[:DAILY_MAX_POINTS]

    print(
        f"races={len(races)} ready_races={ready_races} candidates={len(rows_out)} selected={len(selected)} "
        f"skipped_not_ready={skipped_not_ready} skipped_entries={skipped_entries} "
        f"skipped_odds={skipped_odds} skipped_session={skipped_session}",
        flush=True,
    )
    print(f"low_core_total={low_core_total}", flush=True)

    if not selected:
        print("仮候補はありません。通知しません。", flush=True)
        print("=== v24 PG 仮買い目LINE通知終了 ===", flush=True)
        return

    msg = _build_pre_message(selected)
    print("\n--- pre message ---", flush=True)
    print(msg, flush=True)

    resp = _send_line_message(msg)
    ok = 200 <= int(resp.get("status_code", 0)) < 300
    if DRY_RUN:
        status = "dry_run"
    else:
        status = "sent" if ok else "failed"
    _save_pre_notification(msg, status, resp, selected)

    print("\n=== v24 PG 仮買い目LINE通知 summary ===", flush=True)
    print(f"status={status} dry_run={DRY_RUN} response_status={resp.get('status_code')}", flush=True)
    print("=== v24 PG 仮買い目LINE通知終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise