# -*- coding: utf-8 -*-
"""Fixed K-source historical exhibition repair for 2026-08-30.

Plan mode is read-only.
Repair mode inserts only missing historical exhibition rows for four fixed K0 races.
No odds, PRE, LINE, FINAL, model, Shadow, Forward, Railway settings, or schedules.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

import audit_k_day_all_pg as kday
from db_pg import fetch_all, upsert_rows

VERSION = "2026-08-31 k-exhibition-gap-repair-v1"
TARGET_DATE = "2026-08-30"
START_KEY = "20260830"
END_KEY = "20260831"
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("K_EXH_REPAIR_MODE", "plan").strip().lower()

FIXED_RACES = {
    "20260830_05_08": {1},
    "20260830_05_10": {2},
    "20260830_19_10": {1},
    "20260830_23_11": {6},
}
EXPECTED_RECOVERABLE_ROWS = 20


def as_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_lanes(values: Set[int]) -> str:
    return ",".join(str(x) for x in sorted(values)) if values else "none"


def rank_diff(rows: List[Dict[str, Any]], key: str, rank_key: str, diff_key: str) -> None:
    vals = sorted(
        [(as_int(r["lane"]), r.get(key)) for r in rows if r.get(key) is not None],
        key=lambda x: x[1],
    )
    if not vals:
        return
    best = vals[0][1]
    ranks = {lane: i + 1 for i, (lane, _) in enumerate(vals)}
    for row in rows:
        if row.get(key) is not None:
            row[rank_key] = ranks[as_int(row["lane"])]
            row[diff_key] = round(float(row[key]) - float(best), 3)


def load_existing_lanes() -> Dict[str, Set[int]]:
    rows = fetch_all(
        """
        select race_id, lane
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label=%s
        order by race_id,lane
        """,
        (START_KEY, END_KEY, SNAPSHOT_LABEL),
    )
    out: Dict[str, Set[int]] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        lane = as_int(row.get("lane"))
        if rid and lane in range(1, 7):
            out.setdefault(rid, set()).add(lane)
    return out


def validate_schema(sample_keys: Set[str]) -> None:
    cols = fetch_all(
        """
        select column_name, is_nullable, column_default
        from information_schema.columns
        where table_schema='public'
          and table_name='v2_realtime_exhibition_snapshots'
        order by ordinal_position
        """
    )
    required = {
        str(x["column_name"])
        for x in cols
        if str(x.get("is_nullable") or "") == "NO"
        and x.get("column_default") is None
    }
    missing = required - sample_keys
    print(
        "K_EXH_REPAIR_SCHEMA="
        f"columns:{len(cols)} required_no_default:{','.join(sorted(required)) if required else 'none'} "
        f"missing_from_rows:{','.join(sorted(missing)) if missing else 'none'}",
        flush=True,
    )
    if missing:
        raise RuntimeError(f"required table columns missing from repair rows: {sorted(missing)}")


def load_k_candidates() -> Tuple[List[Dict[str, Any]], Dict[str, Set[int]]]:
    kday.TARGET_DATE = TARGET_DATE
    text = kday.get_k_text(TARGET_DATE)
    sections = kday.split_venue_sections(text.splitlines())

    candidates: List[Dict[str, Any]] = []
    unavailable: Dict[str, Set[int]] = {}
    seen_fixed: Set[str] = set()

    for section in sections:
        for race in kday.parse_section(section):
            rid = str(race["race_id"])
            if rid not in FIXED_RACES:
                continue
            seen_fixed.add(rid)
            rows: List[Dict[str, Any]] = []
            all_lanes: Set[int] = set()
            available_lanes: Set[int] = set()
            for entry in race.get("entries") or []:
                lane = as_int(entry.get("lane"))
                if lane not in range(1, 7):
                    continue
                all_lanes.add(lane)
                if entry.get("exhibition_time") is None:
                    continue
                available_lanes.add(lane)
                venue = str(race.get("venue_code") or "").zfill(2)
                row = {
                    "race_id": rid,
                    "race_date": TARGET_DATE,
                    "venue_id": venue,
                    "venue_code": venue,
                    "race_no": as_int(race.get("race_no")),
                    "snapshot_label": SNAPSHOT_LABEL,
                    "snapshot_at": now_iso(),
                    "source": "official_k_result_historical_repair",
                    "lane": lane,
                    "exhibition_course": entry.get("start_course"),
                    "exhibition_time": entry.get("exhibition_time"),
                    "start_timing": entry.get("start_timing"),
                    "raw": {
                        "source": "BOAT_RACE_K",
                        "finish_status": entry.get("finish_status"),
                        "racer_number": entry.get("racer_number"),
                        "repair_version": VERSION,
                    },
                    "updated_at": now_iso(),
                }
                rows.append(row)

            rank_diff(rows, "exhibition_time", "exhibition_time_rank", "exhibition_time_diff")
            rank_diff(rows, "start_timing", "start_timing_rank", "start_timing_diff")
            candidates.extend(rows)
            unavailable[rid] = all_lanes - available_lanes

    if seen_fixed != set(FIXED_RACES):
        raise RuntimeError(
            f"fixed races not all present in K source: missing={sorted(set(FIXED_RACES)-seen_fixed)}"
        )
    for rid, expected_unavailable in FIXED_RACES.items():
        actual = unavailable.get(rid, set())
        if actual != expected_unavailable:
            raise RuntimeError(
                f"K unavailable lane changed race={rid} expected={sorted(expected_unavailable)} actual={sorted(actual)}"
            )
    if len(candidates) != EXPECTED_RECOVERABLE_ROWS:
        raise RuntimeError(
            f"candidate row count changed expected={EXPECTED_RECOVERABLE_ROWS} actual={len(candidates)}"
        )
    return candidates, unavailable


def main() -> None:
    print(f"K_EXH_REPAIR_VERSION={VERSION}", flush=True)
    print(f"K_EXH_REPAIR_DATE={TARGET_DATE}", flush=True)
    print(f"K_EXH_REPAIR_MODE={MODE}", flush=True)
    print(
        "K_EXH_REPAIR_POLICY=fixed_4_races_historical_exhibition_only_no_odds_no_pre_no_line_no_final_no_model_no_shadow_forward",
        flush=True,
    )
    if MODE not in {"plan", "repair"}:
        raise RuntimeError("K_EXH_REPAIR_MODE must be plan or repair")

    candidates, unavailable = load_k_candidates()
    existing = load_existing_lanes()

    missing_rows = [
        row for row in candidates
        if as_int(row["lane"]) not in existing.get(str(row["race_id"]), set())
    ]

    for rid in sorted(FIXED_RACES):
        k_available = {
            as_int(row["lane"])
            for row in candidates
            if str(row["race_id"]) == rid
        }
        db_lanes = existing.get(rid, set())
        missing = k_available - db_lanes
        print(
            "K_EXH_REPAIR_RACE="
            f"race:{rid} k_available:{csv_lanes(k_available)} "
            f"k_unavailable:{csv_lanes(unavailable.get(rid, set()))} "
            f"db_hist:{csv_lanes(db_lanes)} missing:{csv_lanes(missing)}",
            flush=True,
        )

    print(
        "K_EXH_REPAIR_COUNTS="
        f"candidates:{len(candidates)} missing_now:{len(missing_rows)}",
        flush=True,
    )

    if candidates:
        validate_schema(set(candidates[0].keys()))

    if MODE == "plan":
        print("K_EXH_REPAIR_RESULT=PASS_PLAN_READ_ONLY", flush=True)
        return

    if not missing_rows:
        print("K_EXH_REPAIR_RESULT=ALREADY_COMPLETE", flush=True)
        return

    inserted = upsert_rows(
        "v2_realtime_exhibition_snapshots",
        missing_rows,
        ["race_id", "snapshot_label", "lane"],
    )
    print(f"K_EXH_REPAIR_WRITTEN={inserted}", flush=True)

    after = load_existing_lanes()
    remaining = 0
    total_hist = 0
    for rid in FIXED_RACES:
        k_available = {
            as_int(row["lane"])
            for row in candidates
            if str(row["race_id"]) == rid
        }
        remaining += len(k_available - after.get(rid, set()))
    all_hist = fetch_all(
        """
        select count(*) as n
        from v2_realtime_exhibition_snapshots
        where race_id >= %s and race_id < %s
          and snapshot_label=%s
        """,
        (START_KEY, END_KEY, SNAPSHOT_LABEL),
    )
    if all_hist:
        total_hist = as_int(all_hist[0].get("n"))

    print(
        "K_EXH_REPAIR_VERIFY="
        f"remaining:{remaining} hist_exhibition_rows:{total_hist}",
        flush=True,
    )
    if remaining != 0 or total_hist != 1004:
        raise RuntimeError(
            f"post-repair verification failed remaining={remaining} hist_rows={total_hist}"
        )

    print("K_EXH_REPAIR_RESULT=REPAIR_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
