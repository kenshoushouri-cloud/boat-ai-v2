# -*- coding: utf-8 -*-
"""Result-blind S03_M2_POSITIVE_V1 daily volume report.

Reads only:
- S03 pre-result identifiers/timestamps,
- race deadline,
- motor_place2_rate inputs required by the frozen M2-positive rule.

It deliberately does not select hit, payout, return, evaluation status, or any
result field. This is volume diagnostics only, not economics.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
W = (1.0, 0.6, 0.3)


def _force_read_only_pgoptions() -> None:
    current = os.environ.get("PGOPTIONS", "").strip()
    guard = "-c default_transaction_read_only=on"
    if guard not in current:
        os.environ["PGOPTIONS"] = f"{current} {guard}".strip()


def _si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def _sf(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except Exception:
        return None


def _jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def _lanes(value: Any) -> tuple[int, int, int] | None:
    xs = [int(x) for x in re.findall(r"[1-6]", str(value or ""))]
    if len(xs) < 3 or len(set(xs[:3])) != 3:
        return None
    return xs[0], xs[1], xs[2]


def motor2_score(entries: List[Mapping[str, Any]], ticket: Any) -> float | None:
    ls = _lanes(ticket)
    by = {_si(e.get("lane")): e for e in entries}
    if ls is None or set(by) != {1, 2, 3, 4, 5, 6}:
        return None

    vals: List[float] = []
    for lane in range(1, 7):
        x = _sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0.0 <= x <= 100.0:
            return None
        vals.append(x)

    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None

    z = {i + 1: (vals[i] - mu) / sd for i in range(6)}
    a, b, c = ls
    return W[0] * z[a] + W[1] * z[b] + W[2] * z[c]


def aggregate_s03_m2_volume(
    rows: Iterable[Mapping[str, Any]],
    entries_by_race: Mapping[str, List[Mapping[str, Any]]],
) -> Dict[str, Any]:
    daily: Dict[str, Counter[str]] = defaultdict(Counter)
    positive_race_days = set()

    for row in rows:
        race_id = str(row.get("race_id") or "")
        race_date = str(row.get("race_date") or "")
        if not race_id or not race_date:
            continue

        day = daily[race_date]
        day["source_s03_rows"] += 1

        snapshot_at = _jst(row.get("snapshot_at"))
        deadline_at = _jst(row.get("deadline_at"))
        if snapshot_at is None or deadline_at is None or snapshot_at >= deadline_at:
            day["timing_rejected"] += 1
            continue

        day["timing_valid"] += 1
        score = motor2_score(entries_by_race.get(race_id, []), row.get("ticket"))
        if score is None:
            day["missing_motor"] += 1
            continue

        day["motor_valid"] += 1
        if score > 0.0:
            day["m2_positive_rows"] += 1
            positive_race_days.add((race_date, race_id))

    out_daily: Dict[str, Any] = {}
    totals = Counter()
    for race_date in sorted(daily):
        day = daily[race_date]
        positives = sum(1 for d, _rid in positive_race_days if d == race_date)
        out_daily[race_date] = {
            **dict(sorted(day.items())),
            "m2_positive_unique_races": positives,
            "within_1_to_3_race_context": 1 <= positives <= 3,
            "above_3_race_context": positives > 3,
            "below_1_race_context": positives < 1,
        }
        totals.update(day)
        totals["m2_positive_unique_race_days"] += positives
        totals["days"] += 1
        if 1 <= positives <= 3:
            totals["days_within_1_to_3"] += 1
        elif positives > 3:
            totals["days_above_3"] += 1
        else:
            totals["days_below_1"] += 1

    return {
        "daily": out_daily,
        "totals": dict(sorted(totals.items())),
        "m2_positive_unique_races_across_dates": len(positive_race_days),
    }


def fetch_inputs(start_date: str, end_date: str):
    _force_read_only_pgoptions()
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select
                    s.race_id,
                    s.race_date,
                    s.ticket,
                    s.snapshot_at,
                    r.deadline_at
                from v2_candidate_filter_shadow s
                join v2_races r on r.race_id=s.race_id
                where s.rule_id='S03'
                  and s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (start_date, end_date),
            )
            rows = [dict(r) for r in cur.fetchall()]
            ids = sorted({str(r["race_id"]) for r in rows})
            entries_by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            if ids:
                cur.execute(
                    """
                    select race_id,lane,motor_place2_rate
                    from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane
                    """,
                    (ids,),
                )
                for entry in cur.fetchall():
                    entries_by_race[str(entry["race_id"])].append(dict(entry))
        conn.rollback()

    return rows, entries_by_race


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=os.environ.get("START_DATE"))
    parser.add_argument("--end-date", default=os.environ.get("END_DATE"))
    args = parser.parse_args()

    if not args.start_date or not args.end_date:
        raise SystemExit("START_DATE and END_DATE are required")
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required")

    rows, entries_by_race = fetch_inputs(args.start_date, args.end_date)
    summary = aggregate_s03_m2_volume(rows, entries_by_race)
    payload = {
        "contract": "S03_M2_RESULT_BLIND_VOLUME_V1",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "policy": "S03_M2_POSITIVE_V1",
        "selected_candidate_columns": [
            "race_id",
            "race_date",
            "ticket",
            "snapshot_at",
            "deadline_at",
        ],
        "selected_entry_columns": ["race_id", "lane", "motor_place2_rate"],
        "result_fields_read": False,
        "economics_claim": False,
        "promotion_claim": False,
        "operational_observation_target_races_per_day": {"min": 1, "max": 3},
        "target_is_not_a_selector_gate": True,
        "no_threshold_relaxation": True,
        "diagnostic_only": True,
        "purchase_action": False,
        "line_send": False,
        "db_write": False,
        **summary,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
