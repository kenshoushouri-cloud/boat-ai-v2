# -*- coding: utf-8 -*-
"""Read-only Forward diagnostic: Opponent Pressure head-only by inferred meet day.

Purpose:
- explain whether recent head-only Forward deterioration, especially 2026-08-24
  R05-08, is associated with meet-day composition.
- preserve the already-fixed head-only mapping and coefficient exactly as-is.

Meet day is inferred from consecutive official venue racing dates using a 7-day
pre-period buffer. Streaks longer than 7 days are treated as ambiguous.

Descriptive only: no meet-day/race-band filters, no coefficient search, no DB
writes, no Production/LINE changes, no promotion.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict, Counter
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_trifecta_forward as naive
import opponent_pressure_v24_trifecta_head_only_forward as head

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_MEET_FORWARD_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_MEET_FORWARD_END", "2026-08-24"))
BUFFER_DAYS = 7
MAX_MEET_DAYS = 7
UNIT_PRESSURE_COEF = 1.0
EPS = 1e-15


def race_band(rno: int) -> str:
    if 1 <= rno <= 4:
        return "R01_04"
    if 5 <= rno <= 8:
        return "R05_08"
    if 9 <= rno <= 12:
        return "R09_12"
    return "R_OTHER"


def day_bucket(day_no: int) -> str:
    if day_no == 1:
        return "D1"
    if day_no == 2:
        return "D2"
    if day_no in (3, 4):
        return "D3_4"
    return "D5_PLUS"


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "brier_delta": mean([r["brier_plus"] - r["brier_base"] for r in rows]),
        "logloss_delta": mean([r["ll_plus"] - r["ll_base"] for r in rows]),
        "rank_delta": mean([r["rank_plus"] - r["rank_base"] for r in rows]),
        "lane1_win": mean([1.0 if r["winner_lane"] == 1 else 0.0 for r in rows]),
        "winner_norm_change": mean([r["winner_norm_change"] for r in rows]),
        "raw_delta_sum": mean([r["raw_delta_sum"] for r in rows]),
        "lane1_norm_change": mean([r["lane1_norm_change"] for r in rows]),
        "meet_days": Counter(int(r["meet_day"]) for r in rows),
        "venues": len(set(str(r["venue"]) for r in rows)),
    }


def emit(label: str, m: dict[str, Any]) -> None:
    if not m.get("n"):
        print(f"OPP_MEET_FORWARD={label} n:0", flush=True)
        return
    days = ",".join(f"D{k}:{v}" for k, v in sorted(m["meet_days"].items()))
    print(
        f"OPP_MEET_FORWARD={label} n:{m['n']} venues:{m['venues']} "
        f"brier_delta:{m['brier_delta']:+.8f} logloss_delta:{m['logloss_delta']:+.8f} "
        f"rank_delta:{m['rank_delta']:+.3f} lane1_win:{m['lane1_win']*100:.1f}% "
        f"winner_norm_change:{m['winner_norm_change']:+.6f} "
        f"lane1_norm_change:{m['lane1_norm_change']:+.6f} raw_delta_sum:{m['raw_delta_sum']:+.6f} "
        f"meet_days:{days}",
        flush=True,
    )


def infer_meet_days(official_dates: list[dict[str, Any]]) -> tuple[dict[tuple[str, date], int], set[tuple[str, date]], int]:
    by_venue: dict[str, list[date]] = defaultdict(list)
    for r in official_dates:
        by_venue[str(r["venue"])].append(r["race_date"])
    day_map: dict[tuple[str, date], int] = {}
    ambiguous: set[tuple[str, date]] = set()
    ambiguous_streaks = 0
    for venue, ds0 in by_venue.items():
        ds = sorted(set(ds0))
        streaks: list[list[date]] = []
        streak: list[date] = []
        for d in ds:
            if not streak or d == streak[-1] + timedelta(days=1):
                streak.append(d)
            else:
                streaks.append(streak)
                streak = [d]
        if streak:
            streaks.append(streak)
        for s in streaks:
            if len(s) > MAX_MEET_DAYS:
                ambiguous_streaks += 1
                ambiguous.update((venue, d) for d in s)
                continue
            for i, d in enumerate(s, 1):
                day_map[(venue, d)] = i
    return day_map, ambiguous, ambiguous_streaks


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_MEET_FORWARD_MODE=read_only_head_only_meet_day_diagnostic_no_tuning", flush=True)
    print(f"OPP_MEET_FORWARD_PERIOD={START}..{END}", flush=True)
    print(f"OPP_MEET_FORWARD_MAPPING=head_only_fixed_coef_{UNIT_PRESSURE_COEF:.1f}_second_third_v24_unchanged", flush=True)
    print(f"OPP_MEET_FORWARD_MEET_DAY=consecutive_official_venue_dates_buffer:{BUFFER_DAYS}_max:{MAX_MEET_DAYS}", flush=True)
    print("OPP_MEET_FORWARD_POLICY=no_meet_day_filter_no_race_band_filter_no_coefficient_search_no_writes_no_production_no_line", flush=True)

    query_start = START - timedelta(days=BUFFER_DAYS)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select distinct q.race_date::date race_date,
                       lpad(coalesce(nullif(q.venue_id::text,''),nullif(q.venue_code::text,'')),2,'0') venue
                from v2_results r
                join v2_races q on q.race_id=r.race_id
                where q.race_date between %s and %s
                  and coalesce(r.result_status,'')='official'
                  and coalesce(r.race_status,'')='official'
                order by venue,race_date
                """,
                (query_start, END),
            )
            official_dates = [dict(x) for x in cur.fetchall()]
            cur.execute(
                """
                select s.race_id,s.race_date::date race_date,s.model_version,s.train_end,
                       s.matched_opponents,s.base_win,s.adj_win,
                       r.first_lane,r.second_lane,r.third_lane,r.result_status,r.race_status,
                       q.venue_id,q.venue_code,q.race_no
                from v2_opponent_pressure_shadow_v2 s
                left join v2_results r on r.race_id=s.race_id
                left join v2_races q on q.race_id=s.race_id
                where s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (START, END),
            )
            shadows = [dict(x) for x in cur.fetchall()]
            ids = [str(x["race_id"]) for x in shadows]
            entries_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                cur.execute(
                    """
                    select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                           local_place2_rate,avg_st
                    from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane
                    """,
                    (ids,),
                )
                for e in cur.fetchall():
                    d = dict(e)
                    entries_by_race[str(d["race_id"])].append(d)

    day_map, ambiguous, ambiguous_streaks = infer_meet_days(official_dates)
    records: list[dict[str, Any]] = []
    skipped = pending = missing_entries = 0
    for s in shadows:
        lanes = [naive.si(s.get(k), 0) for k in ("first_lane", "second_lane", "third_lane")]
        if str(s.get("result_status") or "") != "official" or any(x == 0 for x in lanes):
            pending += 1
            continue
        if len(set(lanes)) != 3 or any(not 1 <= x <= 6 for x in lanes):
            skipped += 1
            continue
        if int(s.get("model_version") or 0) != 2 or s.get("train_end") >= s.get("race_date"):
            skipped += 1
            continue
        if not isinstance(s.get("base_win"), list) or not isinstance(s.get("adj_win"), list) or len(s["base_win"]) != 6 or len(s["adj_win"]) != 6:
            skipped += 1
            continue
        supports = s.get("matched_opponents")
        if not isinstance(supports, list) or len(supports) != 6 or any(int(x) < 4 for x in supports):
            skipped += 1
            continue
        venue = str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        key = (venue, s["race_date"])
        if key in ambiguous or key not in day_map:
            skipped += 1
            continue
        rid = str(s["race_id"])
        base_lane = naive.lane_probs(entries_by_race.get(rid, []), venue)
        if base_lane is None:
            missing_entries += 1
            continue
        delta = [naive.sf(s["adj_win"][i]) - naive.sf(s["base_win"][i]) for i in range(6)]
        adjusted_first = naive.norm([
            max(1e-12, min(.999, base_lane[i] + UNIT_PRESSURE_COEF * delta[i]))
            for i in range(6)
        ])
        pb = naive.pl_trifecta(base_lane)
        ph = head.head_only_trifecta(base_lane, adjusted_first)
        ticket = f"{lanes[0]}-{lanes[1]}-{lanes[2]}"
        wi = lanes[0] - 1
        rno = naive.si(s.get("race_no"), 0)
        dno = day_map[key]
        records.append({
            "race_date": str(s["race_date"]),
            "race_no": rno,
            "race_band": race_band(rno),
            "venue": venue,
            "meet_day": dno,
            "day_bucket": day_bucket(dno),
            "winner_lane": lanes[0],
            "brier_base": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in pb.items()),
            "brier_plus": sum((p - (1.0 if t == ticket else 0.0)) ** 2 for t, p in ph.items()),
            "ll_base": -math.log(max(EPS, pb.get(ticket, 0.0))),
            "ll_plus": -math.log(max(EPS, ph.get(ticket, 0.0))),
            "rank_base": float(naive.ticket_rank(pb, ticket)),
            "rank_plus": float(naive.ticket_rank(ph, ticket)),
            "winner_norm_change": adjusted_first[wi] - base_lane[wi],
            "lane1_norm_change": adjusted_first[0] - base_lane[0],
            "raw_delta_sum": sum(delta),
        })

    print(
        f"OPP_MEET_FORWARD_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} pending:{pending} "
        f"skipped:{skipped} missing_entries:{missing_entries} ambiguous_streaks:{ambiguous_streaks}",
        flush=True,
    )
    emit("OVERALL", summarize(records))

    print("OPP_MEET_FORWARD_SECTION=MEET_DAY_EXACT", flush=True)
    for dno in range(1, 8):
        emit(f"MEET_DAY:D{dno}", summarize([r for r in records if r["meet_day"] == dno]))

    print("OPP_MEET_FORWARD_SECTION=MEET_DAY_X_RACE_BAND", flush=True)
    for db in ("D1", "D2", "D3_4", "D5_PLUS"):
        for rb in ("R01_04", "R05_08", "R09_12"):
            emit(f"CROSS:{db}_{rb}", summarize([r for r in records if r["day_bucket"] == db and r["race_band"] == rb]))

    print("OPP_MEET_FORWARD_SECTION=DATE_2026_08_24_R05_08_BY_MEET_DAY", flush=True)
    target = [r for r in records if r["race_date"] == "2026-08-24" and r["race_band"] == "R05_08"]
    emit("TARGET:2026-08-24_R05_08_ALL", summarize(target))
    for dno in range(1, 8):
        emit(f"TARGET:2026-08-24_R05_08_D{dno}", summarize([r for r in target if r["meet_day"] == dno]))

    print("OPP_MEET_FORWARD_INTERPRETATION=COMPOSITION_DIAGNOSTIC_ONLY_NO_CONTEXT_RULE_SELECTION", flush=True)
    print("OPP_MEET_FORWARD_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_MEET_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_MEET_FORWARD_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
