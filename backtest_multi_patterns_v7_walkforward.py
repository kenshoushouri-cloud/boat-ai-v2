# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v7_walkforward.py

競艇AI v2用・walk-forward校正型バックテスト。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python backtest_multi_patterns_v7_walkforward.py

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
    # 初期期間は校正用に使い、購入しない。
    "burn_in_days": 45,
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
        select="race_id,lane,racer_number,racer_class,national_win_rate,national_quinella_rate,local_quinella_rate,motor_quinella_rate,boat_quinella_rate,avg_st",
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
    nat2 = _safe_float(entry.get("national_quinella_rate"), 32.0)
    loc2 = _safe_float(entry.get("local_quinella_rate"), 30.0)
    mot2 = _safe_float(entry.get("motor_quinella_rate"), 33.0)
    boat2 = _safe_float(entry.get("boat_quinella_rate"), 34.0)
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
# Walk-forward calibration
# ============================================================

def _rank_bin(rank: int) -> str:
    if rank <= 1: return "01"
    if rank <= 2: return "02"
    if rank <= 3: return "03"
    if rank <= 5: return "04_05"
    if rank <= 10: return "06_10"
    if rank <= 20: return "11_20"
    if rank <= 40: return "21_40"
    return "41_120"


def _market_bin(rank: int) -> str:
    if rank <= 3: return "m01_03"
    if rank <= 5: return "m04_05"
    if rank <= 10: return "m06_10"
    if rank <= 20: return "m11_20"
    if rank <= 40: return "m21_40"
    return "m41_120"


def _odds_bin(odds: float) -> str:
    if odds < 3: return "o001_003"
    if odds < 5: return "o003_005"
    if odds < 10: return "o005_010"
    if odds < 20: return "o010_020"
    if odds < 50: return "o020_050"
    if odds < 100: return "o050_100"
    if odds < 200: return "o100_200"
    if odds < 500: return "o200_500"
    return "o500_plus"


def _race_no_group(race_no: int) -> str:
    if race_no <= 4: return "r01_04"
    if race_no <= 8: return "r05_08"
    return "r09_12"


def _head_lane(ticket: str) -> str:
    return ticket.split("-")[0] if ticket else ""


@dataclass
class BinAgg:
    n: int = 0
    hits: int = 0
    stake: int = 0
    payout: int = 0
    clipped_payout: int = 0

    def update(self, hit: bool, payout_yen: int) -> None:
        self.n += 1
        self.stake += UNIT_YEN
        if hit:
            self.hits += 1
            self.payout += payout_yen
            self.clipped_payout += min(payout_yen, CALIB_PAYOUT_CLIP_YEN)

    @property
    def hit_rate(self) -> float:
        # conservative smoothing: 1 pseudo-hit over 120 pseudo-candidates.
        return (self.hits + 1.0) / (self.n + 120.0) if self.n > 0 else 0.0

    @property
    def roi(self) -> float:
        return self.payout / self.stake * 100.0 if self.stake else 0.0

    @property
    def clipped_roi(self) -> float:
        return self.clipped_payout / self.stake * 100.0 if self.stake else 0.0


class WalkForwardCalibrator:
    def __init__(self) -> None:
        self.bins: Dict[Tuple[Any, ...], BinAgg] = {}

    def _keys(self, row: Dict[str, Any], venue_id: str, race_no: int) -> List[Tuple[Any, ...]]:
        pr = _rank_bin(_safe_int(row.get("prob_rank"), 999))
        er = _rank_bin(_safe_int(row.get("ev_rank"), 999))
        mr = _market_bin(_safe_int(row.get("market_rank"), 999))
        ob = _odds_bin(_safe_float(row.get("odds"), 0.0))
        rg = _race_no_group(race_no)
        head = _head_lane(str(row.get("ticket", "")))
        return [
            ("venue", venue_id, rg, pr, mr, ob),
            ("venue_head", venue_id, rg, head, pr, ob),
            ("race", rg, pr, mr, ob),
            ("head", head, pr, mr, ob),
            ("rank_odds", pr, mr, ob),
            ("prob_odds", pr, ob),
            ("ev_odds", er, ob),
            ("prob", pr),
        ]

    def update_candidate(self, row: Dict[str, Any], venue_id: str, race_no: int, actual_ticket: str, payout_yen: int) -> None:
        hit = row.get("ticket") == actual_ticket
        for k in self._keys(row, venue_id, race_no):
            self.bins.setdefault(k, BinAgg()).update(hit, payout_yen if hit else 0)

    def profile(self, row: Dict[str, Any], venue_id: str, race_no: int, min_samples: int, use_clipped: bool) -> Optional[Dict[str, Any]]:
        # Prefer more specific bins when sample is enough, fallback to broad bins.
        for k in self._keys(row, venue_id, race_no):
            agg = self.bins.get(k)
            if not agg or agg.n < min_samples:
                continue
            odds = _safe_float(row.get("odds"), 0.0)
            hit_rate = agg.hit_rate
            calib_ev = hit_rate * odds
            return {
                "key": k,
                "samples": agg.n,
                "hits": agg.hits,
                "hist_hit_rate": hit_rate,
                "hist_roi": agg.roi,
                "hist_clip_roi": agg.clipped_roi,
                "calib_ev": calib_ev,
                "use_roi": agg.clipped_roi if use_clipped else agg.roi,
            }
        return None


@dataclass
class WFStrategy:
    name: str
    description: str
    max_points: int = 1
    min_samples: int = 200
    min_calib_ev: float = 1.05
    min_hist_roi: float = 100.0
    min_odds: float = 1.0
    max_odds: float = 9999.0
    use_clipped_roi: bool = True
    seed_only: bool = False
    exclude_venues: Tuple[str, ...] = ()
    lane1_classes: Optional[Tuple[int, ...]] = None
    require_head1: Optional[bool] = None
    score_mode: str = "calib_ev"  # calib_ev / roi_ev / prob_blend


WF_STRATEGIES: List[WFStrategy] = [
    WFStrategy("wf_calib_1pt", "WF校正EV・全場1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, use_clipped_roi=True),
    WFStrategy("wf_calib_2pt", "WF校正EV・全場2点", max_points=2, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, use_clipped_roi=True),
    WFStrategy("wf_calib_5_200_1pt", "WF校正EV・5〜200倍1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, min_odds=5, max_odds=200, use_clipped_roi=True),
    WFStrategy("wf_calib_5_200_2pt", "WF校正EV・5〜200倍2点", max_points=2, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, min_odds=5, max_odds=200, use_clipped_roi=True),
    WFStrategy("wf_calib_5_100_1pt", "WF校正EV・5〜100倍1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, min_odds=5, max_odds=100, use_clipped_roi=True),
    WFStrategy("wf_calib_10_200_1pt", "WF校正EV・10〜200倍1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, min_odds=10, max_odds=200, use_clipped_roi=True),
    WFStrategy("wf_conservative_5_200_1pt", "WF保守・5〜200倍1点", max_points=1, min_samples=500, min_calib_ev=1.10, min_hist_roi=105, min_odds=5, max_odds=200, use_clipped_roi=True),
    WFStrategy("wf_conservative_5_200_2pt", "WF保守・5〜200倍2点", max_points=2, min_samples=500, min_calib_ev=1.10, min_hist_roi=105, min_odds=5, max_odds=200, use_clipped_roi=True),
    WFStrategy("wf_no_bad5_1pt", "WF校正EV・低調5場除外1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, exclude_venues=BAD_VENUES, use_clipped_roi=True),
    WFStrategy("wf_no_bad5_2pt", "WF校正EV・低調5場除外2点", max_points=2, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, exclude_venues=BAD_VENUES, use_clipped_roi=True),
    WFStrategy("wf_seed_1pt", "WF校正EV・シード限定1点", max_points=1, min_samples=150, min_calib_ev=1.05, min_hist_roi=100, seed_only=True, use_clipped_roi=True),
    WFStrategy("wf_head1_1pt", "WF校正EV・1頭限定1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, require_head1=True, use_clipped_roi=True),
    WFStrategy("wf_non_head1_1pt", "WF校正EV・1頭以外1点", max_points=1, min_samples=200, min_calib_ev=1.05, min_hist_roi=100, require_head1=False, use_clipped_roi=True),
]

# ============================================================
# Records / Stats
# ============================================================

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
        profit = payout - stake
        self.adopted_races += 1
        self.total_points += points
        self.total_stake_yen += stake
        self.total_payout_yen += payout
        self.profit_yen += profit
        if hit:
            self.hit_races += 1
            self._cur_losing_streak = 0
        else:
            self._cur_losing_streak += 1
            self.max_losing_streak = max(self.max_losing_streak, self._cur_losing_streak)

    def summary_row(self) -> Dict[str, Any]:
        roi = self.total_payout_yen / self.total_stake_yen * 100.0 if self.total_stake_yen else 0.0
        hit_rate = self.hit_races / self.adopted_races * 100.0 if self.adopted_races else 0.0
        return {
            "strategy": self.name,
            "description": self.description,
            "eligible_before_budget": self.eligible_before_budget,
            "adopted_races": self.adopted_races,
            "hit_races": self.hit_races,
            "hit_rate": round(hit_rate, 2),
            "total_points": self.total_points,
            "total_stake_yen": self.total_stake_yen,
            "total_payout_yen": self.total_payout_yen,
            "profit_yen": self.profit_yen,
            "roi": round(roi, 2),
            "max_losing_streak": self.max_losing_streak,
        }


def _focus_record_from_rc(rc: RaceCandidate) -> Dict[str, Any]:
    points = len(rc.bets)
    stake = points * UNIT_YEN
    payout = 0
    hit = 0
    hit_odds = 0.0
    for b in rc.bets:
        if b["ticket"] == rc.actual_ticket:
            payout = int(rc.actual_payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
            hit = 1
            hit_odds = _safe_float(b.get("odds"), 0.0)
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
        "hit_odds": hit_odds,
        "actual_ticket": rc.actual_ticket,
        "actual_payout_yen": rc.actual_payout_yen,
        "bet_tickets": "|".join(str(b.get("ticket", "")) for b in rc.bets),
        "bet_odds": "|".join(str(round(_safe_float(b.get("odds"), 0.0), 1)) for b in rc.bets),
        "bet_calib_ev": "|".join(str(round(_safe_float(b.get("calib_ev"), 0.0), 3)) for b in rc.bets),
        "bet_hist_roi": "|".join(str(round(_safe_float(b.get("hist_roi"), 0.0), 1)) for b in rc.bets),
        "bet_hist_clip_roi": "|".join(str(round(_safe_float(b.get("hist_clip_roi"), 0.0), 1)) for b in rc.bets),
        "bet_samples": "|".join(str(_safe_int(b.get("samples"), 0)) for b in rc.bets),
        "is_seed": 1 if rc.is_seed else 0,
    }

# ============================================================
# Selection
# ============================================================

def _select_wf_bets(
    candidates: List[Dict[str, Any]],
    strategy: WFStrategy,
    calibrator: WalkForwardCalibrator,
    venue_id: str,
    race_no: int,
    is_seed: bool,
    lane1_class: int,
    day_index: int,
) -> List[Dict[str, Any]]:
    if day_index <= BURN_IN_DAYS:
        return []
    if strategy.exclude_venues and venue_id in strategy.exclude_venues:
        return []
    if strategy.seed_only and not is_seed:
        return []
    if strategy.lane1_classes is not None and lane1_class not in strategy.lane1_classes:
        return []

    rows: List[Dict[str, Any]] = []
    for c in candidates:
        odds = _safe_float(c.get("odds"), 0.0)
        if odds < strategy.min_odds or odds > strategy.max_odds:
            continue
        head_is_1 = str(c.get("ticket", "")).startswith("1-")
        if strategy.require_head1 is True and not head_is_1:
            continue
        if strategy.require_head1 is False and head_is_1:
            continue
        prof = calibrator.profile(c, venue_id, race_no, strategy.min_samples, strategy.use_clipped_roi)
        if not prof:
            continue
        if prof["calib_ev"] < strategy.min_calib_ev:
            continue
        if prof["use_roi"] < strategy.min_hist_roi:
            continue
        row = dict(c)
        row.update(prof)
        # score: current oddsに校正hit率を掛けたEVを中心に、サンプル数で少し補正。
        score = prof["calib_ev"] * math.log1p(prof["samples"])
        row["wf_score"] = score
        row["label"] = "main"
        rows.append(row)

    rows.sort(key=lambda x: (x["wf_score"], x["calib_ev"], x["use_roi"], x["prob"]), reverse=True)
    return rows[:strategy.max_points]


def _apply_daily_budget(candidates: List[RaceCandidate], fair_budget: bool = FAIR_BUDGET) -> List[RaceCandidate]:
    if not candidates:
        return []
    if fair_budget:
        candidates = candidates[:]
        candidates.sort(key=lambda x: (x.race_date, x.venue_id, x.race_no, -x.priority))
    else:
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

# ============================================================
# Summaries
# ============================================================

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
        "roi": round(payout / stake * 100.0, 2) if stake else 0.0,
        "hits": hits,
        "hit_rate": round(hits / races * 100.0, 2) if races else 0.0,
        "max_losing_streak": max_losing,
    }


def _month_excluded_records(records: List[Dict[str, Any]], months: List[str]) -> List[Dict[str, Any]]:
    mset = set(months)
    return [r for r in records if str(r.get("month")) not in mset]


def _top_hit_excluded_records(records: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    if n <= 0:
        return records
    hits = [r for r in records if r.get("hit") == 1]
    hits.sort(key=lambda x: _safe_int(x.get("payout_yen"), 0), reverse=True)
    remove = {(r.get("race_id"), r.get("actual_ticket"), r.get("payout_yen")) for r in hits[:n]}
    return [r for r in records if (r.get("race_id"), r.get("actual_ticket"), r.get("payout_yen")) not in remove]


def _print_focus_line(name: str, records: List[Dict[str, Any]]) -> None:
    all_row = _summarize_records(records, "all")
    no_2605 = _summarize_records(_month_excluded_records(records, ["2026-05"]), "ex26-05")
    no_2505 = _summarize_records(_month_excluded_records(records, ["2025-05"]), "ex25-05")
    no_both = _summarize_records(_month_excluded_records(records, FOCUS_EXCLUDE_MONTHS), "exBoth")
    no_top1 = _summarize_records(_top_hit_excluded_records(records, 1), "exTop1")
    no_top3 = _summarize_records(_top_hit_excluded_records(records, 3), "exTop3")
    print(
        f"FOCUS {name:<30} "
        f"allROI={all_row['roi']:>6.1f}% profit={all_row['profit']:>+8,} "
        f"ex26-05={no_2605['roi']:>6.1f}% ex25-05={no_2505['roi']:>6.1f}% "
        f"exBoth={no_both['roi']:>6.1f}% exTop1={no_top1['roi']:>6.1f}% exTop3={no_top3['roi']:>6.1f}% "
        f"maxLose={all_row['max_losing_streak']:>3}",
        flush=True,
    )

# ============================================================
# Main
# ============================================================

def main() -> None:
    _require_settings()
    print("✅ backtest_multi_patterns_v7_walkforward.py VERSION 2026-06-22 walk-forward-calibration", flush=True)
    print("=== walk-forward校正型バックテスト開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"daily_budget={DAILY_BUDGET_YEN}円 unit={UNIT_YEN}円 burn_in_days={BURN_IN_DAYS}", flush=True)
    print(f"calib_clip={CALIB_PAYOUT_CLIP_YEN}円 bad_venues={','.join(BAD_VENUES)}", flush=True)

    stats: Dict[str, StrategyStats] = {s.name: StrategyStats(s.name, s.description) for s in WF_STRATEGIES}
    focus_records: Dict[str, List[Dict[str, Any]]] = {s.name: [] for s in WF_STRATEGIES}
    calibrator = WalkForwardCalibrator()

    total_ready = 0
    total_races_seen = 0
    total_seed_ready = 0
    month_stats: Dict[str, Dict[str, int]] = {}
    dates = list(_daterange(START_DATE, END_DATE))

    for idx, race_date in enumerate(dates, start=1):
        t0 = time.time()
        races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)
        total_races_seen += len(races)

        ready_today = 0
        seed_today = 0
        day_candidates_by_strategy: Dict[str, List[RaceCandidate]] = {s.name: [] for s in WF_STRATEGIES}
        day_update_rows: List[Tuple[List[Dict[str, Any]], str, int, str, int]] = []

        for r in races:
            rid = r.get("race_id")
            venue_id = str(r.get("venue_id", "")).zfill(2)
            race_no = _safe_int(r.get("race_no"), 0)
            result = results.get(rid)
            entries = entries_by_race.get(rid, [])
            odds = odds_by_race.get(rid, {})
            if not _is_backtest_ready(result, entries, odds):
                continue

            ready_today += 1
            is_seed = _is_seed_race(entries)
            if is_seed:
                seed_today += 1
            by_lane = _entry_by_lane(entries)
            lane1_class = _safe_int(by_lane.get(1, {}).get("racer_class"), 0)
            actual_ticket = _get_actual_ticket(result)
            actual_payout = _safe_int(result.get("trifecta_payout_yen"), 0)
            candidates = _rank_candidates(entries, venue_id, odds)
            if not candidates:
                continue

            for st in WF_STRATEGIES:
                bets = _select_wf_bets(candidates, st, calibrator, venue_id, race_no, is_seed, lane1_class, idx)
                if not bets:
                    continue
                stats[st.name].add_eligible_before_budget()
                priority = max((_safe_float(b.get("wf_score"), 0.0) for b in bets), default=0.0)
                day_candidates_by_strategy[st.name].append(
                    RaceCandidate(rid, race_date, venue_id, race_no, st.name, bets, actual_ticket, actual_payout, is_seed, priority)
                )

            # update is delayed until day end to avoid same-day leakage.
            day_update_rows.append((candidates, venue_id, race_no, actual_ticket, actual_payout))

        # Apply daily budget strategy by strategy.
        adopted_total = 0
        for st in WF_STRATEGIES:
            selected = _apply_daily_budget(day_candidates_by_strategy[st.name])
            for rc in selected:
                stats[st.name].adopt(rc)
                focus_records[st.name].append(_focus_record_from_rc(rc))
            adopted_total += len(selected)

        # Now update calibrator with the whole day.
        for candidates, venue_id, race_no, actual_ticket, actual_payout in day_update_rows:
            for c in candidates:
                calibrator.update_candidate(c, venue_id, race_no, actual_ticket, actual_payout)

        total_ready += ready_today
        total_seed_ready += seed_today
        mk = race_date[:7]
        ms = month_stats.setdefault(mk, {"races": 0, "ready": 0, "seed": 0})
        ms["races"] += len(races)
        ms["ready"] += ready_today
        ms["seed"] += seed_today

        should_log = idx == 1 or idx == len(dates) or (LOG_EVERY_DAYS > 0 and idx % LOG_EVERY_DAYS == 0)
        if should_log:
            print(
                f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={ready_today} seed={seed_today} "
                f"adopted_total={adopted_total} bins={len(calibrator.bins)} elapsed={time.time()-t0:.1f}s",
                flush=True,
            )
        if DAY_SLEEP > 0 and idx < len(dates):
            time.sleep(DAY_SLEEP)

    print("\n" + "=" * 88, flush=True)
    print("v7 walk-forward バックテスト最終結果", flush=True)
    print("=" * 88, flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"読み込みレース数: {total_races_seen}", flush=True)
    print(f"backtest_ready: {total_ready}", flush=True)
    print(f"seed_ready: {total_seed_ready}", flush=True)
    print(f"日次上限: {DAILY_BUDGET_YEN}円 / burn_in_days={BURN_IN_DAYS}", flush=True)

    print("\n--- 月別 ready / seed ---", flush=True)
    for m in sorted(month_stats):
        ms = month_stats[m]
        print(f"{m} races={ms['races']:>5} ready={ms['ready']:>5} seed={ms['seed']:>4}", flush=True)

    rows = [stats[s.name].summary_row() for s in WF_STRATEGIES]
    rows.sort(key=lambda x: (x["roi"], x["profit_yen"]), reverse=True)
    print(f"\n--- v7戦略別サマリー ROI順 Top {SUMMARY_TOP_N} ---", flush=True)
    for r in rows[:SUMMARY_TOP_N]:
        print(
            f"{r['strategy']:<30} 採用{r['adopted_races']:>5}R/{r['total_points']:>5}点 "
            f"的中{r['hit_races']:>4}R({r['hit_rate']:>5.1f}%) "
            f"投資{r['total_stake_yen']:>9,}円 回収{r['total_payout_yen']:>9,}円 "
            f"損益{r['profit_yen']:>+9,}円 ROI{r['roi']:>6.1f}% "
            f"最大連敗{r['max_losing_streak']:>3} 予算前eligible{r['eligible_before_budget']:>5}",
            flush=True,
        )

    print("\n--- v7 FOCUS耐久チェック ---", flush=True)
    for r in rows[:SUMMARY_TOP_N]:
        name = r["strategy"]
        _print_focus_line(name, focus_records.get(name, []))

    print("=== v7 walk-forward バックテスト終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        raise