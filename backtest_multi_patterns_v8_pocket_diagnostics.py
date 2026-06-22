# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v8_pocket_diagnostics.py

競艇AI v2用・買える条件を探すポケット診断スクリプト。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python backtest_multi_patterns_v8_pocket_diagnostics.py

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
    "summary_top_n": 30,
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
# v8 Pocket diagnostics
# ============================================================

@dataclass
class PocketAgg:
    name: str
    n: int = 0
    hits: int = 0
    stake: int = 0
    payout: int = 0
    by_month: Dict[str, Dict[str, int]] = field(default_factory=dict)
    top_hit_payouts: List[int] = field(default_factory=list)
    cur_losing_streak: int = 0
    max_losing_streak: int = 0

    def update(self, race_date: str, hit: bool, payout_yen: int) -> None:
        self.n += 1
        self.stake += UNIT_YEN

        month = str(race_date)[:7]
        m = self.by_month.setdefault(month, {"n": 0, "hits": 0, "stake": 0, "payout": 0})
        m["n"] += 1
        m["stake"] += UNIT_YEN

        if hit:
            pay = int(payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
            self.hits += 1
            self.payout += pay
            m["hits"] += 1
            m["payout"] += pay
            self.top_hit_payouts.append(pay)
            self.top_hit_payouts.sort(reverse=True)
            if len(self.top_hit_payouts) > 5:
                self.top_hit_payouts = self.top_hit_payouts[:5]
            self.cur_losing_streak = 0
        else:
            self.cur_losing_streak += 1
            self.max_losing_streak = max(self.max_losing_streak, self.cur_losing_streak)

    def roi(self) -> float:
        return self.payout / self.stake * 100.0 if self.stake else 0.0

    def profit(self) -> int:
        return self.payout - self.stake

    def ex_month_roi(self, months: Tuple[str, ...]) -> float:
        stake = self.stake
        payout = self.payout
        for mm in months:
            m = self.by_month.get(mm)
            if m:
                stake -= m["stake"]
                payout -= m["payout"]
        return payout / stake * 100.0 if stake > 0 else 0.0

    def ex_top_roi(self, k: int) -> float:
        k = min(k, len(self.top_hit_payouts))
        stake = self.stake - k * UNIT_YEN
        payout = self.payout - sum(self.top_hit_payouts[:k])
        return payout / stake * 100.0 if stake > 0 else 0.0

    def row(self) -> Dict[str, Any]:
        ex25 = self.ex_month_roi(("2025-05",))
        ex26 = self.ex_month_roi(("2026-05",))
        exboth = self.ex_month_roi(("2025-05", "2026-05"))
        extop1 = self.ex_top_roi(1)
        extop3 = self.ex_top_roi(3)
        robust = min(self.roi(), ex25, ex26, exboth, extop1)
        return {
            "name": self.name,
            "n": self.n,
            "hits": self.hits,
            "hit_rate": self.hits / self.n * 100.0 if self.n else 0.0,
            "stake": self.stake,
            "payout": self.payout,
            "profit": self.profit(),
            "roi": self.roi(),
            "ex25": ex25,
            "ex26": ex26,
            "exboth": exboth,
            "extop1": extop1,
            "extop3": extop3,
            "robust": robust,
            "maxlose": self.max_losing_streak,
            "top1pay": self.top_hit_payouts[0] if self.top_hit_payouts else 0,
        }


def _pocket_update(pockets: Dict[str, PocketAgg], key: str, race_date: str, hit: bool, payout_yen: int) -> None:
    if key not in pockets:
        pockets[key] = PocketAgg(key)
    pockets[key].update(race_date, hit, payout_yen)


def _model_market_gap(prob_rank: int, market_rank: int) -> str:
    if prob_rank <= 2 and market_rank <= 3:
        return "probTop2_marketTop3"
    if prob_rank <= 2 and market_rank <= 10:
        return "probTop2_market4_10"
    if prob_rank <= 2 and market_rank <= 30:
        return "probTop2_market11_30"
    if prob_rank <= 2:
        return "probTop2_market31plus"
    if prob_rank <= 5 and market_rank <= 10:
        return "prob3_5_marketTop10"
    if prob_rank <= 5 and market_rank > 10:
        return "prob3_5_market11plus"
    if prob_rank <= 10:
        return "prob6_10"
    return "prob11_20"


def _head_group(ticket: str) -> str:
    h = _head_lane(ticket)
    return "head1" if h == "1" else f"head{h}"


def _candidate_in_scope(row: Dict[str, Any]) -> bool:
    pr = _safe_int(row.get("prob_rank"), 999)
    er = _safe_int(row.get("ev_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    # 診断対象を絞る。全120点を全更新すると重いので、
    # モデル上位・EV上位・市場上位だけを候補ポケットにする。
    return pr <= 20 or er <= 20 or mr <= 10


def _update_pockets_for_candidate(
    pockets: Dict[str, PocketAgg],
    row: Dict[str, Any],
    race: Dict[str, Any],
    actual_ticket: str,
    payout_yen: int,
    is_seed: bool,
    lane1_class: int,
) -> None:
    ticket = str(row.get("ticket"))
    hit = ticket == actual_ticket
    race_date = str(race.get("race_date"))
    venue_id = str(race.get("venue_id", "")).zfill(2)
    race_no = _safe_int(race.get("race_no"), 0)

    pr = _safe_int(row.get("prob_rank"), 999)
    er = _safe_int(row.get("ev_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odds = _safe_float(row.get("odds"), 0.0)

    pb = _rank_bin(pr)
    eb = _rank_bin(er)
    mb = _market_bin(mr)
    ob = _odds_bin(odds)
    rg = _race_no_group(race_no)
    hg = _head_group(ticket)
    gap = _model_market_gap(pr, mr)
    seed_tag = "seed" if is_seed else "non_seed"
    bad_tag = "bad5" if venue_id in BAD_VENUES else "good19"
    lane1_tag = {4: "lane1_A1", 3: "lane1_A2", 2: "lane1_B1", 1: "lane1_B2"}.get(lane1_class, "lane1_other")

    # Exact model top groups. ここは既存all_prob_2pt等の再検証に近い。
    if pr == 1:
        _pocket_update(pockets, "MODEL/prob_top1", race_date, hit, payout_yen)
    if pr <= 2:
        _pocket_update(pockets, "MODEL/prob_top2", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/market={mb}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/gap={gap}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/head={hg}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/venue={venue_id}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/racegrp={rg}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/{bad_tag}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/{seed_tag}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/{lane1_tag}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/venue={venue_id}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/head={hg}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/gap={gap}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"TOP2/market={mb}/odds={ob}", race_date, hit, payout_yen)
    if pr <= 3:
        _pocket_update(pockets, "MODEL/prob_top3", race_date, hit, payout_yen)
    if pr <= 5:
        _pocket_update(pockets, "MODEL/prob_top5", race_date, hit, payout_yen)
    if pr <= 10:
        _pocket_update(pockets, "MODEL/prob_top10", race_date, hit, payout_yen)
    if er <= 2:
        _pocket_update(pockets, "MODEL/ev_top2", race_date, hit, payout_yen)
        _pocket_update(pockets, f"EVTOP2/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"EVTOP2/gap={gap}", race_date, hit, payout_yen)
    if mr <= 3:
        _pocket_update(pockets, "MARKET/market_top3", race_date, hit, payout_yen)

    # General diagnostic bins for top20.
    if pr <= 20:
        _pocket_update(pockets, f"DIAG/prob={pb}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/prob={pb}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/prob={pb}/market={mb}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/prob={pb}/market={mb}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/head={hg}/prob={pb}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/venue={venue_id}/prob={pb}/odds={ob}", race_date, hit, payout_yen)
        _pocket_update(pockets, f"DIAG/racegrp={rg}/prob={pb}/odds={ob}", race_date, hit, payout_yen)


def _fmt_row(r: Dict[str, Any]) -> str:
    return (
        f"{r['name'][:52]:52s} "
        f"n={r['n']:6d} hit={r['hits']:4d}({r['hit_rate']:5.1f}%) "
        f"ROI={r['roi']:6.1f}% profit={r['profit']:>+9,} "
        f"ex25={r['ex25']:6.1f}% ex26={r['ex26']:6.1f}% "
        f"both={r['exboth']:6.1f}% top1={r['extop1']:6.1f}% top3={r['extop3']:6.1f}% "
        f"maxL={r['maxlose']:4d} topPay={r['top1pay']:>7,}"
    )


def _print_rows(title: str, rows: List[Dict[str, Any]], limit: int = 30) -> None:
    print(f"\n--- {title} ---", flush=True)
    if not rows:
        print("該当なし", flush=True)
        return
    for r in rows[:limit]:
        print(_fmt_row(r), flush=True)


def main() -> None:
    _require_settings()
    print("✅ backtest_multi_patterns_v8_pocket_diagnostics.py VERSION 2026-06-22 pocket-diagnostics", flush=True)
    print("=== v8 買える条件ポケット診断開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"対象候補: prob_rank<=20 or ev_rank<=20 or market_rank<=10", flush=True)
    print(f"bad_venues={','.join(BAD_VENUES)}", flush=True)

    dates = list(_daterange(START_DATE, END_DATE))
    pockets: Dict[str, PocketAgg] = {}
    monthly: Dict[str, Dict[str, int]] = {}
    total_races = ready_races = seed_ready = candidate_count = 0

    try:
        for idx, race_date in enumerate(dates, start=1):
            t0 = time.time()
            races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)
            day_ready = 0
            day_seed = 0
            day_candidates = 0

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

                rows = _rank_candidates(entries, venue_id, odds)
                for row in rows:
                    if not _candidate_in_scope(row):
                        continue
                    candidate_count += 1
                    day_candidates += 1
                    _update_pockets_for_candidate(pockets, row, race, actual, payout_yen, is_seed, lane1_class)

            mm = race_date[:7]
            m = monthly.setdefault(mm, {"races": 0, "ready": 0, "seed": 0})
            m["races"] += len(races)
            m["ready"] += day_ready
            m["seed"] += day_seed

            if idx == 1 or idx % LOG_EVERY_DAYS == 0 or idx == len(dates):
                print(
                    f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={day_ready} seed={day_seed} "
                    f"candidates={day_candidates} pockets={len(pockets)} elapsed={time.time()-t0:.1f}s",
                    flush=True,
                )
            if DAY_SLEEP > 0:
                time.sleep(DAY_SLEEP)

        print("\n" + "=" * 88, flush=True)
        print("v8 買える条件ポケット診断結果", flush=True)
        print("=" * 88, flush=True)
        print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
        print(f"読み込みレース数: {total_races}", flush=True)
        print(f"backtest_ready: {ready_races}", flush=True)
        print(f"seed_ready: {seed_ready}", flush=True)
        print(f"候補チケット更新数: {candidate_count}", flush=True)
        print(f"pocket数: {len(pockets)}", flush=True)

        print("\n--- 月別 ready / seed ---", flush=True)
        for mm in sorted(monthly):
            m = monthly[mm]
            print(f"{mm} races={m['races']:5d} ready={m['ready']:5d} seed={m['seed']:4d}", flush=True)

        rows = [p.row() for p in pockets.values()]

        # Existing model-style baselines.
        baseline_names = {
            "MODEL/prob_top1", "MODEL/prob_top2", "MODEL/prob_top3", "MODEL/prob_top5", "MODEL/prob_top10",
            "MODEL/ev_top2", "MARKET/market_top3",
            "TOP2/good19", "TOP2/bad5", "TOP2/seed", "TOP2/non_seed",
            "TOP2/lane1_A1", "TOP2/lane1_A2", "TOP2/lane1_B1", "TOP2/lane1_B2",
        }
        _print_rows(
            "主要ベースライン",
            [r for r in rows if r["name"] in baseline_names],
            limit=50,
        )

        min_n = 300
        min_hits = 5
        robust_rows = [
            r for r in rows
            if r["n"] >= min_n and r["hits"] >= min_hits
        ]

        _print_rows(
            f"堅牢性順 Top30 n>={min_n} hits>={min_hits} / min(all,ex25,ex26,both,top1)",
            sorted(robust_rows, key=lambda r: (r["robust"], r["roi"]), reverse=True),
            limit=30,
        )

        _print_rows(
            f"表面ROI順 Top30 n>={min_n} hits>={min_hits}",
            sorted(robust_rows, key=lambda r: r["roi"], reverse=True),
            limit=30,
        )

        _print_rows(
            "TOP2 breakdown",
            sorted([r for r in rows if r["name"].startswith("TOP2/") and r["n"] >= 100], key=lambda r: r["robust"], reverse=True),
            limit=60,
        )

        _print_rows(
            "DIAG prob/market/odds robust Top40",
            sorted([r for r in rows if r["name"].startswith("DIAG/prob=") and r["n"] >= 200 and r["hits"] >= 3], key=lambda r: r["robust"], reverse=True),
            limit=40,
        )

        print("\n=== v8 買える条件ポケット診断終了 ===", flush=True)

    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()