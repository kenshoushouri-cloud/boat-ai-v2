# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

from db_pg import fetch_all

VERSION = "2026-08-21 v24-motor2-forward-performance-v2-mid-veto"
JST = timezone(timedelta(hours=9))
END_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
START_DATE = (os.getenv("MOTOR2_FORWARD_REPORT_START_DATE") or "2026-08-20").strip()
UNIT_YEN = max(1, int(os.getenv("MOTOR2_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100"))))
REVIEW_TARGETS = [
    int(x)
    for x in (os.getenv("MOTOR2_FORWARD_REVIEW_TARGETS") or "10,30,50,100").split(",")
    if x.strip().isdigit()
]
MID_VETO_REVIEW_TARGETS = [
    int(x)
    for x in (os.getenv("MOTOR2_MID_VETO_REVIEW_TARGETS") or "10,30,50,100").split(",")
    if x.strip().isdigit()
]


def si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def fetch_rows():
    return fetch_all(
        """
        SELECT *
        FROM v2_v24_motor2_forward_shadow
        WHERE race_date >= %s
          AND race_date <= %s
          AND evaluated_at IS NOT NULL
          AND result_ticket IS NOT NULL
          AND payout_yen > 0
        ORDER BY race_date, snapshot_at, id
        """,
        (START_DATE, END_DATE),
    )


def new() -> Dict[str, int]:
    return {"bets": 0, "hits": 0, "investment": 0, "return": 0}


def add(s: Dict[str, int], selected: bool, hit: bool, payout: int) -> None:
    if not selected:
        return
    s["bets"] += 1
    s["investment"] += UNIT_YEN
    if hit:
        s["hits"] += 1
        s["return"] += payout


def roi(s: Dict[str, int]) -> float:
    return s["return"] / s["investment"] * 100 if s["investment"] else 0.0


def fmt(name: str, s: Dict[str, int]) -> str:
    bets = s["bets"]
    hit_rate = s["hits"] / bets * 100 if bets else 0.0
    return (
        f"{name}: bets={bets} hits={s['hits']} hit_rate={hit_rate:.2f}% "
        f"investment={s['investment']} return={s['return']} "
        f"profit={s['return'] - s['investment']} ROI={roi(s):.2f}%"
    )


def latest(rows: Iterable[Dict[str, Any]]):
    out: Dict[tuple[str, str, str, str], Dict[str, Any]] = {}
    for r in rows:
        key = (
            str(r.get("race_id") or ""),
            str(r.get("ticket") or ""),
            str(r.get("run_class") or ""),
            str(r.get("window_name") or ""),
        )
        if key not in out or str(r.get("snapshot_at") or "") >= str(out[key].get("snapshot_at") or ""):
            out[key] = r
    return list(out.values())


def summarize(rows):
    st = {
        "BASE": new(),
        "MOTOR2": new(),
        "BOTH": new(),
        "BASE_ONLY": new(),
        "MOTOR2_ONLY": new(),
    }
    transitions = defaultdict(int)

    for r in rows:
        payout = si(r.get("payout_yen"))
        hit = str(r.get("ticket") or "") == str(r.get("result_ticket") or "")
        base_selected = bool(r.get("base_low_candidate")) or bool(r.get("base_mid_candidate"))
        motor2_selected = bool(r.get("motor2_low_candidate")) or bool(r.get("motor2_mid_candidate"))

        add(st["BASE"], base_selected, base_selected and hit, payout)
        add(st["MOTOR2"], motor2_selected, motor2_selected and hit, payout)

        transition = str(r.get("candidate_transition") or "")
        transitions[transition] += 1
        if transition in st and transition not in ("BASE", "MOTOR2"):
            add(st[transition], True, hit, payout)

    return st, transitions


def scope(label: str, rows) -> None:
    st, transitions = summarize(rows)
    print(f"=== {label} ===")
    print(f"rows={len(rows)}")
    print(fmt("BASE", st["BASE"]))
    print(fmt("MOTOR2", st["MOTOR2"]))
    print(f"ROI_DELTA MOTOR2-BASE={roi(st['MOTOR2']) - roi(st['BASE']):+.2f}pt")
    print(
        "TRANSITIONS "
        f"BOTH={transitions.get('BOTH', 0)} "
        f"BASE_ONLY={transitions.get('BASE_ONLY', 0)} "
        f"MOTOR2_ONLY={transitions.get('MOTOR2_ONLY', 0)} "
        f"NEITHER={transitions.get('NEITHER', 0)}"
    )


def raw_dict(r: Dict[str, Any]) -> Dict[str, Any]:
    raw = r.get("raw")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def mid_veto_stats(rows):
    variants = {
        "MID_ORIGINAL": new(),
        "KEEP_A": new(),
        "KEEP_AC": new(),
        "KEEP_ABC": new(),
    }
    eligible = 0
    missing_context = 0

    for r in rows:
        if not bool(r.get("base_mid_candidate")):
            continue

        raw = raw_dict(r)
        if not bool(raw.get("mid_veto_shadow_active")):
            missing_context += 1
            continue

        eligible += 1
        payout = si(r.get("payout_yen"))
        hit = str(r.get("ticket") or "") == str(r.get("result_ticket") or "")

        add(variants["MID_ORIGINAL"], True, hit, payout)
        add(variants["KEEP_A"], bool(raw.get("mid_keep_a_effective")), hit, payout)
        add(variants["KEEP_AC"], bool(raw.get("mid_keep_ac_effective")), hit, payout)
        add(variants["KEEP_ABC"], bool(raw.get("mid_keep_abc_effective")), hit, payout)

    return variants, eligible, missing_context


def mid_veto_scope(label: str, rows) -> int:
    variants, eligible, missing_context = mid_veto_stats(rows)
    original = variants["MID_ORIGINAL"]

    print(f"=== MID VETO FORWARD {label} ===")
    print(
        f"eligible_mid_rows={eligible} "
        f"base_mid_without_veto_context={missing_context}"
    )
    print(fmt("MID_ORIGINAL", original))

    for name in ("KEEP_A", "KEEP_AC", "KEEP_ABC"):
        s = variants[name]
        dropped_bets = original["bets"] - s["bets"]
        dropped_hits = original["hits"] - s["hits"]
        drop_rate = dropped_bets / original["bets"] * 100 if original["bets"] else 0.0
        print(fmt(name, s))
        print(
            f"{name}_DELTA: roi_delta={roi(s) - roi(original):+.2f}pt "
            f"dropped_bets={dropped_bets} dropped_hits={dropped_hits} "
            f"drop_rate={drop_rate:.2f}%"
        )

    return eligible


def prefinal(rows) -> None:
    pre: Dict[tuple[str, str], Dict[str, Any]] = {}
    final: Dict[tuple[str, str], Dict[str, Any]] = {}

    for r in rows:
        key = (str(r.get("race_id") or ""), str(r.get("ticket") or ""))
        target = final if str(r.get("window_name") or "") == "final" else pre
        if key not in target or str(r.get("snapshot_at") or "") >= str(target[key].get("snapshot_at") or ""):
            target[key] = r

    counts = defaultdict(int)
    matched = 0
    for key in set(pre) & set(final):
        p = pre[key]
        f = final[key]
        pm = bool(p.get("motor2_low_candidate")) or bool(p.get("motor2_mid_candidate"))
        fm = bool(f.get("motor2_low_candidate")) or bool(f.get("motor2_mid_candidate"))
        pb = bool(p.get("base_low_candidate")) or bool(p.get("base_mid_candidate"))
        fb = bool(f.get("base_low_candidate")) or bool(f.get("base_mid_candidate"))
        counts[f"M{int(pm)}{int(fm)}"] += 1
        counts[f"B{int(pb)}{int(fb)}"] += 1
        matched += 1

    print("=== PRE -> FINAL TRANSITION ===")
    print(f"matched_race_tickets={matched}")
    print(
        f"MOTOR2 kept={counts['M11']} dropped={counts['M10']} "
        f"added_final={counts['M01']} none={counts['M00']}"
    )
    print(
        f"BASE kept={counts['B11']} dropped={counts['B10']} "
        f"added_final={counts['B01']} none={counts['B00']}"
    )


def next_target(current: int, targets):
    return next((x for x in targets if current < x), None)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    print(f"OK report_v24_motor2_forward_performance_pg.py VERSION {VERSION}")
    print(f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN}")
    print("READ_ONLY=1 PROD_CHANGE=0 LINE=0 BUY=0 MID_VETO_PROD_CHANGE=0")

    raw = fetch_rows()
    rows = latest(raw)
    print(f"raw_rows={len(raw)} dedup_latest_rows={len(rows)}")

    pre = [
        r for r in rows
        if str(r.get("window_name") or "") in ("morning", "day", "night")
    ]
    final = [r for r in rows if str(r.get("window_name") or "") == "final"]

    scope("OVERALL", rows)
    scope("PRE ALL", pre)
    scope("FINAL", final)
    for window in ("morning", "day", "night"):
        scope(
            f"PRE {window.upper()}",
            [r for r in rows if str(r.get("window_name") or "") == window],
        )

    mid_eligible = mid_veto_scope("OVERALL", rows)
    mid_veto_scope("PRE ALL", pre)
    mid_veto_scope("FINAL", final)

    prefinal(rows)

    motor2_candidates = sum(
        1
        for r in rows
        if bool(r.get("motor2_low_candidate")) or bool(r.get("motor2_mid_candidate"))
    )
    motor2_next = next_target(motor2_candidates, REVIEW_TARGETS)
    mid_next = next_target(mid_eligible, MID_VETO_REVIEW_TARGETS)

    print("=== REVIEW PROGRESS ===")
    print(f"motor2_candidate_rows={motor2_candidates}")
    if motor2_next is None:
        print("next_review_target=completed")
    else:
        print(f"next_review_target={motor2_next} remaining={motor2_next - motor2_candidates}")

    print(f"mid_veto_evaluable_rows={mid_eligible}")
    if mid_next is None:
        print("mid_veto_next_review_target=completed")
    else:
        print(
            f"mid_veto_next_review_target={mid_next} "
            f"remaining={mid_next - mid_eligible}"
        )

    print("RESULT=PASS")


if __name__ == "__main__":
    main()
