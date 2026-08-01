# -*- coding: utf-8 -*-
"""
v22_realtime_decision_engine_pg.py

Railway Postgres版。
v21で保存した直前snapshotを使い、最終 BUY / WATCH / SKIP 判定を保存します。

Railway Start Command:
    python -u v22_realtime_decision_engine_pg.py

通常は run_v22_pg.py から起動してください。
"""
from __future__ import annotations

import itertools
import math
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from db_pg import execute, fetch_all, upsert_rows

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
DECISION_LABEL = os.getenv("DECISION_LABEL", SNAPSHOT_LABEL).strip() or SNAPSHOT_LABEL
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
REQUIRE_EXHIBITION = os.getenv("REQUIRE_EXHIBITION", "0").strip() in ("1", "true", "True", "yes", "YES")
SAVE_DECISIONS = os.getenv("SAVE_DECISIONS", "1").strip() not in ("0", "false", "False", "no", "NO")
MIN_ODDS_ROWS = int(os.getenv("MIN_ODDS_ROWS", "100"))
MIN_ODDS = float(os.getenv("MIN_ODDS", "3.0"))
MAX_ODDS = float(os.getenv("MAX_ODDS", "5.5"))
MAX_WIND_M = float(os.getenv("MAX_WIND_M", "6.0"))
MAX_WAVE_CM = float(os.getenv("MAX_WAVE_CM", "8.0"))
BAD_EXH_TIME_DIFF = float(os.getenv("BAD_EXH_TIME_DIFF", "0.18"))
BAD_ST_DIFF = float(os.getenv("BAD_ST_DIFF", "0.10"))
EVENT_DAY_LOOKBACK = int(os.getenv("EVENT_DAY_LOOKBACK", "10"))

UNIT_YEN = int(os.getenv("UNIT_YEN", "100"))
DAILY_BUDGET_YEN = int(os.getenv("DAILY_BUDGET_YEN", "1000"))
DAILY_MAX_POINTS = DAILY_BUDGET_YEN // UNIT_YEN if DAILY_BUDGET_YEN > 0 else 999999
PROB_TEMP = float(os.getenv("PROB_TEMP", "2.20"))
TARGET_VENUES = [str(i).zfill(2) for i in range(1, 25)]

CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}
BAD5_VENUES = {"01", "04", "05", "06", "23"}
IN_STRONG_VENUES = {"12", "15", "18", "21", "24"}
ROUGH_VENUES = {"02", "03", "04", "05", "06"}
BAD_VENUES = BAD5_VENUES

META_TEXT_KEYS = (
    "race_title", "race_name", "title", "event_title", "event_name",
    "series_title", "series_name", "tournament_title", "tournament_name",
    "meeting_title", "meet_title", "grade", "grade_type", "category",
    "race_category", "race_type", "program_name", "subtitle", "session_type",
)

# name, include_low, low_filter, extra_filter
STRATEGIES = [
    ("low_exR10_12_base", True, "exclude_r10_12", "all"),
    ("mode_balanced_venue_best", True, "exclude_r10_12", "venue_best_combo"),
    ("mode_intersection_day_and_venue", True, "exclude_r10_12", "day_and_venue_best"),
    ("mode_general_cup_bad5_r04_09", True, "r04_09", "general_cup_bad5"),
    ("mode_strict_bad5_r04_09", True, "r04_09", "venue_bad5"),
    ("mode_union_day_or_venue", True, "exclude_r10_12", "day_or_venue_best"),
    ("mode_wide_not_standard", True, "exclude_r10_12", "not_standard"),
]


def _require_settings() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")


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
    return f"{nums[0]}-{nums[1]}-{nums[2]}" if len(nums) >= 3 else s.strip()


ALL_LANES = {1, 2, 3, 4, 5, 6}


def _expected_ticket_set(active_lanes: set[int]) -> set[str]:
    return {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations(sorted(active_lanes), 3)
    }


def _evaluate_odds_snapshot(odds: Dict[str, float]) -> Dict[str, Any]:
    """
    6艇120通り・5艇60通り・4艇24通りの完全一致を判定する。

    件数だけではなく、ticket集合が特定の有効艇集合の全順列と
    完全一致した場合だけreadyとする。119件、取消前後混在、
    malformed ticketはすべてnot ready。
    """
    valid_tickets: set[str] = set()
    malformed = 0

    for raw_ticket, raw_odds in (odds or {}).items():
        ticket = _norm_ticket(raw_ticket)
        parts = ticket.split("-")
        if (
            len(parts) != 3
            or any(not part.isdigit() for part in parts)
        ):
            malformed += 1
            continue

        lanes = [int(part) for part in parts]
        if (
            any(lane not in ALL_LANES for lane in lanes)
            or len(set(lanes)) != 3
            or _safe_float(raw_odds, 0.0) <= 0
        ):
            malformed += 1
            continue

        valid_tickets.add(ticket)

    active_lanes = sorted({
        lane
        for ticket in valid_tickets
        for lane in map(int, ticket.split("-"))
    })
    active_lane_set = set(active_lanes)
    lane_count_valid = 4 <= len(active_lanes) <= 6
    expected = (
        _expected_ticket_set(active_lane_set)
        if lane_count_valid
        else set()
    )
    missing = expected - valid_tickets
    unexpected = valid_tickets - expected
    expected_count = len(expected)
    ready = (
        lane_count_valid
        and malformed == 0
        and len(valid_tickets) == expected_count
        and not missing
        and not unexpected
    )

    return {
        "ready": ready,
        "valid_tickets": len(valid_tickets),
        "active_lanes": active_lanes,
        "scratched_lanes": sorted(ALL_LANES - active_lane_set),
        "expected_count": expected_count,
        "malformed": malformed,
        "missing": len(missing),
        "unexpected": len(unexpected),
    }


def _odds_status_text(status: Dict[str, Any]) -> str:
    return (
        f"valid_tickets={status['valid_tickets']} "
        f"active_lanes={status['active_lanes']} "
        f"scratched_lanes={status['scratched_lanes']} "
        f"expected_count={status['expected_count']} "
        f"malformed={status['malformed']} "
        f"missing={status['missing']} "
        f"unexpected={status['unexpected']}"
    )


def _norm_text(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s or "")).strip()


def _rid_prefix(date_str: str) -> str:
    return date_str.replace("-", "")


def _next_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _shift_day(date_str: str, days: int) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def _date_str(v: Any) -> str:
    return str(v)[:10] if v is not None else ""


def _entry_by_lane(entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for e in entries:
        lane = _safe_int(e.get("lane"), 0)
        if 1 <= lane <= 6:
            out[lane] = e
    return out


def _ticket_lanes(ticket: str) -> List[int]:
    return [int(x) for x in re.findall(r"[1-6]", str(ticket))[:3]]


def _race_group(race_no: int) -> str:
    if race_no <= 3:
        return "R01_03"
    if race_no <= 6:
        return "R04_06"
    if race_no <= 9:
        return "R07_09"
    return "R10_12"


def _ensure_schema() -> None:
    ddl = [
        "create table if not exists v2_realtime_decisions (id bigserial primary key);",
        "alter table v2_realtime_decisions add column if not exists race_id text;",
        "alter table v2_realtime_decisions add column if not exists race_date date;",
        "alter table v2_realtime_decisions add column if not exists venue_id text;",
        "alter table v2_realtime_decisions add column if not exists venue_code text;",
        "alter table v2_realtime_decisions add column if not exists race_no integer;",
        "alter table v2_realtime_decisions add column if not exists decision_label text;",
        "alter table v2_realtime_decisions add column if not exists decision_at timestamptz;",
        "alter table v2_realtime_decisions add column if not exists selector_version text;",
        "alter table v2_realtime_decisions add column if not exists selector_mode text;",
        "alter table v2_realtime_decisions add column if not exists mode_name text;",
        "alter table v2_realtime_decisions add column if not exists mode_label text;",
        "alter table v2_realtime_decisions add column if not exists ticket text;",
        "alter table v2_realtime_decisions add column if not exists odds numeric;",
        "alter table v2_realtime_decisions add column if not exists prob numeric;",
        "alter table v2_realtime_decisions add column if not exists prob_rank integer;",
        "alter table v2_realtime_decisions add column if not exists market_rank integer;",
        "alter table v2_realtime_decisions add column if not exists raw_ev numeric;",
        "alter table v2_realtime_decisions add column if not exists base_score numeric;",
        "alter table v2_realtime_decisions add column if not exists realtime_score numeric;",
        "alter table v2_realtime_decisions add column if not exists final_score numeric;",
        "alter table v2_realtime_decisions add column if not exists recommendation text;",
        "alter table v2_realtime_decisions add column if not exists skip_reason text;",
        "alter table v2_realtime_decisions add column if not exists positive_reasons jsonb;",
        "alter table v2_realtime_decisions add column if not exists negative_reasons jsonb;",
        "alter table v2_realtime_decisions add column if not exists stake_yen integer;",
        "alter table v2_realtime_decisions add column if not exists expected_return_yen integer;",
        "alter table v2_realtime_decisions add column if not exists was_notified boolean default false;",
        "alter table v2_realtime_decisions add column if not exists notified_at timestamptz;",
        "alter table v2_realtime_decisions add column if not exists raw jsonb;",
        "create unique index if not exists uq_v2_realtime_decisions_main on v2_realtime_decisions (race_id, decision_label, selector_mode, mode_name, ticket);",
    ]
    for sql in ddl:
        execute(sql)


def _fetch_live_day_rows(date_str: str):
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
    races = [r for r in races if str(r.get("venue_id") or r.get("venue_code") or "").zfill(2) in TARGET_VENUES]

    entries_rows = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id asc, lane asc;
        """,
        (day_prefix, next_prefix),
    )
    entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for e in entries_rows:
        entries_by_race.setdefault(str(e.get("race_id")), []).append(e)

    odds_rows = fetch_all(
        """
        select *
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id asc, ticket asc;
        """,
        (day_prefix, next_prefix),
    )
    odds_by_race: Dict[str, Dict[str, float]] = {}
    for o in odds_rows:
        rid = str(o.get("race_id"))
        ticket = _norm_ticket(o.get("ticket"))
        odds = _safe_float(o.get("odds"), 0.0)
        if rid and ticket and odds > 0:
            odds_by_race.setdefault(rid, {})[ticket] = odds
    return races, entries_by_race, odds_by_race


def _fetch_race_rows_for_event_day(target_date: str) -> List[Dict[str, Any]]:
    start = _shift_day(target_date, -EVENT_DAY_LOOKBACK)
    return fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s and race_date <= %s
        order by race_date asc, venue_id asc, race_no asc;
        """,
        (start, target_date),
    )


def _compute_event_day_by_venue(target_date: str) -> Dict[str, int]:
    rows = _fetch_race_rows_for_event_day(target_date)
    dates_by_venue: Dict[str, List[str]] = {}
    for r in rows:
        v = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        d = _date_str(r.get("race_date"))
        if not v or not d:
            continue
        dates_by_venue.setdefault(v, [])
        if d not in dates_by_venue[v]:
            dates_by_venue[v].append(d)
    out: Dict[str, int] = {}
    for v, ds in dates_by_venue.items():
        cur = 0
        prev = ""
        for d in sorted(ds):
            cur = cur + 1 if prev and d == _shift_day(prev, 1) else 1
            prev = d
            if d == target_date:
                out[v] = cur
    return out


def _fetch_realtime_for_day(date_str: str, snapshot_label: str):
    exh = fetch_all(
        "select * from v2_realtime_exhibition_snapshots where race_date=%s and snapshot_label=%s order by race_id asc,lane asc;",
        (date_str, snapshot_label),
    )
    weather = fetch_all(
        "select * from v2_realtime_weather_snapshots where race_date=%s and snapshot_label=%s order by race_id asc;",
        (date_str, snapshot_label),
    )
    odds = fetch_all(
        "select * from v2_realtime_odds_snapshots where race_date=%s and snapshot_label=%s order by race_id asc, market_rank asc nulls last;",
        (date_str, snapshot_label),
    )
    entries = fetch_all(
        "select * from v2_realtime_entry_snapshots where race_date=%s and snapshot_label=%s order by race_id asc,lane asc;",
        (date_str, snapshot_label),
    )
    exh_by: Dict[str, List[Dict[str, Any]]] = {}
    for r in exh:
        exh_by.setdefault(str(r.get("race_id")), []).append(r)
    weather_by = {str(r.get("race_id")): r for r in weather}
    odds_by: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for r in odds:
        rid = str(r.get("race_id")); t = _norm_ticket(r.get("ticket"))
        if rid and t:
            odds_by.setdefault(rid, {})[t] = r
    entry_by: Dict[str, List[Dict[str, Any]]] = {}
    for r in entries:
        entry_by.setdefault(str(r.get("race_id")), []).append(r)
    return exh_by, weather_by, odds_by, entry_by


def _metadata_text(row: Dict[str, Any]) -> str:
    vals = []
    for k in META_TEXT_KEYS:
        s = _norm_text(row.get(k))
        if s:
            vals.append(f"{k}={s}")
    return " / ".join(vals)


def _best_race_name(row: Dict[str, Any]) -> str:
    for k in ("race_name", "race_title", "title", "program_name"):
        s = _norm_text(row.get(k))
        if s:
            return s
    return ""


def _infer_event_category(meta_text: str) -> str:
    t = _norm_text(meta_text); tu = t.upper()
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
    if "SG" in tu or "グランプリ" in t or "クラシック" in t or "オールスター" in t or "ダービー" in t:
        return "SG_like"
    if "周年" in t or "開設" in t or "地区選" in t or "モーターボート大賞" in t or "ダイヤモンドカップ" in t:
        return "G1_like"
    if "G2" in tu or "GⅡ" in t:
        return "G2_like"
    if "G3" in tu or "GⅢ" in t or "企業杯" in t:
        return "G3_like"
    if "一般" in t:
        return "general_named"
    if "杯" in t or "カップ" in t or "CUP" in tu or "賞" in t or "記念" in t:
        return "general_cup_award"
    return "category_other"


def _infer_grade(meta_text: str) -> str:
    t = _norm_text(meta_text).upper()
    if not t:
        return "grade_unknown"
    if "SG" in t or "グランプリ" in t or "クラシック" in t or "オールスター" in t or "ダービー" in t:
        return "SG_like"
    if "G1" in t or "GⅠ" in t or "GI" in t or "周年" in t or "開設" in t:
        return "G1_like"
    if "G2" in t or "GⅡ" in t or "GII" in t:
        return "G2_like"
    if "G3" in t or "GⅢ" in t or "GIII" in t:
        return "G3_like"
    if "一般" in t:
        return "GENERAL"
    return "grade_other"


def _infer_gender(meta_text: str) -> str:
    t = _norm_text(meta_text)
    if not t:
        return "gender_unknown"
    if "オールレディース" in t:
        return "all_ladies"
    if "ヴィーナス" in t or "ビーナス" in t:
        return "venus"
    if "レディース" in t or "女子" in t or "女流" in t:
        return "ladies_other"
    return "mixed_or_unknown"


def _infer_session_type(row: Dict[str, Any]) -> str:
    s = _norm_text(row.get("session_type")).lower()
    return s if s else "session_unknown"


def _infer_venue_style(venue_id: str) -> str:
    v = str(venue_id).zfill(2)
    if v in BAD5_VENUES:
        return "bad5"
    if v in ROUGH_VENUES:
        return "rough"
    if v in IN_STRONG_VENUES:
        return "in_strong"
    return "standard"


def _stage_combo(race_name: str, day_no: int, race_no: int) -> str:
    name = _norm_text(race_name)
    if "準優" in name:
        return "semifinal"
    if "優勝" in name and "準優" not in name:
        return "final"
    if "ドリーム" in name:
        return "dream"
    if "選抜" in name or "特選" in name or "特賞" in name:
        return "selection"
    if "一般" in name:
        return "general"
    if "予選" in name:
        return "qualifying"
    if day_no == 1:
        return "inferred_day1"
    if 2 <= day_no <= 3:
        return "inferred_day2_3"
    if day_no >= 6 and race_no >= 10:
        return "inferred_finalday_r10_12"
    return "inferred_other"


def _selector_strategy_names(mode: str) -> List[str]:
    if mode == "strict":
        return ["mode_intersection_day_and_venue", "mode_general_cup_bad5_r04_09", "mode_strict_bad5_r04_09"]
    if mode in ("ab", "a_b", "rank_ab", "test_ab"):
        return ["mode_balanced_venue_best", "mode_intersection_day_and_venue", "mode_general_cup_bad5_r04_09", "mode_strict_bad5_r04_09", "low_exR10_12_base"]
    if mode == "wide":
        return ["mode_balanced_venue_best", "mode_union_day_or_venue", "mode_wide_not_standard", "mode_intersection_day_and_venue", "mode_general_cup_bad5_r04_09", "mode_strict_bad5_r04_09"]
    if mode == "all":
        return [s[0] for s in STRATEGIES]
    return ["mode_balanced_venue_best", "mode_intersection_day_and_venue", "mode_general_cup_bad5_r04_09", "mode_strict_bad5_r04_09"]


def _mode_rank(names: List[str]) -> int:
    s = set(names)
    if s & {"mode_intersection_day_and_venue", "mode_general_cup_bad5_r04_09", "mode_strict_bad5_r04_09"}:
        return 40
    if "mode_balanced_venue_best" in s:
        return 30
    if s & {"mode_union_day_or_venue", "mode_wide_not_standard"}:
        return 20
    if "low_exR10_12_base" in s:
        return 10
    return 1


def _mode_label(names: List[str]) -> str:
    rank = _mode_rank(names)
    if rank >= 40:
        return "Aランク強化"
    if rank == 30:
        return "Aランク本命"
    if rank == 20:
        return "広め候補"
    if "low_exR10_12_base" in set(names):
        return "Bランク参考"
    return "参考"


def _match_extra_filter(name: str, venue_style: str, event_category: str, gender: str, grade: str, session: str, day_no: int, race_no: int) -> bool:
    day_best = (day_no in (2, 3) and 4 <= race_no <= 9) or (day_no >= 6 and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    venue_best = (venue_style == "bad5" and 4 <= race_no <= 9) or (venue_style == "in_strong" and (1 <= race_no <= 3 or 7 <= race_no <= 9))
    if name == "all":
        return True
    if name == "venue_best_combo":
        return venue_best
    if name == "day_and_venue_best":
        return day_best and venue_best
    if name == "day_or_venue_best":
        return day_best or venue_best
    if name == "not_standard":
        return venue_style != "standard"
    if name == "venue_bad5":
        return venue_style == "bad5"
    if name == "general_cup_bad5":
        return event_category == "general_cup_award" and venue_style == "bad5"
    return True


def _lane_raw_strength(entry: Dict[str, Any], lane: int, venue_id: str) -> float:
    cls = _safe_int(entry.get("racer_class"), 2)
    cls_w = CLASS_WEIGHT.get(cls, 0.55)
    win_rate = _safe_float(entry.get("national_win_rate"), 0.0)
    nat2 = _safe_float(entry.get("national_place2_rate"), 32.0)
    loc2 = _safe_float(entry.get("local_place2_rate"), 30.0)
    mot2 = _safe_float(entry.get("motor_place2_rate"), 33.0)
    boat2 = _safe_float(entry.get("boat_place2_rate"), 34.0)
    avg_st = _safe_float(entry.get("avg_st") or entry.get("average_st"), 0.18)
    course = VENUE_COURSE_BIAS.get(venue_id, DEFAULT_COURSE_BIAS).get(lane, DEFAULT_COURSE_BIAS[lane])
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return cls_w + win_rate * 0.16 + (nat2 / 100) * 0.90 + (loc2 / 100) * 0.55 + (mot2 / 100) * 0.45 + (boat2 / 100) * 0.25 + st_score * 0.35 + course * 0.22


def _rank_candidates(entries: List[Dict[str, Any]], venue_id: str, odds: Dict[str, float]) -> List[Dict[str, Any]]:
    by = _entry_by_lane(entries)
    status = _evaluate_odds_snapshot(odds)
    active_lanes = [
        lane for lane in status["active_lanes"]
        if lane in by
    ]
    if len(active_lanes) < 4:
        return []

    raw = {
        lane: _lane_raw_strength(by[lane], lane, venue_id)
        for lane in active_lanes
    }
    weights = {
        lane: math.exp(raw[lane] / PROB_TEMP)
        for lane in active_lanes
    }
    total = sum(weights.values())
    rows: List[Dict[str, Any]] = []
    for a in active_lanes:
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in active_lanes:
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in active_lanes:
                if c == a or c == b:
                    continue
                ticket = f"{a}-{b}-{c}"
                odd = _safe_float(odds.get(ticket), 0.0)
                if odd <= 0:
                    continue
                prob = pa * pb * (weights[c] / total_c)
                rows.append({"ticket": ticket, "prob": prob, "odds": odd, "raw_ev": prob * odd})
    for i, r in enumerate(sorted(rows, key=lambda x: (x["odds"], -x["prob"])), 1):
        r["market_rank"] = i
    for i, r in enumerate(sorted(rows, key=lambda x: x["prob"], reverse=True), 1):
        r["prob_rank"] = i
    rows.sort(key=lambda x: x["prob"], reverse=True)
    return rows


def _is_low_candidate(row: Dict[str, Any], venue_id: str, race_no: int, low_filter: str) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)
    if not (11 <= pr <= 20 and mr == 1 and 3.0 <= odds < 5.0):
        return False
    if low_filter == "r04_09":
        return 4 <= race_no <= 9
    if low_filter == "exclude_r10_12":
        return race_no <= 9
    if low_filter == "bad5":
        return venue_id in BAD_VENUES
    return True


def _priority(row: Dict[str, Any]) -> float:
    prob = _safe_float(row.get("prob"), 0.0)
    ev = _safe_float(row.get("raw_ev"), 0.0)
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    return prob * 10000.0 + ev * 100.0 - pr * 0.01 - mr * 0.001


def _select_bets(rows: List[Dict[str, Any]], strategy: Tuple[str, bool, str, str], venue_id: str, race_no: int) -> List[Dict[str, Any]]:
    name, include_low, low_filter, extra_filter = strategy
    if not include_low:
        return []
    lows = []
    for r in rows:
        if _is_low_candidate(r, venue_id, race_no, low_filter):
            x = dict(r)
            x["label"] = "low"
            x["select_priority"] = _priority(x)
            lows.append(x)
    lows.sort(key=lambda x: x["select_priority"], reverse=True)
    return lows[:1]


def _rt_odds_dict(rows: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for t, r in (rows or {}).items():
        ticket = _norm_ticket(t or r.get("ticket"))
        odds = _safe_float(r.get("odds"), 0.0)
        if ticket and odds > 0:
            out[ticket] = odds
    return out


def _format_entries(entries: List[Dict[str, Any]]) -> str:
    by = _entry_by_lane(entries)
    out = []
    for lane in range(1, 7):
        e = by.get(lane, {})
        name = _norm_text(e.get("racer_name")) or str(e.get("racer_number", "?"))
        cls = {4: "A1", 3: "A2", 2: "B1", 1: "B2"}.get(_safe_int(e.get("racer_class"), 0), str(e.get("racer_class", "?")))
        out.append(f"{lane}:{name}({cls})")
    return " / ".join(out)


def _low_precondition_count(rows: List[Dict[str, Any]]) -> int:
    n = 0
    for r in rows:
        if 11 <= _safe_int(r.get("prob_rank"), 999) <= 20 and _safe_int(r.get("market_rank"), 999) == 1 and 3.0 <= _safe_float(r.get("odds"), 0.0) < 5.0:
            n += 1
    return n


def _realtime_judge(cand: Dict[str, Any], exh_rows: List[Dict[str, Any]], weather: Dict[str, Any], odds_snap: Optional[Dict[str, Any]], entry_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    pos: List[str] = []
    neg: List[str] = []
    score = 0.0
    skip_reason = ""
    ticket = str(cand.get("ticket", ""))
    lanes = _ticket_lanes(ticket)
    head_lane = lanes[0] if lanes else 0
    final_odds = _safe_float(cand.get("odds"), 0.0)
    final_rank = _safe_int(cand.get("market_rank"), 999)

    if odds_snap:
        final_odds = _safe_float(odds_snap.get("odds"), final_odds)
        final_rank = _safe_int(odds_snap.get("market_rank"), final_rank)
        if odds_snap.get("is_odds_too_low"):
            neg.append("直前オッズが下がりすぎ"); score -= 1.5
        elif MIN_ODDS <= final_odds <= MAX_ODDS:
            pos.append("直前オッズが想定範囲"); score += 1.0
        if odds_snap.get("is_odds_steam"):
            pos.append("直前で売れ気配"); score += 0.3
        if odds_snap.get("is_odds_drift"):
            neg.append("直前で人気低下"); score -= 0.5
    else:
        neg.append("直前オッズsnapshotなし"); score -= 0.5

    if final_odds < MIN_ODDS:
        skip_reason = "odds_too_low"
    elif final_odds > MAX_ODDS:
        neg.append("通常モード想定よりオッズ高め"); score -= 0.7

    if weather:
        wind = _safe_float(weather.get("wind_speed_m"), 0.0)
        wave = _safe_float(weather.get("wave_height_cm"), 0.0)
        if wind >= MAX_WIND_M:
            neg.append(f"風速{wind:g}mで強め"); score -= 1.5
        elif wind > 0:
            pos.append(f"風速{wind:g}m"); score += 0.2
        if wave >= MAX_WAVE_CM:
            neg.append(f"波高{wave:g}cmで高め"); score -= 1.0
    else:
        neg.append("直前気象snapshotなし"); score -= 0.3

    changed = [r for r in entry_rows if r.get("is_course_changed")]
    absent = [r for r in entry_rows if r.get("is_absent") or r.get("is_late_absent")]
    if absent:
        skip_reason = "absent"; neg.append("欠場/直前欠場あり"); score -= 9
    if changed:
        neg.append("展示進入変更あり"); score -= 2.0

    exh_by = {_safe_int(r.get("lane"), 0): r for r in exh_rows}
    if len(exh_by) >= 6:
        pos.append("展示6艇分あり"); score += 0.5
        head = exh_by.get(head_lane, {})
        if head:
            hdiff = _safe_float(head.get("exhibition_time_diff"), 0.0)
            sdiff = _safe_float(head.get("start_timing_diff"), 0.0)
            hrank = _safe_int(head.get("exhibition_time_rank"), 9)
            srank = _safe_int(head.get("start_timing_rank"), 9)
            if hdiff >= BAD_EXH_TIME_DIFF or hrank >= 5:
                neg.append(f"頭艇の展示タイム弱い rank={hrank} diff={hdiff:g}"); score -= 1.5
            else:
                pos.append(f"頭艇展示OK rank={hrank}"); score += 0.7
            if sdiff >= BAD_ST_DIFF or srank >= 5:
                neg.append(f"頭艇の展示ST弱い rank={srank} diff={sdiff:g}"); score -= 1.0
            else:
                pos.append(f"頭艇ST展示OK rank={srank}"); score += 0.5
    else:
        neg.append("展示6艇分未取得")
        if REQUIRE_EXHIBITION:
            skip_reason = "exhibition_not_complete"; score -= 5
        else:
            score -= 0.3

    if _safe_int(cand.get("mode_rank"), 1) >= 40:
        pos.append("強化/厳選モード"); score += 1.0
    elif _safe_int(cand.get("mode_rank"), 1) >= 30:
        pos.append("通常本命モード"); score += 0.6

    rec = "skip" if skip_reason else ("buy" if score >= 1.0 else "watch" if score >= 0.0 else "skip")
    return {"recommendation": rec, "skip_reason": skip_reason, "positive_reasons": pos, "negative_reasons": neg, "realtime_score": round(score, 4), "odds": final_odds, "market_rank": final_rank}


def _save_decisions(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    dedup: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
    for r in rows:
        key = (str(r.get("race_id")), str(r.get("decision_label")), str(r.get("selector_mode")), str(r.get("mode_name")), str(r.get("ticket")))
        dedup[key] = r
    out = list(dedup.values())
    if len(out) != len(rows):
        print(f"decision rows deduped: {len(rows)} -> {len(out)}", flush=True)
    return upsert_rows("v2_realtime_decisions", out, ["race_id", "decision_label", "selector_mode", "mode_name", "ticket"])


def main() -> None:
    _require_settings()
    _ensure_schema()
    print("✅ v22_realtime_decision_engine_pg.py VERSION 2026-08-01 dynamic-odds-completeness-v2", flush=True)
    print("=== v22 PG 直前判定エンジン開始 ===", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} DECISION_LABEL={DECISION_LABEL} SELECTOR_MODE={SELECTOR_MODE} REQUIRE_EXHIBITION={REQUIRE_EXHIBITION} ODDS_READY_MODE=dynamic_exact_120_60_24", flush=True)

    strategy_names = _selector_strategy_names(SELECTOR_MODE)
    strategies = [s for s in STRATEGIES if s[0] in strategy_names]
    print("対象モード: " + ", ".join(s[0] for s in strategies), flush=True)

    event_day_by_venue = _compute_event_day_by_venue(TARGET_DATE)
    races, entries_by_race, odds_by_race = _fetch_live_day_rows(TARGET_DATE)
    exh_by, weather_by, rt_odds_by, rt_entry_by = _fetch_realtime_for_day(TARGET_DATE, SNAPSHOT_LABEL)
    print(f"races={len(races)} realtime_exh_races={len(exh_by)} weather_races={len(weather_by)} rt_odds_races={len(rt_odds_by)} rt_entry_races={len(rt_entry_by)}", flush=True)
    if not races:
        print("対象日のv2_racesがありません。先に当日補修を実行してください。", flush=True)
        return

    candidate_rows: List[Dict[str, Any]] = []
    skipped_not_ready = skipped_entries = skipped_odds = ready_races = low_core_total = mode_extra_match_races = 0

    for race in races:
        rid = str(race.get("race_id"))
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)
        entries = entries_by_race.get(rid, [])
        base_odds = odds_by_race.get(rid, {})
        rt_odds = _rt_odds_dict(rt_odds_by.get(rid, {}))

        rt_status = _evaluate_odds_snapshot(rt_odds)
        base_status = _evaluate_odds_snapshot(base_odds)

        # 直前snapshotが完全なら最優先。未完成なら完全なbaseへフォールバック。
        if rt_status["ready"]:
            odds = rt_odds
            odds_status = rt_status
            odds_source = "realtime"
        elif base_status["ready"]:
            odds = base_odds
            odds_status = base_status
            odds_source = "base_fallback"
        else:
            skipped_not_ready += 1
            skipped_odds += 1
            print(
                f"ODDS_NOT_READY race_id={rid} "
                f"rt=({_odds_status_text(rt_status)}) "
                f"base=({_odds_status_text(base_status)})",
                flush=True,
            )
            continue

        entry_lanes = set(_entry_by_lane(entries))
        required_lanes = set(odds_status["active_lanes"])
        if not required_lanes.issubset(entry_lanes):
            skipped_not_ready += 1
            skipped_entries += 1
            print(
                f"ENTRIES_NOT_READY race_id={rid} "
                f"required_lanes={sorted(required_lanes)} "
                f"entry_lanes={sorted(entry_lanes)}",
                flush=True,
            )
            continue
        ready_races += 1

        meta = _metadata_text(race)
        grade = _infer_grade(meta)
        gender = _infer_gender(meta)
        event_cat = _infer_event_category(meta)
        session = _infer_session_type(race)
        venue_style = _infer_venue_style(venue_id)
        race_name = _best_race_name(race)
        day_no = event_day_by_venue.get(venue_id, 1)
        stage = _stage_combo(race_name, day_no, race_no)
        ranked = _rank_candidates(entries, venue_id, odds)
        low_core_total += _low_precondition_count(ranked)

        by_ticket: Dict[str, Dict[str, Any]] = {}
        for st in strategies:
            st_name, include_low, low_filter, extra_filter = st
            if not _match_extra_filter(extra_filter, venue_style, event_cat, gender, grade, session, day_no, race_no):
                continue
            for b in _select_bets(ranked, st, venue_id, race_no):
                ticket = str(b.get("ticket", ""))
                if not ticket:
                    continue
                rec = by_ticket.setdefault(ticket, {
                    "race_id": rid, "race_date": TARGET_DATE, "venue_id": venue_id, "race_no": race_no,
                    "race_title": race_name, "session": session, "event_day_no": day_no, "stage_combo": stage,
                    "racegrp": _race_group(race_no), "venue_style": venue_style, "event_category": event_cat,
                    "grade": grade, "gender": gender, "ticket": ticket, "odds": _safe_float(b.get("odds"), 0.0),
                    "prob_rank": _safe_int(b.get("prob_rank"), 999), "market_rank": _safe_int(b.get("market_rank"), 999),
                    "prob": _safe_float(b.get("prob"), 0.0), "raw_ev": _safe_float(b.get("raw_ev"), 0.0),
                    "priority": _safe_float(b.get("select_priority"), 0.0), "modes": [], "entries": _format_entries(entries),
                    "odds_source": odds_source,
                    "active_lanes": odds_status["active_lanes"],
                    "expected_odds_count": odds_status["expected_count"],
                })
                rec["modes"].append(st_name)
                rec["priority"] = max(rec["priority"], _safe_float(b.get("select_priority"), 0.0))
        if by_ticket:
            mode_extra_match_races += 1
        for rec in by_ticket.values():
            rec["mode_rank"] = _mode_rank(rec["modes"])
            rec["mode_label"] = _mode_label(rec["modes"])
            candidate_rows.append(rec)

    candidate_rows.sort(key=lambda r: (r["mode_rank"], r["priority"], -r["race_no"]), reverse=True)

    decision_rows: List[Dict[str, Any]] = []
    printable: List[Dict[str, Any]] = []
    for cand in candidate_rows:
        rid = cand["race_id"]; ticket = cand["ticket"]
        judge = _realtime_judge(cand, exh_by.get(rid, []), weather_by.get(rid, {}), rt_odds_by.get(rid, {}).get(ticket), rt_entry_by.get(rid, []))
        modes = cand.get("modes", [])
        mode_name = modes[0] if modes else cand.get("mode_label", "")
        venue_id = str(cand.get("venue_id") or "").zfill(2)
        row = {
            "race_id": rid, "race_date": TARGET_DATE, "venue_id": venue_id, "venue_code": venue_id, "race_no": cand.get("race_no"),
            "decision_label": DECISION_LABEL, "decision_at": datetime.now(JST).isoformat(),
            "selector_version": "v22_realtime_decision_engine_pg_dynamic_odds_v2", "selector_mode": SELECTOR_MODE,
            "mode_name": mode_name, "mode_label": cand.get("mode_label"), "ticket": ticket,
            "odds": judge["odds"], "prob": cand.get("prob"), "prob_rank": cand.get("prob_rank"),
            "market_rank": judge["market_rank"], "raw_ev": cand.get("raw_ev"), "base_score": cand.get("priority"),
            "realtime_score": judge["realtime_score"],
            "final_score": round(_safe_float(cand.get("priority"), 0.0) + _safe_float(judge["realtime_score"], 0.0), 4),
            "recommendation": judge["recommendation"], "skip_reason": judge["skip_reason"],
            "positive_reasons": judge["positive_reasons"], "negative_reasons": judge["negative_reasons"],
            "stake_yen": UNIT_YEN, "expected_return_yen": int(round(judge["odds"] * UNIT_YEN)) if judge["odds"] else None,
            "was_notified": False,
            "raw": {"candidate": cand, "snapshot_label": SNAPSHOT_LABEL, "exhibition_rows": len(exh_by.get(rid, [])), "weather_exists": bool(weather_by.get(rid)), "rt_odds_exists": bool(rt_odds_by.get(rid, {}).get(ticket)), "rt_entry_rows": len(rt_entry_by.get(rid, []))},
        }
        decision_rows.append(row)
        printable.append({**cand, **judge})

    saved = _save_decisions(decision_rows) if SAVE_DECISIONS else 0
    buy = [r for r in printable if r["recommendation"] == "buy"]
    watch = [r for r in printable if r["recommendation"] == "watch"]
    skip = [r for r in printable if r["recommendation"] == "skip"]
    buy.sort(key=lambda r: (r.get("mode_rank", 0), r.get("realtime_score", 0), r.get("priority", 0)), reverse=True)
    watch.sort(key=lambda r: (r.get("mode_rank", 0), r.get("realtime_score", 0), r.get("priority", 0)), reverse=True)

    print("\n=== v22 PG decision summary ===", flush=True)
    print(f"candidate_rows={len(candidate_rows)} ready_races={ready_races} skipped_not_ready={skipped_not_ready} skipped_entries={skipped_entries} skipped_odds={skipped_odds}", flush=True)
    print(f"low_core_total={low_core_total} mode_extra_match_races={mode_extra_match_races}", flush=True)
    print(f"decisions_saved={saved}", flush=True)
    print(f"BUY={len(buy)} WATCH={len(watch)} SKIP={len(skip)}", flush=True)

    print("\n--- BUY候補 ---", flush=True)
    for i, r in enumerate(buy[:DAILY_MAX_POINTS], 1):
        print(f"{i:02d}. {r['race_id']} {r['venue_id']}場 {r['race_no']}R {r['ticket']} odds={r['odds']:.1f} mode={r['mode_label']} score={r['realtime_score']} prob_rank={r['prob_rank']} market_rank={r['market_rank']} reasons={';'.join(r['positive_reasons'][:4])}", flush=True)
        if r.get("negative_reasons"):
            print(f"    caution: {';'.join(r['negative_reasons'][:4])}", flush=True)
        if r.get("race_title"):
            print(f"    title: {r['race_title']}", flush=True)

    print("\n--- WATCH候補 ---", flush=True)
    for i, r in enumerate(watch[:10], 1):
        print(f"{i:02d}. {r['race_id']} {r['venue_id']}場 {r['race_no']}R {r['ticket']} odds={r['odds']:.1f} mode={r['mode_label']} score={r['realtime_score']} neg={';'.join(r['negative_reasons'][:3])}", flush=True)

    print("\n--- 主なSKIP理由 ---", flush=True)
    counts: Dict[str, int] = {}
    for r in skip:
        reason = r.get("skip_reason") or (r.get("negative_reasons", ["score_negative"])[0] if r.get("negative_reasons") else "score_negative")
        counts[reason] = counts.get(reason, 0) + 1
    for reason, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"{reason}: {cnt}", flush=True)
    print("=== v22 PG 直前判定エンジン終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise