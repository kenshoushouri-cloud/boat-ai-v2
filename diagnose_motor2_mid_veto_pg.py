# -*- coding: utf-8 -*-
"""
diagnose_motor2_mid_veto_pg.py

MID Motor2 veto diagnostic (READ ONLY).

BASE MID candidates are fixed. This script evaluates three risk conditions:

A = BEST_RANK == R3
    The best Motor2 rank among the ticket's 3 lanes is exactly 3.

B = AVG_DIFF in [-10, -5)
    Ticket 3-lane average Motor2 minus race 6-lane average Motor2.

C = HEAD_DIFF in [-10, -5)
    Head-lane Motor2 minus race 6-lane average Motor2.

It reports:
- exclusive overlap groups
- each individual condition
- each OR-combination
- MID original vs MID after veto
- TRAIN / VALID / TEST / OOS1 / OOS2 / ALL
- dropped bets / dropped hits / drop rate
- race counts before/after

No DB update / LINE / BUY / production change.

Start Command:
    python -u diagnose_motor2_mid_veto_pg.py

Variables:
    MOTOR2_MID_VETO_START_DATE=2025-07-01
    MOTOR2_MID_VETO_END_DATE=2026-08-19
    MOTOR2_MID_VETO_UNIT_YEN=100
    MOTOR2_MID_VETO_REQUIRE_COMPLETE_MOTOR2=1
    MOTOR2_MID_VETO_PROGRESS_EVERY=5000
    MOTOR2_MID_VETO_MAX_RACES=0
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

import backtest_v24_motor2_historical_pg as bt
from db_pg import fetch_all

VERSION = "2026-08-21 motor2-mid-veto-diagnostic-v1"

START_DATE = os.getenv("MOTOR2_MID_VETO_START_DATE", "2025-07-01").strip()
END_DATE = os.getenv("MOTOR2_MID_VETO_END_DATE", "2026-08-19").strip()
UNIT_YEN = max(1, int(os.getenv("MOTOR2_MID_VETO_UNIT_YEN", "100")))
PROGRESS_EVERY = max(1, int(os.getenv("MOTOR2_MID_VETO_PROGRESS_EVERY", "5000")))
MAX_RACES = max(0, int(os.getenv("MOTOR2_MID_VETO_MAX_RACES", "0")))
REQUIRE_COMPLETE_MOTOR2 = os.getenv(
    "MOTOR2_MID_VETO_REQUIRE_COMPLETE_MOTOR2", "1"
).strip().lower() not in {"0", "false", "no", "off"}

PERIODS = ("ALL", "TRAIN", "VALID", "TEST", "OOS1", "OOS2")
PATTERNS = ("A", "B", "C", "A|B", "A|C", "B|C", "A|B|C")
EXCLUSIVE_GROUPS = (
    "NONE",
    "A_ONLY",
    "B_ONLY",
    "C_ONLY",
    "A_AND_B",
    "A_AND_C",
    "B_AND_C",
    "A_AND_B_AND_C",
)


def stat_new() -> Dict[str, int]:
    return {
        "bets": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "races": 0,
    }


def stat_add(s: Dict[str, int], hit: bool, payout: int) -> None:
    s["bets"] += 1
    s["investment"] += UNIT_YEN
    if hit:
        s["hits"] += 1
        s["return"] += payout


def roi(s: Dict[str, int]) -> float:
    return s["return"] / s["investment"] * 100 if s["investment"] else 0.0


def hit_rate(s: Dict[str, int]) -> float:
    return s["hits"] / s["bets"] * 100 if s["bets"] else 0.0


def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(bt.next_day(END_DATE), mx)
    if a >= b:
        return [], [], [], []

    ra, rb = a.replace("-", ""), b.replace("-", "")

    races = fetch_all(
        """
        select race_id,race_date,venue_id,venue_code,race_no
        from v2_races
        where race_date >= %s and race_date < %s
        order by race_date,venue_id,race_no
        """,
        (a, b),
    )
    entries = fetch_all(
        """
        select race_id,lane,racer_class,national_win_rate,
               national_place2_rate,local_place2_rate,avg_st,
               motor_place2_rate
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane
        """,
        (ra, rb),
    )
    results = fetch_all(
        """
        select race_id,trifecta_ticket,trifecta_payout_yen
        from v2_results
        where race_date >= %s and race_date < %s
          and result_status='official'
          and race_status='official'
          and trifecta_ticket is not null
          and trifecta_payout_yen > 0
        order by race_id
        """,
        (a, b),
    )
    odds = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
          and odds > 0
        order by race_id,ticket
        """,
        (ra, rb),
    )
    return races, entries, results, odds


def motor_rank_values(entries: List[Dict[str, Any]]) -> Tuple[Dict[int, int], Dict[int, float], float]:
    vals: List[Tuple[int, float]] = []
    for e in entries:
        lane = bt.si(e.get("lane"), 0)
        m2 = bt.valid_motor2(e.get("motor_place2_rate"))
        if 1 <= lane <= 6 and m2 is not None:
            vals.append((lane, float(m2)))

    vals.sort(key=lambda x: (-x[1], x[0]))
    ranks = {lane: idx for idx, (lane, _) in enumerate(vals, 1)}
    values = {lane: v for lane, v in vals}
    race_avg = sum(values.values()) / len(values) if values else 0.0
    return ranks, values, race_avg


def condition_flags(
    ticket: str,
    ranks: Dict[int, int],
    values: Dict[int, float],
    race_avg: float,
) -> Tuple[bool, bool, bool]:
    lanes = [int(x) for x in ticket.split("-")]

    ticket_ranks = [ranks[lane] for lane in lanes]
    ticket_values = [values[lane] for lane in lanes]

    best_rank = min(ticket_ranks)
    ticket_avg = sum(ticket_values) / 3.0
    avg_diff = ticket_avg - race_avg
    head_diff = ticket_values[0] - race_avg

    a = best_rank == 3
    b = -10.0 <= avg_diff < -5.0
    c = -10.0 <= head_diff < -5.0
    return a, b, c


def exclusive_group(a: bool, b: bool, c: bool) -> str:
    if a and b and c:
        return "A_AND_B_AND_C"
    if a and b:
        return "A_AND_B"
    if a and c:
        return "A_AND_C"
    if b and c:
        return "B_AND_C"
    if a:
        return "A_ONLY"
    if b:
        return "B_ONLY"
    if c:
        return "C_ONLY"
    return "NONE"


def veto_match(pattern: str, a: bool, b: bool, c: bool) -> bool:
    if pattern == "A":
        return a
    if pattern == "B":
        return b
    if pattern == "C":
        return c
    if pattern == "A|B":
        return a or b
    if pattern == "A|C":
        return a or c
    if pattern == "B|C":
        return b or c
    if pattern == "A|B|C":
        return a or b or c
    raise RuntimeError(f"unknown pattern={pattern}")


def fmt_stat(label: str, s: Dict[str, int]) -> str:
    return (
        f"{label}: bets={s['bets']} hits={s['hits']} "
        f"hit_rate={hit_rate(s):.3f}% investment={s['investment']} "
        f"return={s['return']} profit={s['return']-s['investment']} "
        f"ROI={roi(s):.2f}% races={s['races']}"
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")

    print(f"â diagnose_motor2_mid_veto_pg.py VERSION {VERSION}", flush=True)
    print(
        f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN} "
        f"REQUIRE_COMPLETE_MOTOR2={REQUIRE_COMPLETE_MOTOR2} "
        f"MAX_RACES={MAX_RACES or 'ALL'}",
        flush=True,
    )
    print("BASE_MID_FIXED=1 MOTOR2_CANDIDATE_CHANGE=0 DB_UPDATE=0 LINE=0 BUY=0", flush=True)
    print(
        "A=BEST_RANK_R3 B=AVG_DIFF[-10,-5) C=HEAD_DIFF[-10,-5)",
        flush=True,
    )

    original = {p: stat_new() for p in PERIODS}
    exclusive = {
        p: {g: stat_new() for g in EXCLUSIVE_GROUPS}
        for p in PERIODS
    }
    condition_stats = {
        p: {pat: stat_new() for pat in PATTERNS}
        for p in PERIODS
    }
    after = {
        p: {pat: stat_new() for pat in PATTERNS}
        for p in PERIODS
    }

    original_races: Dict[str, Set[str]] = {p: set() for p in PERIODS}
    group_races = {
        p: {g: set() for g in EXCLUSIVE_GROUPS}
        for p in PERIODS
    }
    condition_races = {
        p: {pat: set() for pat in PATTERNS}
        for p in PERIODS
    }
    after_races = {
        p: {pat: set() for pat in PATTERNS}
        for p in PERIODS
    }

    processed = 0
    candidate_rows = 0
    skipped_entries = skipped_motor2 = skipped_result = skipped_odds = 0

    for ms in bt.month_starts(START_DATE, END_DATE):
        races, entries, results, odds_rows = fetch_month(
            ms, bt.next_month_start(ms)
        )

        eb = defaultdict(list)
        for e in entries:
            eb[str(e.get("race_id") or "")].append(e)

        rb: Dict[str, Tuple[str, int]] = {}
        for r in results:
            rid = str(r.get("race_id") or "")
            t = bt.norm_ticket(r.get("trifecta_ticket"))
            payout = bt.si(r.get("trifecta_payout_yen"), 0)
            if rid and t and payout > 0:
                rb[rid] = (t, payout)

        ob: Dict[str, Dict[str, float]] = defaultdict(dict)
        for o in odds_rows:
            rid = str(o.get("race_id") or "")
            t = bt.norm_ticket(o.get("ticket"))
            odd = bt.sf(o.get("odds"), None)
            if rid and t and odd is not None and odd > 0:
                ob[rid][t] = float(odd)

        for race in races:
            if MAX_RACES and processed >= MAX_RACES:
                break

            rid = str(race.get("race_id") or "")
            ds = str(race.get("race_date") or "")[:10]
            venue = str(
                race.get("venue_id") or race.get("venue_code") or ""
            ).zfill(2)

            if rid not in rb:
                skipped_result += 1
                continue

            ent = eb.get(rid, [])
            lanes = {
                bt.si(e.get("lane"))
                for e in ent
                if 1 <= bt.si(e.get("lane")) <= 6
            }
            if len(ent) != 6 or lanes != bt.ALL_LANES:
                skipped_entries += 1
                continue

            valid_m2 = sum(
                bt.valid_motor2(e.get("motor_place2_rate")) is not None
                for e in ent
            )
            if REQUIRE_COMPLETE_MOTOR2 and valid_m2 != 6:
                skipped_motor2 += 1
                continue

            odds = ob.get(rid, {})
            if not bt.validate_odds(odds):
                skipped_odds += 1
                continue

            win_ticket, payout = rb[rid]
            market_rank = bt.rank_map(odds, reverse=False)
            base_ranks = bt.rank_map(
                bt.ticket_probs(ent, venue, 0.0),
                reverse=True,
            )

            mid_candidates = {
                t
                for t, odd in odds.items()
                if bt.is_mid(t, base_ranks[t], market_rank[t], float(odd))
            }

            processed += 1

            if not mid_candidates:
                if processed % PROGRESS_EVERY == 0:
                    print(
                        f"PROGRESS processed={processed} date={ds} race_id={rid}",
                        flush=True,
                    )
                continue

            p = bt.period(ds)
            ranks, values, race_avg = motor_rank_values(ent)

            for ticket in mid_candidates:
                candidate_rows += 1
                hit = ticket == win_ticket
                a, b, c = condition_flags(ticket, ranks, values, race_avg)
                grp = exclusive_group(a, b, c)

                for scope in ("ALL", p):
                    stat_add(original[scope], hit, payout)
                    original_races[scope].add(rid)

                    stat_add(exclusive[scope][grp], hit, payout)
                    group_races[scope][grp].add(rid)

                    for pat in PATTERNS:
                        matched = veto_match(pat, a, b, c)

                        if matched:
                            stat_add(condition_stats[scope][pat], hit, payout)
                            condition_races[scope][pat].add(rid)
                        else:
                            stat_add(after[scope][pat], hit, payout)
                            after_races[scope][pat].add(rid)

            if processed % PROGRESS_EVERY == 0:
                print(
                    f"PROGRESS processed={processed} date={ds} race_id={rid}",
                    flush=True,
                )

        if MAX_RACES and processed >= MAX_RACES:
            break

    for p in PERIODS:
        original[p]["races"] = len(original_races[p])
        for g in EXCLUSIVE_GROUPS:
            exclusive[p][g]["races"] = len(group_races[p][g])
        for pat in PATTERNS:
            condition_stats[p][pat]["races"] = len(condition_races[p][pat])
            after[p][pat]["races"] = len(after_races[p][pat])

    print("\n=== MID ORIGINAL ===", flush=True)
    for p in PERIODS:
        print(f"[{p}] {fmt_stat('MID_ORIGINAL', original[p])}", flush=True)

    print("\n=== MID VETO CONDITION OVERLAP ===", flush=True)
    for p in PERIODS:
        print(f"\n[{p}]", flush=True)
        for g in EXCLUSIVE_GROUPS:
            print("  " + fmt_stat(g, exclusive[p][g]), flush=True)

    print("\n=== MID VETO PATTERN COMPARISON ===", flush=True)
    for pat in PATTERNS:
        print(f"\n### VETO {pat}", flush=True)
        for p in PERIODS:
            before = original[p]
            dropped = condition_stats[p][pat]
            kept = after[p][pat]

            drop_rate = (
                dropped["bets"] / before["bets"] * 100
                if before["bets"] else 0.0
            )
            hit_loss_rate = (
                dropped["hits"] / before["hits"] * 100
                if before["hits"] else 0.0
            )
            roi_delta = roi(kept) - roi(before)

            print(
                f"[{p}] "
                f"before={before['bets']}/{before['hits']}/{roi(before):.2f}% "
                f"dropped={dropped['bets']}/{dropped['hits']}/{roi(dropped):.2f}% "
                f"after={kept['bets']}/{kept['hits']}/{roi(kept):.2f}% "
                f"ROI_DELTA={roi_delta:+.2f}pt "
                f"drop_rate={drop_rate:.2f}% "
                f"hit_loss_rate={hit_loss_rate:.2f}% "
                f"races_before={before['races']} "
                f"races_dropped={dropped['races']} "
                f"races_after={kept['races']}",
                flush=True,
            )

    print("\n=== TRAIN-BASED REVIEW ===", flush=True)
    ranked = []
    for pat in PATTERNS:
        train_before = original["TRAIN"]
        train_after = after["TRAIN"][pat]
        valid_before = original["VALID"]
        valid_after = after["VALID"][pat]
        test_before = original["TEST"]
        test_after = after["TEST"][pat]

        train_delta = roi(train_after) - roi(train_before)
        valid_delta = roi(valid_after) - roi(valid_before)
        test_delta = roi(test_after) - roi(test_before)
        train_hit_loss = (
            condition_stats["TRAIN"][pat]["hits"]
            / train_before["hits"] * 100
            if train_before["hits"] else 0.0
        )

        # Selection score intentionally does not use OOS1/OOS2.
        score = (
            min(valid_delta, test_delta),
            (valid_delta + test_delta) / 2.0,
            train_delta,
            -train_hit_loss,
        )
        ranked.append((score, pat))

    ranked.sort(reverse=True)

    for i, (_, pat) in enumerate(ranked, 1):
        print(
            f"{i:02d}. {pat} "
            f"TRAIN_DELTA={roi(after['TRAIN'][pat])-roi(original['TRAIN']):+.2f}pt "
            f"VALID_DELTA={roi(after['VALID'][pat])-roi(original['VALID']):+.2f}pt "
            f"TEST_DELTA={roi(after['TEST'][pat])-roi(original['TEST']):+.2f}pt "
            f"OOS1_DELTA={roi(after['OOS1'][pat])-roi(original['OOS1']):+.2f}pt "
            f"OOS2_DELTA={roi(after['OOS2'][pat])-roi(original['OOS2']):+.2f}pt "
            f"ALL_AFTER_ROI={roi(after['ALL'][pat]):.2f}%",
            flush=True,
        )

    print("\n=== AUDIT ===", flush=True)
    print(f"processed={processed}", flush=True)
    print(f"candidate_rows={candidate_rows}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_motor2={skipped_motor2}", flush=True)
    print(f"skipped_result={skipped_result}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()