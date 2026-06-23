# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v9_pocket_strategy.py

競艇AI v2用・v8で見つかったポケット条件の実買いバックテスト。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python backtest_multi_patterns_v9_pocket_strategy.py

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



# ============================================================
# v9 Pocket strategy backtest
# ============================================================

def _head_lane(ticket: str) -> str:
    s = _norm_ticket(ticket)
    if not s:
        return "?"
    return s.split("-")[0]


@dataclass
class PocketStrategy:
    name: str
    description: str
    prob_min: int
    prob_max: int
    market_min: int
    market_max: int
    min_odds: float
    max_odds: float
    max_points_per_race: int = 1
    exclude_venues: Tuple[str, ...] = ()
    only_venues: Tuple[str, ...] = ()
    require_head: Optional[str] = None
    priority_mode: str = "prob"  # prob / odds / ev / mid_first
    include_low_stable: bool = False


POCKET_STRATEGIES: List[PocketStrategy] = [
    PocketStrategy(
        "pocket_mid_30_50_1pt",
        "v8本命候補: prob4-5 × market21-30 × odds30-50 1点",
        4, 5, 21, 30, 30.0, 50.0, 1, priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_2pt",
        "v8本命候補: prob4-5 × market21-30 × odds30-50 最大2点",
        4, 5, 21, 30, 30.0, 50.0, 2, priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_ev1pt",
        "prob4-5 × market21-30 × odds30-50 rawEV優先1点",
        4, 5, 21, 30, 30.0, 50.0, 1, priority_mode="ev",
    ),
    PocketStrategy(
        "pocket_mid_30_50_odds1pt",
        "prob4-5 × market21-30 × odds30-50 高オッズ優先1点",
        4, 5, 21, 30, 30.0, 50.0, 1, priority_mode="odds",
    ),
    PocketStrategy(
        "pocket_mid_30_50_no_bad5_1pt",
        "prob4-5 × market21-30 × odds30-50 低調5場除外1点",
        4, 5, 21, 30, 30.0, 50.0, 1, exclude_venues=BAD_VENUES, priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_no_bad5_2pt",
        "prob4-5 × market21-30 × odds30-50 低調5場除外最大2点",
        4, 5, 21, 30, 30.0, 50.0, 2, exclude_venues=BAD_VENUES, priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_head1_1pt",
        "prob4-5 × market21-30 × odds30-50 1頭だけ1点",
        4, 5, 21, 30, 30.0, 50.0, 1, require_head="1", priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_non_head1_1pt",
        "prob4-5 × market21-30 × odds30-50 1頭以外1点",
        4, 5, 21, 30, 30.0, 50.0, 1, require_head="non1", priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_mid_30_50_venue_subset_1pt",
        "v8で中穴候補が出た場だけ: 03,06,09,17,19,20,22",
        4, 5, 21, 30, 30.0, 50.0, 1,
        only_venues=("03", "06", "09", "17", "19", "20", "22"),
        priority_mode="prob",
    ),
    PocketStrategy(
        "pocket_low_stable_1pt",
        "低オッズ安定候補: prob11-20 × market1 × odds3-5 1点",
        11, 20, 1, 1, 3.0, 5.0, 1, priority_mode="prob",
    ),
    PocketStrategy(
        "combo_mid_plus_low_1pt_each",
        "中穴候補 + 低オッズ安定候補、各1点まで",
        4, 5, 21, 30, 30.0, 50.0, 1, priority_mode="mid_first", include_low_stable=True,
    ),
]


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


def _match_base_pocket(row: Dict[str, Any], st: PocketStrategy, venue_id: str) -> bool:
    if st.exclude_venues and venue_id in st.exclude_venues:
        return False
    if st.only_venues and venue_id not in st.only_venues:
        return False
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)
    if not (st.prob_min <= pr <= st.prob_max):
        return False
    if not (st.market_min <= mr <= st.market_max):
        return False
    if not (st.min_odds <= odds < st.max_odds):
        return False
    head = _head_lane(str(row.get("ticket", "")))
    if st.require_head == "1" and head != "1":
        return False
    if st.require_head == "non1" and head == "1":
        return False
    return True


def _match_low_stable(row: Dict[str, Any]) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)
    return 11 <= pr <= 20 and mr == 1 and 3.0 <= odds < 5.0


def _candidate_priority(row: Dict[str, Any], mode: str, label: str = "") -> float:
    prob = _safe_float(row.get("prob"), 0.0)
    odds = _safe_float(row.get("odds"), 0.0)
    ev = _safe_float(row.get("raw_ev"), 0.0)
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)

    if mode == "odds":
        return odds + prob * 100.0
    if mode == "ev":
        return ev * 10000.0 + prob * 100.0
    if mode == "mid_first":
        base = 100000.0 if label == "mid" else 0.0
        return base + ev * 10000.0 + prob * 100.0 - pr * 0.01 - mr * 0.001
    return prob * 10000.0 + ev * 100.0 - pr * 0.01 - mr * 0.001


def _select_strategy_bets(rows: List[Dict[str, Any]], st: PocketStrategy, venue_id: str) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []

    mid_rows = []
    for r in rows:
        if _match_base_pocket(r, st, venue_id):
            x = dict(r)
            x["label"] = "mid"
            x["select_priority"] = _candidate_priority(x, st.priority_mode, "mid")
            mid_rows.append(x)
    mid_rows.sort(key=lambda x: x["select_priority"], reverse=True)
    selected.extend(mid_rows[:st.max_points_per_race])

    if st.include_low_stable:
        low_rows = []
        existing = {x["ticket"] for x in selected}
        for r in rows:
            if r.get("ticket") in existing:
                continue
            if _match_low_stable(r):
                x = dict(r)
                x["label"] = "low"
                x["select_priority"] = _candidate_priority(x, st.priority_mode, "low")
                low_rows.append(x)
        low_rows.sort(key=lambda x: x["select_priority"], reverse=True)
        selected.extend(low_rows[:1])

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
    for b in rc.bets:
        if b["ticket"] == rc.actual_ticket:
            payout = int(rc.actual_payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
            hit = 1
            break
    return {
        "strategy": rc.strategy,
        "race_id": rc.race_id,
        "race_date": rc.race_date,
        "month": rc.race_date[:7],
        "venue_id": rc.venue_id,
        "race_no": rc.race_no,
        "points": points,
        "stake_yen": stake,
        "payout_yen": payout,
        "profit_yen": payout - stake,
        "hit": hit,
        "actual_ticket": rc.actual_ticket,
        "actual_payout_yen": rc.actual_payout_yen,
        "bet_tickets": "|".join(str(b.get("ticket", "")) for b in rc.bets),
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
        f"{row['strategy'][:32]:32s} "
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
        f"FOCUS {strategy[:32]:32s} "
        f"allROI={all_row['roi']:6.1f}% profit={all_row['profit']:>+9,} "
        f"ex25={ex25['roi']:6.1f}% ex26={ex26['roi']:6.1f}% "
        f"both={both['roi']:6.1f}% top1={top1['roi']:6.1f}% top3={top3['roi']:6.1f}% "
        f"maxLose={all_row['max_losing']:4d}",
        flush=True,
    )

    # 月別も上位候補だけ簡易表示
    by_month: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        by_month.setdefault(str(r.get("month")), []).append(r)
    month_lines = []
    for mm in sorted(by_month):
        m = _summarize_records(by_month[mm], mm)
        month_lines.append(f"{mm}:{m['roi']:.0f}%/{m['profit']:+,}")
    print("  monthly " + " ".join(month_lines), flush=True)


def main() -> None:
    _require_settings()
    print("✅ backtest_multi_patterns_v9_pocket_strategy.py VERSION 2026-06-23 pocket-realbet", flush=True)
    print("=== v9 ポケット実買いバックテスト開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"daily_budget={DAILY_BUDGET_YEN}円 unit={UNIT_YEN}円 max_points={DAILY_MAX_POINTS}", flush=True)
    print("target pocket: prob_rank4-5 × market_rank21-30 × odds30-50", flush=True)

    stats: Dict[str, StrategyStats] = {s.name: StrategyStats(s.name, s.description) for s in POCKET_STRATEGIES}
    records_by_strategy: Dict[str, List[Dict[str, Any]]] = {s.name: [] for s in POCKET_STRATEGIES}
    monthly: Dict[str, Dict[str, int]] = {}

    total_races = 0
    ready_races = 0
    seed_ready = 0

    dates = list(_daterange(START_DATE, END_DATE))
    for idx, race_date in enumerate(dates, start=1):
        t0 = time.time()
        races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)
        day_candidates: Dict[str, List[RaceCandidate]] = {s.name: [] for s in POCKET_STRATEGIES}
        day_ready = 0
        day_seed = 0

        for race in races:
            total_races += 1
            rid = race.get("race_id")
            venue_id = str(race.get("venue_id", "")).zfill(2)
            race_no = _safe_int(race.get("race_no"), 0)
            result = results.get(rid)
            entries = entries_by_race.get(rid, [])
            odds = odds_by_race.get(rid, {})

            if not _is_backtest_ready(result, entries, odds):
                continue

            actual = _get_actual_ticket(result)
            payout_yen = _safe_int(result.get("trifecta_payout_yen"), 0)
            is_seed = _is_seed_race(entries, STRICT_SEED)
            by_lane = _entry_by_lane(entries)
            lane1_class = _safe_int(by_lane.get(1, {}).get("racer_class"), 0)

            ready_races += 1
            day_ready += 1
            if is_seed:
                seed_ready += 1
                day_seed += 1

            ranked_rows = _rank_candidates(entries, venue_id, odds)

            for st in POCKET_STRATEGIES:
                bets = _select_strategy_bets(ranked_rows, st, venue_id)
                if not bets:
                    continue
                stats[st.name].add_eligible_before_budget()
                priority = max(_safe_float(b.get("select_priority"), 0.0) for b in bets)
                rc = RaceCandidate(
                    race_id=str(rid),
                    race_date=str(race_date),
                    venue_id=venue_id,
                    race_no=race_no,
                    strategy=st.name,
                    bets=bets,
                    actual_ticket=actual,
                    actual_payout_yen=payout_yen,
                    is_seed=is_seed,
                    priority=priority,
                )
                day_candidates[st.name].append(rc)

        for st in POCKET_STRATEGIES:
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
            adopted = sum(len(day_candidates[s.name]) for s in POCKET_STRATEGIES)
            print(
                f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={day_ready} seed={day_seed} "
                f"eligible_candidates={adopted} elapsed={time.time()-t0:.1f}s",
                flush=True,
            )
        if DAY_SLEEP > 0:
            time.sleep(DAY_SLEEP)

    print("\n" + "=" * 88, flush=True)
    print("v9 ポケット実買いバックテスト最終結果", flush=True)
    print("=" * 88, flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"読み込みレース数: {total_races}", flush=True)
    print(f"backtest_ready: {ready_races}", flush=True)
    print(f"seed_ready: {seed_ready}", flush=True)
    print(f"日次上限: {DAILY_BUDGET_YEN}円", flush=True)

    print("--- 月別 ready / seed ---", flush=True)
    for mm in sorted(monthly):
        m = monthly[mm]
        print(f"{mm} races={m['races']:5d} ready={m['ready']:5d} seed={m['seed']:4d}", flush=True)

    print("--- v9戦略別サマリー ROI順 ---", flush=True)
    rows = [stats[s.name].row() for s in POCKET_STRATEGIES]
    rows.sort(key=lambda r: r["roi"], reverse=True)
    for r in rows:
        _print_total_row(r)

    print("--- v9 FOCUS耐久チェック ---", flush=True)
    for r in rows:
        _print_focus(r["strategy"], records_by_strategy.get(r["strategy"], []))

    print("=== v9 ポケット実買いバックテスト終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise