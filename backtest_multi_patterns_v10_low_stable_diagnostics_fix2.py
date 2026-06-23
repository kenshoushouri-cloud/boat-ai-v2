# -*- coding: utf-8 -*-
"""
backtest_multi_patterns_v10_low_stable_diagnostics.py

競艇AI v2用・低オッズ安定候補の会場/日付/レース番号別ポケット診断。

目的:
- Variablesを毎回変えず、ロジック内設定だけで実行する。
- 現在の未校正probをそのままEV計算に使わず、過去日までの実績だけで
  ビン別の的中率・ROIを校正して買い目を選ぶ。
- 未来データを使わない walk-forward 方式。
- 大穴一撃依存を避けるため、払戻クリップROIや上位払戻除外も自動表示する。

Railway Start Command:
    python backtest_multi_patterns_v10_low_stable_diagnostics.py

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
# v10 Low-stable diagnostics
# ============================================================

@dataclass
class Agg:
    name: str
    n: int = 0
    hits: int = 0
    stake: int = 0
    payout: int = 0
    by_month: Dict[str, Dict[str, int]] = field(default_factory=dict)
    top: List[int] = field(default_factory=list)
    cur_losing: int = 0
    max_losing: int = 0

    def add(self, race_date: str, hit: bool, payout_yen: int) -> None:
        self.n += 1
        self.stake += UNIT_YEN
        mm = race_date[:7]
        m = self.by_month.setdefault(mm, {"n": 0, "hits": 0, "stake": 0, "payout": 0})
        m["n"] += 1
        m["stake"] += UNIT_YEN
        if hit:
            pay = int(payout_yen * UNIT_YEN / PAYOUT_BASE_YEN)
            self.hits += 1
            self.payout += pay
            m["hits"] += 1
            m["payout"] += pay
            self.top.append(pay)
            self.top.sort(reverse=True)
            self.top = self.top[:5]
            self.cur_losing = 0
        else:
            self.cur_losing += 1
            self.max_losing = max(self.max_losing, self.cur_losing)

    def roi(self) -> float:
        return self.payout / self.stake * 100.0 if self.stake else 0.0

    def ex_month(self, *months: str) -> float:
        stake = self.stake
        payout = self.payout
        for mm in months:
            m = self.by_month.get(mm)
            if m:
                stake -= m["stake"]
                payout -= m["payout"]
        return payout / stake * 100.0 if stake > 0 else 0.0

    def ex_top(self, k: int) -> float:
        k = min(k, len(self.top))
        stake = self.stake - k * UNIT_YEN
        payout = self.payout - sum(self.top[:k])
        return payout / stake * 100.0 if stake > 0 else 0.0

    def row(self) -> Dict[str, Any]:
        ex25 = self.ex_month("2025-05")
        ex26 = self.ex_month("2026-05")
        both = self.ex_month("2025-05", "2026-05")
        top1 = self.ex_top(1)
        top3 = self.ex_top(3)
        return {
            "name": self.name,
            "n": self.n,
            "hits": self.hits,
            "hit_rate": self.hits / self.n * 100.0 if self.n else 0.0,
            "roi": self.roi(),
            "profit": self.payout - self.stake,
            "ex25": ex25,
            "ex26": ex26,
            "both": both,
            "top1": top1,
            "top3": top3,
            "robust": min(self.roi(), ex25, ex26, both, top1),
            "max_losing": self.max_losing,
            "top_pay": self.top[0] if self.top else 0,
        }


def _add(aggs: Dict[str, Agg], key: str, race_date: str, hit: bool, payout_yen: int) -> None:
    if key not in aggs:
        aggs[key] = Agg(key)
    aggs[key].add(race_date, hit, payout_yen)


def _head_lane(ticket: str) -> str:
    s = _norm_ticket(ticket)
    return s.split("-")[0] if s else "?"


def _race_group(race_no: int) -> str:
    if race_no <= 3:
        return "R01_03"
    if race_no <= 6:
        return "R04_06"
    if race_no <= 9:
        return "R07_09"
    return "R10_12"


def _weekday(race_date: str) -> str:
    from datetime import date as _date
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][_date.fromisoformat(str(race_date)).weekday()]


def _day_group(race_date: str) -> str:
    d = int(race_date[8:10])
    if d <= 10:
        return "D01_10"
    if d <= 20:
        return "D11_20"
    return "D21_end"


def _is_low(row: Dict[str, Any]) -> bool:
    return (
        11 <= _safe_int(row.get("prob_rank"), 999) <= 20
        and _safe_int(row.get("market_rank"), 999) == 1
        and 3.0 <= _safe_float(row.get("odds"), 0.0) < 5.0
    )


def _fmt(r: Dict[str, Any]) -> str:
    return (
        f"{r['name'][:58]:58s} n={r['n']:5d} hit={r['hits']:4d}({r['hit_rate']:5.1f}%) "
        f"ROI={r['roi']:6.1f}% profit={r['profit']:>+8,} "
        f"ex25={r['ex25']:6.1f}% ex26={r['ex26']:6.1f}% both={r['both']:6.1f}% "
        f"top1={r['top1']:6.1f}% top3={r['top3']:6.1f}% "
        f"maxL={r['max_losing']:3d} topPay={r['top_pay']:>5,}"
    )


def _print(title: str, rows: List[Dict[str, Any]], limit: int = 30) -> None:
    print(f"\\n--- {title} ---", flush=True)
    if not rows:
        print("該当なし", flush=True)
        return
    for r in rows[:limit]:
        print(_fmt(r), flush=True)


def main() -> None:
    _require_settings()
    print("✅ backtest_multi_patterns_v10_low_stable_diagnostics_fix2.py VERSION 2026-06-23 weekday-local-import-fix", flush=True)
    print("=== v10 低オッズ安定候補チューニング診断開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print("target: prob_rank 11-20 × market_rank 1 × odds 3-5", flush=True)

    aggs: Dict[str, Agg] = {}
    monthly: Dict[str, Dict[str, int]] = {}
    total = ready = seed_ready = low_count = 0
    dates = list(_daterange(START_DATE, END_DATE))

    for idx, race_date in enumerate(dates, start=1):
        t0 = time.time()
        races, results, entries_by_race, odds_by_race = _fetch_day_rows(race_date)
        day_ready = day_seed = day_low = 0

        for race in races:
            total += 1
            rid = race.get("race_id")
            venue = str(race.get("venue_id", "")).zfill(2)
            race_no = _safe_int(race.get("race_no"), 0)
            result = results.get(rid)
            entries = entries_by_race.get(rid, [])
            odds = odds_by_race.get(rid, {})

            if not _is_backtest_ready(result, entries, odds):
                continue

            actual = _get_actual_ticket(result)
            payout_yen = _safe_int(result.get("trifecta_payout_yen"), 0)
            is_seed = _is_seed_race(entries, STRICT_SEED)

            ready += 1
            day_ready += 1
            if is_seed:
                seed_ready += 1
                day_seed += 1

            rows = _rank_candidates(entries, venue, odds)
            for row in rows:
                if not _is_low(row):
                    continue

                low_count += 1
                day_low += 1
                hit = str(row.get("ticket")) == actual
                rg = _race_group(race_no)
                wd = _weekday(race_date)
                dg = _day_group(race_date)
                head = _head_lane(str(row.get("ticket")))
                bad = "bad5" if venue in BAD_VENUES else "good19"
                seed_tag = "seed" if is_seed else "non_seed"

                keys = [
                    "LOW/base_prob11_20_market1_odds3_5",
                    f"LOW/venue={venue}",
                    f"LOW/race_no={race_no:02d}",
                    f"LOW/racegrp={rg}",
                    f"LOW/weekday={wd}",
                    f"LOW/daygrp={dg}",
                    f"LOW/head={head}",
                    f"LOW/{bad}",
                    f"LOW/{seed_tag}",
                    f"LOW/venue={venue}/racegrp={rg}",
                    f"LOW/venue={venue}/weekday={wd}",
                    f"LOW/venue={venue}/daygrp={dg}",
                    f"LOW/racegrp={rg}/weekday={wd}",
                    f"LOW/racegrp={rg}/daygrp={dg}",
                    f"LOW/head={head}/racegrp={rg}",
                    f"LOW/{bad}/racegrp={rg}",
                    f"LOW/{bad}/weekday={wd}",
                    f"LOW/venue={venue}/racegrp={rg}/weekday={wd}",
                    f"LOW/venue={venue}/racegrp={rg}/daygrp={dg}",
                ]
                for key in keys:
                    _add(aggs, key, race_date, hit, payout_yen)

        mm = race_date[:7]
        m = monthly.setdefault(mm, {"races": 0, "ready": 0, "seed": 0, "low": 0})
        m["races"] += len(races)
        m["ready"] += day_ready
        m["seed"] += day_seed
        m["low"] += day_low

        if idx == 1 or idx % LOG_EVERY_DAYS == 0 or idx == len(dates):
            print(
                f"[{idx}/{len(dates)}] {race_date} races={len(races)} ready={day_ready} "
                f"seed={day_seed} low={day_low} pockets={len(aggs)} elapsed={time.time()-t0:.1f}s",
                flush=True,
            )

    rows = [a.row() for a in aggs.values()]

    print("\\n" + "=" * 88, flush=True)
    print("v10 低オッズ安定候補チューニング診断結果", flush=True)
    print("=" * 88, flush=True)
    print(f"読み込みレース数: {total}", flush=True)
    print(f"backtest_ready: {ready}", flush=True)
    print(f"seed_ready: {seed_ready}", flush=True)
    print(f"low_candidate_count: {low_count}", flush=True)
    print(f"pocket数: {len(aggs)}", flush=True)

    print("\\n--- 月別 ready / seed / low ---", flush=True)
    for mm in sorted(monthly):
        m = monthly[mm]
        print(f"{mm} races={m['races']:5d} ready={m['ready']:5d} seed={m['seed']:4d} low={m['low']:4d}", flush=True)

    _print("低オッズ安定 base", [r for r in rows if r["name"] == "LOW/base_prob11_20_market1_odds3_5"], 5)

    robust = [r for r in rows if r["n"] >= 50 and r["hits"] >= 10]
    _print("堅牢性順 Top40 n>=50 hits>=10", sorted(robust, key=lambda r: (r["robust"], r["roi"]), reverse=True), 40)
    _print("表面ROI順 Top40 n>=50 hits>=10", sorted(robust, key=lambda r: r["roi"], reverse=True), 40)
    _print("会場別 LOW", sorted([r for r in rows if r["name"].startswith("LOW/venue=") and r["name"].count("/") == 1], key=lambda r: r["robust"], reverse=True), 30)
    _print("レース番号/時間帯 LOW", sorted([r for r in rows if (r["name"].startswith("LOW/race_no=") or r["name"].startswith("LOW/racegrp=")) and r["name"].count("/") == 1], key=lambda r: r["robust"], reverse=True), 30)
    _print("曜日/日付帯 LOW", sorted([r for r in rows if (r["name"].startswith("LOW/weekday=") or r["name"].startswith("LOW/daygrp=")) and r["name"].count("/") == 1], key=lambda r: r["robust"], reverse=True), 30)
    _print("会場×レース帯/曜日 Top40 n>=30 hits>=6", sorted([r for r in rows if r["name"].startswith("LOW/venue=") and r["name"].count("/") >= 2 and r["n"] >= 30 and r["hits"] >= 6], key=lambda r: (r["robust"], r["roi"]), reverse=True), 40)

    print("\\n=== v10 低オッズ安定候補チューニング診断終了 ===", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL ERROR", flush=True)
        print(f"{type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise