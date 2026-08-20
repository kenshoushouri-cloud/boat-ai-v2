# -*- coding: utf-8 -*-
"""
backtest_v24_motor2_historical_pg.py

Motor2 historical backtest (READ ONLY)

- Historical races with complete entries, official trifecta result,
  and complete stored trifecta odds snapshot are evaluated.
- BASE = no lane-varying Motor2 effect.
- Multiple Motor2 weights are compared on the same races.
- LOW / MID rules match the current Motor2 Forward Shadow.
- No DB update / LINE / BUY / production change.
"""

from __future__ import annotations

import itertools
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from db_pg import fetch_all

VERSION = "2026-08-20 v24-motor2-historical-backtest-v1"

START_DATE = os.getenv("MOTOR2_BT_START_DATE", "2025-07-01").strip()
END_DATE = os.getenv("MOTOR2_BT_END_DATE", "2026-08-19").strip()
UNIT_YEN = max(1, int(os.getenv("MOTOR2_BT_UNIT_YEN", "100")))
PROGRESS_EVERY = max(1, int(os.getenv("MOTOR2_BT_PROGRESS_EVERY", "5000")))
REQUIRE_COMPLETE_MOTOR2 = os.getenv("MOTOR2_BT_REQUIRE_COMPLETE_MOTOR2", "1").strip().lower() not in {"0", "false", "no", "off"}
MAX_RACES = max(0, int(os.getenv("MOTOR2_BT_MAX_RACES", "0")))

RAW_WEIGHTS = os.getenv(
    "MOTOR2_BT_WEIGHTS",
    "0,0.10,0.20,0.30,0.40,0.45,0.50,0.60",
)
WEIGHTS = sorted({round(float(x.strip()), 6) for x in RAW_WEIGHTS.split(",") if x.strip()})
if 0.0 not in WEIGHTS:
    WEIGHTS = [0.0] + WEIGHTS

PROB_TEMP = 2.20
CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"
ALL_LANES = {1, 2, 3, 4, 5, 6}


def sf(v: Any, d=None):
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def si(v: Any, d=0):
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def period(ds: str) -> str:
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1"
    return "OOS2"


def month_starts(a: str, b: str) -> Iterable[str]:
    d = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    e = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-%d")
        d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)


def next_month_start(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")


def next_day(s: str) -> str:
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def norm_ticket(v: Any) -> str:
    s = str(v or "").strip()
    parts = s.split("-")
    if len(parts) != 3:
        return ""
    try:
        lanes = [int(x) for x in parts]
    except Exception:
        return ""
    if any(x not in ALL_LANES for x in lanes) or len(set(lanes)) != 3:
        return ""
    return f"{lanes[0]}-{lanes[1]}-{lanes[2]}"


def expected_ticket_set(active_lanes: set[int]) -> set[str]:
    return {f"{a}-{b}-{c}" for a, b, c in itertools.permutations(sorted(active_lanes), 3)}


def validate_odds(odds: Dict[str, float]) -> bool:
    tickets = set(odds)
    active = set()
    for t in tickets:
        nt = norm_ticket(t)
        if not nt:
            return False
        active.update(int(x) for x in nt.split("-"))
    if not (4 <= len(active) <= 6):
        return False
    return tickets == expected_ticket_set(active)


def valid_motor2(v: Any):
    x = sf(v, None)
    return x if x is not None and 0.0 <= x <= 100.0 else None


def raw_strength(entry: Dict[str, Any], lane: int, venue: str, motor_weight: float) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0) or 0.0
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)
    nat2 = 32.0 if nat2 is None else nat2
    loc2 = 30.0 if loc2 is None else loc2
    avg_st = 0.18 if avg_st is None else avg_st
    m2 = valid_motor2(entry.get("motor_place2_rate"))
    if m2 is None:
        m2 = 33.0
    course_bias = VENUE_COURSE_BIAS.get(venue, DEFAULT_COURSE_BIAS).get(lane, DEFAULT_COURSE_BIAS[lane])
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        cls_w
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (m2 / 100.0) * motor_weight
        + (34.0 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probs(entries: List[Dict[str, Any]], venue: str, motor_weight: float) -> Dict[str, float]:
    by = {si(e.get("lane")): e for e in entries}
    raw = {lane: raw_strength(by[lane], lane, venue, motor_weight) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    out = {}
    for a in range(1, 7):
        pa = weights[a] / total
        tb = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / tb
            tc = tb - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / tc)
    return out


def rank_map(values: Dict[str, float], reverse: bool = True) -> Dict[str, int]:
    ordered = sorted(values.items(), key=(lambda kv: (-kv[1], kv[0])) if reverse else (lambda kv: (kv[1], kv[0])))
    return {t: i for i, (t, _) in enumerate(ordered, 1)}


def is_low(pr: int, mr: int, odd: float) -> bool:
    return 11 <= pr <= 20 and mr == 1 and 3.0 <= odd < 5.0


def is_mid(ticket: str, pr: int, mr: int, odd: float) -> bool:
    return 4 <= pr <= 5 and 21 <= mr <= 30 and 30.0 <= odd < 50.0 and ticket.split("-", 1)[0] != "1"


def stat_new():
    return {"bets": 0, "hits": 0, "investment": 0, "return": 0, "low_bets": 0, "low_hits": 0, "low_return": 0, "mid_bets": 0, "mid_hits": 0, "mid_return": 0, "both": 0, "base_only": 0, "motor_only": 0}


def add_bet(stat, kind: str, hit: bool, payout: int):
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN
    stat[f"{kind}_bets"] += 1
    if hit:
        stat["hits"] += 1
        stat["return"] += payout
        stat[f"{kind}_hits"] += 1
        stat[f"{kind}_return"] += payout


def pct(a: int, b: int) -> float:
    return a / b * 100 if b else 0.0


def roi(ret: int, inv: int) -> float:
    return ret / inv * 100 if inv else 0.0


def fmt_weight(weight: float, s) -> str:
    return (
        f"W={weight:.2f} bets={s['bets']} hits={s['hits']} hit_rate={pct(s['hits'],s['bets']):.3f}% "
        f"investment={s['investment']} return={s['return']} profit={s['return']-s['investment']} ROI={roi(s['return'],s['investment']):.2f}% "
        f"LOW={s['low_bets']}/{s['low_hits']} ROI={roi(s['low_return'],s['low_bets']*UNIT_YEN):.2f}% "
        f"MID={s['mid_bets']}/{s['mid_hits']} ROI={roi(s['mid_return'],s['mid_bets']*UNIT_YEN):.2f}%"
    )


def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return [], [], [], []
    ra, rb = a.replace("-", ""), b.replace("-", "")
    races = fetch_all("select race_id,race_date,venue_id,venue_code,race_no from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no", (a, b))
    entries = fetch_all("select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st,motor_place2_rate from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane", (ra, rb))
    results = fetch_all("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_date >= %s and race_date < %s and result_status='official' and race_status='official' and trifecta_ticket is not null and trifecta_payout_yen > 0 order by race_id", (a, b))
    odds = fetch_all("select race_id,ticket,odds from v2_odds_trifecta where race_id >= %s and race_id < %s and odds > 0 order by race_id,ticket", (ra, rb))
    return races, entries, results, odds


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")

    print(f"â backtest_v24_motor2_historical_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} WEIGHTS={','.join(f'{w:.2f}' for w in WEIGHTS)} UNIT_YEN={UNIT_YEN} REQUIRE_COMPLETE_MOTOR2={REQUIRE_COMPLETE_MOTOR2} MAX_RACES={MAX_RACES or 'ALL'}", flush=True)
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    print("NOTE: historical odds use the snapshot currently stored in v2_odds_trifecta; exact same-moment market reconstruction is not guaranteed.", flush=True)

    overall = {w: stat_new() for w in WEIGHTS}
    by_period = {p: {w: stat_new() for w in WEIGHTS} for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2")}

    processed = skipped_entries = skipped_motor2 = skipped_result = skipped_odds = 0

    for ms in month_starts(START_DATE, END_DATE):
        races, entries, results, odds_rows = fetch_month(ms, next_month_start(ms))
        eb = defaultdict(list)
        for e in entries:
            eb[str(e.get("race_id") or "")].append(e)
        rb = {}
        for r in results:
            rid = str(r.get("race_id") or "")
            t = norm_ticket(r.get("trifecta_ticket"))
            p = si(r.get("trifecta_payout_yen"), 0)
            if rid and t and p > 0:
                rb[rid] = (t, p)
        ob = defaultdict(dict)
        for o in odds_rows:
            rid = str(o.get("race_id") or "")
            t = norm_ticket(o.get("ticket"))
            odd = sf(o.get("odds"), None)
            if rid and t and odd is not None and odd > 0:
                ob[rid][t] = float(odd)

        month_processed = 0
        for race in races:
            if MAX_RACES and processed >= MAX_RACES:
                break
            rid = str(race.get("race_id") or "")
            ds = str(race.get("race_date") or "")[:10]
            venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            if rid not in rb:
                skipped_result += 1
                continue
            ent = eb.get(rid, [])
            lanes = {si(e.get("lane")) for e in ent if 1 <= si(e.get("lane")) <= 6}
            if len(ent) != 6 or lanes != ALL_LANES:
                skipped_entries += 1
                continue
            valid_m2 = sum(valid_motor2(e.get("motor_place2_rate")) is not None for e in ent)
            if REQUIRE_COMPLETE_MOTOR2 and valid_m2 != 6:
                skipped_motor2 += 1
                continue
            odds = ob.get(rid, {})
            if not validate_odds(odds):
                skipped_odds += 1
                continue

            win_ticket, payout = rb[rid]
            market_rank = rank_map(odds, reverse=False)
            base_probs = ticket_probs(ent, venue, 0.0)
            base_ranks = rank_map(base_probs, reverse=True)
            base_candidates = {}
            for t, odd in odds.items():
                pr, mr = base_ranks[t], market_rank[t]
                if is_low(pr, mr, odd):
                    base_candidates[t] = "low"
                elif is_mid(t, pr, mr, odd):
                    base_candidates[t] = "mid"

            per = period(ds)
            for w in WEIGHTS:
                if w == 0.0:
                    ranks = base_ranks
                else:
                    ranks = rank_map(ticket_probs(ent, venue, w), reverse=True)

                candidates = {}
                for t, odd in odds.items():
                    pr, mr = ranks[t], market_rank[t]
                    if is_low(pr, mr, odd):
                        candidates[t] = "low"
                    elif is_mid(t, pr, mr, odd):
                        candidates[t] = "mid"

                s, ps = overall[w], by_period[per][w]
                all_tickets = set(base_candidates) | set(candidates)
                for t in all_tickets:
                    b, m = t in base_candidates, t in candidates
                    if b and m:
                        s["both"] += 1; ps["both"] += 1
                    elif b:
                        s["base_only"] += 1; ps["base_only"] += 1
                    elif m:
                        s["motor_only"] += 1; ps["motor_only"] += 1

                for t, kind in candidates.items():
                    add_bet(s, kind, t == win_ticket, payout)
                    add_bet(ps, kind, t == win_ticket, payout)

            processed += 1
            month_processed += 1
            if processed % PROGRESS_EVERY == 0:
                print(f"PROGRESS processed={processed} date={ds} race_id={rid}", flush=True)

        print(f"month={ms[:7]} races={len(races)} processed={month_processed}", flush=True)
        if MAX_RACES and processed >= MAX_RACES:
            break

    print("\n=== OVERALL WEIGHT COMPARISON ===", flush=True)
    base_roi = roi(overall[0.0]["return"], overall[0.0]["investment"])
    for w in WEIGHTS:
        print(fmt_weight(w, overall[w]), flush=True)
        if w != 0.0:
            wr = roi(overall[w]["return"], overall[w]["investment"])
            print(f"  vs BASE: ROI_DELTA={wr-base_roi:+.2f}pt bets_delta={overall[w]['bets']-overall[0.0]['bets']:+d} hits_delta={overall[w]['hits']-overall[0.0]['hits']:+d} BOTH={overall[w]['both']} BASE_ONLY={overall[w]['base_only']} MOTOR2_ONLY={overall[w]['motor_only']}", flush=True)

    print("\n=== PERIOD STABILITY ===", flush=True)
    for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2"):
        print(f"[{p}]", flush=True)
        br = roi(by_period[p][0.0]["return"], by_period[p][0.0]["investment"])
        for w in WEIGHTS:
            s = by_period[p][w]
            wr = roi(s["return"], s["investment"])
            print(f"  W={w:.2f} bets={s['bets']} hits={s['hits']} ROI={wr:.2f}% delta_vs_base={wr-br:+.2f}pt", flush=True)

    print("\n=== AUDIT ===", flush=True)
    print(f"processed={processed}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_motor2={skipped_motor2}", flush=True)
    print(f"skipped_result={skipped_result}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()