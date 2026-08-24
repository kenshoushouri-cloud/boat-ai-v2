# -*- coding: utf-8 -*-
"""Read-only audit of realized upset frequency by inferred meet day and race number.

Primary upset definition: trifecta payout >= 10,000 yen ("manshu").
Secondary diagnostics: lane-1 loss, outer-lane winner (3-6), payout median/P90.

Meet day is inferred from consecutive official racing dates within each venue.
Venue date streaks longer than MAX_MEET_DAYS are treated as ambiguous and excluded
from meet-day comparisons rather than forcing a possibly false event boundary.

No odds snapshots are used, so this audit is not affected by historical base-odds
freeze limitations. Descriptive only: no filters, thresholds, model coefficients,
DB writes, Production/LINE changes, or promotion.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("UPSET_MEET_START", "2025-07-01"))
END = date.fromisoformat(os.getenv("UPSET_MEET_END", "2026-08-24"))
MAX_MEET_DAYS = 7
MANSHU_YEN = 10_000


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return max(0.0, center - half), min(1.0, center + half)


def day_bucket(day_no: int) -> str:
    if day_no == 1:
        return "D1"
    if day_no == 2:
        return "D2"
    if day_no in (3, 4):
        return "D3_4"
    return "D5_PLUS"


def race_band(race_no: int) -> str:
    if 1 <= race_no <= 4:
        return "R01_04"
    if 5 <= race_no <= 8:
        return "R05_08"
    return "R09_12"


def summarize(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rr = list(rows)
    n = len(rr)
    if not n:
        return {"n": 0}
    payouts = [float(r["payout"]) for r in rr]
    manshu = sum(1 for r in rr if float(r["payout"]) >= MANSHU_YEN)
    lane1_loss = sum(1 for r in rr if int(r["first_lane"]) != 1)
    outer_win = sum(1 for r in rr if int(r["first_lane"]) >= 3)
    lo, hi = wilson(manshu, n)
    by_venue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rr:
        by_venue[str(r["venue"])].append(r)
    venue_rates = [
        sum(float(x["payout"]) >= MANSHU_YEN for x in xs) / len(xs)
        for xs in by_venue.values()
        if xs
    ]
    return {
        "n": n,
        "manshu": manshu,
        "manshu_rate": manshu / n,
        "manshu_lo": lo,
        "manshu_hi": hi,
        "venue_equal_manshu": sum(venue_rates) / len(venue_rates) if venue_rates else 0.0,
        "lane1_loss": lane1_loss / n,
        "outer_win": outer_win / n,
        "median": pct(payouts, 0.50),
        "p90": pct(payouts, 0.90),
        "mean": sum(payouts) / n,
        "venues": len(by_venue),
    }


def emit(label: str, m: dict[str, Any], baseline: float) -> None:
    if not m.get("n"):
        print(f"UPSET_MEET={label} n:0", flush=True)
        return
    rel = m["manshu_rate"] / baseline if baseline > 0 else 0.0
    print(
        f"UPSET_MEET={label} n:{m['n']} venues:{m['venues']} "
        f"manshu:{m['manshu']} manshu_rate:{m['manshu_rate']*100:.2f}% "
        f"manshu95:{m['manshu_lo']*100:.2f}-{m['manshu_hi']*100:.2f}% rel_to_all:{rel:.3f} "
        f"venue_equal_manshu:{m['venue_equal_manshu']*100:.2f}% "
        f"lane1_loss:{m['lane1_loss']*100:.2f}% outer_win:{m['outer_win']*100:.2f}% "
        f"payout_median:{m['median']:.0f} payout_p90:{m['p90']:.0f} payout_mean:{m['mean']:.0f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("UPSET_MEET_MODE=read_only_realized_payout_descriptive_no_tuning", flush=True)
    print(f"UPSET_MEET_PERIOD={START}..{END}", flush=True)
    print(f"UPSET_MEET_PRIMARY=trifecta_payout_yen>={MANSHU_YEN}", flush=True)
    print("UPSET_MEET_DAY_INFERENCE=consecutive_official_venue_racing_dates_max7_ambiguous_long_streak_excluded", flush=True)
    print("UPSET_MEET_POLICY=no_odds_no_filter_selection_no_writes_no_production_no_line_no_promotion", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select q.race_id,q.race_date::date race_date,
                       lpad(coalesce(nullif(q.venue_id::text,''),nullif(q.venue_code::text,'')),2,'0') venue,
                       q.race_no::int race_no,
                       r.first_lane::int first_lane,
                       r.trifecta_payout_yen::float8 payout
                from v2_results r
                join v2_races q on q.race_id=r.race_id
                where q.race_date between %s and %s
                  and q.race_no between 1 and 12
                  and r.first_lane between 1 and 6
                  and r.trifecta_payout_yen is not null
                  and r.trifecta_payout_yen > 0
                  and coalesce(r.result_status,'')='official'
                  and coalesce(r.race_status,'')='official'
                order by venue,race_date,race_no
                """,
                (START, END),
            )
            raw = [dict(r) for r in cur.fetchall()]

    venue_dates: dict[str, list[date]] = defaultdict(list)
    for r in raw:
        venue_dates[str(r["venue"])].append(r["race_date"])
    venue_dates = {v: sorted(set(ds)) for v, ds in venue_dates.items()}

    day_map: dict[tuple[str, date], tuple[int, int]] = {}
    ambiguous_dates: set[tuple[str, date]] = set()
    streak_count = 0
    ambiguous_streaks = 0
    max_streak_seen = 0
    for venue, dates in venue_dates.items():
        streak: list[date] = []
        all_streaks: list[list[date]] = []
        for d in dates:
            if not streak or d == streak[-1] + timedelta(days=1):
                streak.append(d)
            else:
                all_streaks.append(streak)
                streak = [d]
        if streak:
            all_streaks.append(streak)
        for s in all_streaks:
            streak_count += 1
            max_streak_seen = max(max_streak_seen, len(s))
            if len(s) > MAX_MEET_DAYS:
                ambiguous_streaks += 1
                ambiguous_dates.update((venue, d) for d in s)
                continue
            for i, d in enumerate(s, start=1):
                day_map[(venue, d)] = (i, len(s))

    rows: list[dict[str, Any]] = []
    excluded_ambiguous = 0
    for r in raw:
        key = (str(r["venue"]), r["race_date"])
        if key in ambiguous_dates or key not in day_map:
            excluded_ambiguous += 1
            continue
        dno, meet_len = day_map[key]
        x = dict(r)
        x["meet_day"] = dno
        x["meet_len"] = meet_len
        x["day_bucket"] = day_bucket(dno)
        x["race_band"] = race_band(int(r["race_no"]))
        rows.append(x)

    allm = summarize(rows)
    baseline = float(allm.get("manshu_rate", 0.0))
    print(
        f"UPSET_MEET_COVERAGE=raw:{len(raw)} evaluated:{len(rows)} excluded_ambiguous:{excluded_ambiguous} "
        f"venue_streaks:{streak_count} ambiguous_streaks:{ambiguous_streaks} max_streak_seen:{max_streak_seen}",
        flush=True,
    )
    emit("ALL", allm, baseline)

    print("UPSET_MEET_SECTION=MEET_DAY_EXACT", flush=True)
    for dno in range(1, 8):
        emit(f"MEET_DAY:D{dno}", summarize(r for r in rows if r["meet_day"] == dno), baseline)

    print("UPSET_MEET_SECTION=RACE_NO_EXACT", flush=True)
    for rno in range(1, 13):
        emit(f"RACE_NO:R{rno:02d}", summarize(r for r in rows if int(r["race_no"]) == rno), baseline)

    print("UPSET_MEET_SECTION=DAY_BUCKET_X_RACE_NO", flush=True)
    for db in ("D1", "D2", "D3_4", "D5_PLUS"):
        for rno in range(1, 13):
            emit(
                f"CROSS:{db}_R{rno:02d}",
                summarize(r for r in rows if r["day_bucket"] == db and int(r["race_no"]) == rno),
                baseline,
            )

    print("UPSET_MEET_SECTION=DAY_BUCKET_X_RACE_BAND", flush=True)
    for db in ("D1", "D2", "D3_4", "D5_PLUS"):
        for rb in ("R01_04", "R05_08", "R09_12"):
            emit(
                f"CROSS_BAND:{db}_{rb}",
                summarize(r for r in rows if r["day_bucket"] == db and r["race_band"] == rb),
                baseline,
            )

    print("UPSET_MEET_INTERPRETATION=DESCRIPTIVE_HYPOTHESIS_CHECK_ONLY_REQUIRE_STABILITY_BEFORE_MODEL_USE", flush=True)
    print("UPSET_MEET_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("UPSET_MEET_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"UPSET_MEET_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
