# -*- coding: utf-8 -*-
"""
analyze_v24_motor_features_pg.py

Read-only audit of whether real motor/boat place-2 rates improve the probability
model used by v24_pre_candidate_notifier_pg.py.

Models:
  BASE            : current v24 logic (motor=33.0, boat=34.0)
  MOTOR2          : valid motor_place2_rate, boat fixed 34.0
  MOTOR2_BOAT2    : valid motor_place2_rate + valid boat_place2_rate

Important:
- DB update: none
- LINE notification: none
- production decision: none
- odds: NOT USED
- actual result: v2_results.trifecta_ticket
- invalid/null rates are replaced by BASE constants
- coefficients and PROB_TEMP are kept identical to current v24
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-19 v24-motor-feature-audit-v1"
START_DATE = os.getenv("V24_MOTOR_START_DATE", "2025-07-01")
END_DATE = os.getenv("V24_MOTOR_END_DATE", "2026-08-15")

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"

MODELS = ("BASE", "MOTOR2", "MOTOR2_BOAT2")
EPS = 1e-15


def sf(v: Any, d=None):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d


def si(v: Any, d=0):
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d


def next_day(s: str) -> str:
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def month_starts(a: str, b: str):
    cur = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-01")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)


def month_end(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")


def period_name(ds: str) -> str:
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1"
    return "OOS2"


def valid_pct(v: Any) -> float | None:
    x = sf(v, None)
    if x is None or not (0.0 <= x <= 100.0):
        return None
    return x


def model_rates(entry: Dict[str, Any], model: str) -> Tuple[float, float, bool, bool]:
    m = valid_pct(entry.get("motor_place2_rate"))
    b = valid_pct(entry.get("boat_place2_rate"))
    m_valid = m is not None
    b_valid = b is not None
    if model == "BASE":
        return 33.0, 34.0, m_valid, b_valid
    if model == "MOTOR2":
        return (m if m_valid else 33.0), 34.0, m_valid, b_valid
    return (m if m_valid else 33.0), (b if b_valid else 34.0), m_valid, b_valid


def lane_raw_strength(entry: Dict[str, Any], lane: int, venue_id: str, model: str) -> float:
    # Keep current v24 coefficients exactly; only motor/boat inputs differ by model.
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0) or 0.0
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)
    nat2 = 32.0 if nat2 is None else nat2
    loc2 = 30.0 if loc2 is None else loc2
    avg_st = 0.18 if avg_st is None else avg_st
    mot2, boat2, _, _ = model_rates(entry, model)
    course_bias = v24.VENUE_COURSE_BIAS.get(venue_id, v24.DEFAULT_COURSE_BIAS).get(
        lane, v24.DEFAULT_COURSE_BIAS[lane]
    )
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


def ticket_probs(entries: List[Dict[str, Any]], venue_id: str, model: str) -> Dict[str, float]:
    by = v24._entry_by_lane(entries)
    if len(by) != 6:
        return {}
    raw = {lane: lane_raw_strength(by[lane], lane, venue_id, model) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    out: Dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        tb = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / tb
            tc = tb - weights[b]
            for c in range(1, 7):
                if c == a or c == b:
                    continue
                pc = weights[c] / tc
                out[f"{a}-{b}-{c}"] = pa * pb * pc
    return out


def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return [], [], []
    ra, rb = a.replace("-", ""), b.replace("-", "")
    races = fetch_all(
        "select race_id,race_date,venue_id,venue_code,race_no from v2_races "
        "where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",
        (a, b),
    )
    entries = fetch_all(
        "select race_id,lane,racer_class,national_win_rate,national_place2_rate,"
        "local_place2_rate,avg_st,motor_place2_rate,boat_place2_rate "
        "from v2_race_entries where race_id >= %s and race_id < %s order by race_id,lane",
        (ra, rb),
    )
    results = fetch_all(
        "select race_id,trifecta_ticket,official,result_status,race_status "
        "from v2_results where race_id >= %s and race_id < %s",
        (ra, rb),
    )
    return races, entries, results


def result_ticket(row: Dict[str, Any]) -> str:
    return v24._norm_ticket(row.get("trifecta_ticket"))


def metric(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    n = len(rows)
    if not n:
        return {"n": 0, "brier": 0.0, "logloss": 0.0, "top1": 0.0, "winprob": 0.0}
    return {
        "n": n,
        "brier": sum(r["brier"] for r in rows) / n,
        "logloss": sum(r["logloss"] for r in rows) / n,
        "top1": sum(r["top1"] for r in rows) / n * 100.0,
        "winprob": sum(r["winprob"] for r in rows) / n * 100.0,
    }


def fmt(m: Dict[str, float]) -> str:
    return (
        f"n={int(m['n'])} brier={m['brier']:.8f} logloss={m['logloss']:.8f} "
        f"top1={m['top1']:.3f}% avg_actual_prob={m['winprob']:.4f}%"
    )


def delta(candidate: Dict[str, float], base: Dict[str, float]) -> str:
    if not candidate["n"] or not base["n"]:
        return "n/a"
    # Negative Brier/logloss delta is improvement; positive top1 is improvement.
    return (
        f"brier_delta={candidate['brier']-base['brier']:+.8f} "
        f"logloss_delta={candidate['logloss']-base['logloss']:+.8f} "
        f"top1_delta={candidate['top1']-base['top1']:+.3f}pt "
        f"actual_prob_delta={candidate['winprob']-base['winprob']:+.4f}pt"
    )


def improved(candidate: Dict[str, float], base: Dict[str, float]) -> bool:
    if not candidate["n"] or candidate["n"] != base["n"]:
        return False
    # Require both proper scoring rules to improve. top1 is reported, not gated.
    return candidate["brier"] < base["brier"] and candidate["logloss"] < base["logloss"]


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")

    print(f"â analyze_v24_motor_features_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        f"SPLIT TRAIN< {TRAIN_END} / VALID< {VALID_END} / TEST< {OOS1_START} / "
        f"OOS1< {OOS2_START} / OOS2 thereafter",
        flush=True,
    )
    print("èª­ã¿åãå°ç¨ãDBæ´æ°ã»LINEéç¥ã»æ¬çªå¤å®å¤æ´ãªãã", flush=True)
    print("ãªããºã¯ä½¿ç¨ãã¾ãããv2_resultsã®å®ä¸é£åã«å¯¾ããç¢ºçåè³ªã ããæ¯è¼ãã¾ãã", flush=True)
    print("BASE=motor33.0/boat34.0; MOTOR2=å®motor2; MOTOR2_BOAT2=å®motor2+boat2", flush=True)
    print("å®å¤ã¯0..100ã®ã¿æ¡ç¨ããNULL/ç¯å²å¤ã¯BASEå¤ã¸ãã©ã¼ã«ããã¯ãã¾ãã", flush=True)

    rows_by_model: Dict[str, List[Dict[str, Any]]] = {m: [] for m in MODELS}
    coverage = {"entry_rows": 0, "motor_valid": 0, "motor_fallback": 0, "boat_valid": 0, "boat_fallback": 0}
    total_races = ready_races = skipped_entries = skipped_result = 0

    for ms in month_starts(START_DATE, END_DATE):
        races, entries, results = fetch_month(ms, month_end(ms))
        eb = defaultdict(list)
        for e in entries:
            eb[str(e.get("race_id") or "")].append(e)
        rb = {}
        for r in results:
            rid = str(r.get("race_id") or "")
            t = result_ticket(r)
            if rid and t:
                rb[rid] = t

        month_ready = 0
        for race in races:
            total_races += 1
            rid = str(race.get("race_id") or "")
            ent = eb.get(rid, [])
            if len(v24._entry_by_lane(ent)) != 6:
                skipped_entries += 1
                continue
            actual = rb.get(rid, "")
            if not actual:
                skipped_result += 1
                continue

            if not rows_by_model["BASE"] or rows_by_model["BASE"][-1].get("race_id") != rid:
                for e in ent:
                    coverage["entry_rows"] += 1
                    if valid_pct(e.get("motor_place2_rate")) is not None:
                        coverage["motor_valid"] += 1
                    else:
                        coverage["motor_fallback"] += 1
                    if valid_pct(e.get("boat_place2_rate")) is not None:
                        coverage["boat_valid"] += 1
                    else:
                        coverage["boat_fallback"] += 1

            venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            ds = str(race.get("race_date") or "")[:10]
            month = ds[:7]

            model_probs = {m: ticket_probs(ent, venue, m) for m in MODELS}
            if any(actual not in model_probs[m] for m in MODELS):
                skipped_result += 1
                continue

            ready_races += 1
            month_ready += 1
            for m in MODELS:
                probs = model_probs[m]
                p_actual = max(EPS, probs[actual])
                brier = sum(p * p for p in probs.values()) - 2.0 * probs[actual] + 1.0
                top_ticket = max(probs.items(), key=lambda kv: kv[1])[0]
                rows_by_model[m].append({
                    "race_id": rid,
                    "date": ds,
                    "month": month,
                    "period": period_name(ds),
                    "brier": brier,
                    "logloss": -math.log(p_actual),
                    "top1": 1 if top_ticket == actual else 0,
                    "winprob": probs[actual],
                })

        print(f"month={ms[:7]} races={len(races)} ready={month_ready}", flush=True)

    print("\n=== DATA QUALITY / COVERAGE ===", flush=True)
    print(
        f"total_races={total_races} ready_races={ready_races} "
        f"skipped_entries={skipped_entries} skipped_result={skipped_result}",
        flush=True,
    )
    er = coverage["entry_rows"]
    mp = coverage["motor_valid"] / er * 100 if er else 0.0
    bp = coverage["boat_valid"] / er * 100 if er else 0.0
    print(
        f"entry_rows={er} motor_valid={coverage['motor_valid']} ({mp:.2f}%) "
        f"motor_fallback={coverage['motor_fallback']} boat_valid={coverage['boat_valid']} ({bp:.2f}%) "
        f"boat_fallback={coverage['boat_fallback']}",
        flush=True,
    )

    print("\n=== PERIOD COMPARISON ===", flush=True)
    period_metrics: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(dict)
    for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2"):
        print(f"\n[{p}]", flush=True)
        base_rows = [r for r in rows_by_model["BASE"] if r["period"] == p]
        bm = metric(base_rows)
        period_metrics[p]["BASE"] = bm
        print(f"BASE         {fmt(bm)}", flush=True)
        for m in ("MOTOR2", "MOTOR2_BOAT2"):
            mm = metric([r for r in rows_by_model[m] if r["period"] == p])
            period_metrics[p][m] = mm
            print(f"{m:<13}{fmt(mm)}", flush=True)
            print(f"  vs BASE: {delta(mm, bm)}", flush=True)

    print("\n=== MONTHLY COMPARISON ===", flush=True)
    months = sorted({r["month"] for r in rows_by_model["BASE"]})
    monthly_wins = {m: {"brier": 0, "logloss": 0, "both": 0, "months": 0} for m in MODELS if m != "BASE"}
    for mon in months:
        bm = metric([r for r in rows_by_model["BASE"] if r["month"] == mon])
        print(f"{mon} BASE {fmt(bm)}", flush=True)
        for m in ("MOTOR2", "MOTOR2_BOAT2"):
            mm = metric([r for r in rows_by_model[m] if r["month"] == mon])
            if mm["n"]:
                monthly_wins[m]["months"] += 1
                if mm["brier"] < bm["brier"]:
                    monthly_wins[m]["brier"] += 1
                if mm["logloss"] < bm["logloss"]:
                    monthly_wins[m]["logloss"] += 1
                if improved(mm, bm):
                    monthly_wins[m]["both"] += 1
            print(f"  {m:<13}{delta(mm, bm)}", flush=True)

    print("\n=== MONTHLY STABILITY ===", flush=True)
    for m in ("MOTOR2", "MOTOR2_BOAT2"):
        x = monthly_wins[m]
        print(
            f"{m}: months={x['months']} brier_better={x['brier']} "
            f"logloss_better={x['logloss']} both_better={x['both']}",
            flush=True,
        )

    print("\n=== FINAL VERDICT ===", flush=True)
    overall = {m: metric(rows_by_model[m]) for m in MODELS}
    for m in MODELS:
        print(f"{m:<13}{fmt(overall[m])}", flush=True)
        if m != "BASE":
            print(f"  vs BASE: {delta(overall[m], overall['BASE'])}", flush=True)

    candidates = []
    for m in ("MOTOR2", "MOTOR2_BOAT2"):
        oos1_ok = improved(period_metrics["OOS1"][m], period_metrics["OOS1"]["BASE"])
        oos2_ok = improved(period_metrics["OOS2"][m], period_metrics["OOS2"]["BASE"])
        test_ok = improved(period_metrics["TEST"][m], period_metrics["TEST"]["BASE"])
        stable = monthly_wins[m]["both"] >= max(1, math.ceil(monthly_wins[m]["months"] * 0.50))
        print(
            f"{m}: TEST={'PASS' if test_ok else 'WAIT'} "
            f"OOS1={'PASS' if oos1_ok else 'FAIL'} OOS2={'PASS' if oos2_ok else 'FAIL'} "
            f"MONTHLY_STABILITY={'PASS' if stable else 'WAIT'}",
            flush=True,
        )
        # OOS1/OOS2 both are mandatory. TEST/monthly stability are supporting guards.
        if oos1_ok and oos2_ok and test_ok and stable:
            candidates.append(m)

    if not candidates:
        verdict = "KEEP_BASE"
        reason = "OOS1/OOS2ãå«ãæ¡ç¨æ¡ä»¶ãæºããå®å¤ã¢ãã«ãªã"
    else:
        best = min(candidates, key=lambda m: (overall[m]["brier"], overall[m]["logloss"]))
        verdict = f"REVIEW_FOR_PRODUCTION:{best}"
        reason = "OOS1/OOS2ä¸¡æ¹ã»TESTã»æå¥å®å®æ§ãééãã¾ã èªååæ ã¯ããªã"
    print(f"VERDICT={verdict}", flush=True)
    print(f"REASON={reason}", flush=True)
    print("æ¬ã¹ã¯ãªããã¯èª­ã¿åãå°ç¨ã§ããv24æ¬çªã³ã¼ãã¯å¤æ´ãã¦ãã¾ããã", flush=True)
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()