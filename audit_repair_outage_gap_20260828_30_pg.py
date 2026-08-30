# -*- coding: utf-8 -*-
"""
audit_repair_outage_gap_20260828_30_pg.py

Fixed outage-gap audit/repair for Railway DB outage dates 2026-08-28..2026-08-30.

Safety:
- Allowed dates are hard-coded.
- Audit mode is read-only.
- Repair mode does not call PRE/FINAL/LINE/purchase/model code.
- Core race/entry pages are refreshed for the selected date.
- Results are repaired only when v2_results has no row for the race.
- Odds are repaired only when v2_odds_trifecta has zero rows for the race.
  Existing partial/complete odds races are never touched by this script.
- Historical beforeinfo is written only with snapshot_label=historical.
- No Shadow/Forward/live evidence is recreated.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from db_pg import fetch_all, fetch_one

VERSION = "2026-08-31 outage-gap-repair-v1"
ALLOWED_DATES = ("2026-08-28", "2026-08-29", "2026-08-30")
MODE = os.getenv("OUTAGE_GAP_MODE", "audit").strip().lower()
TARGET_DATE = os.getenv("OUTAGE_GAP_DATE", "").strip()
RUN_BEFOREINFO = os.getenv("OUTAGE_GAP_BEFOREINFO", "1").strip().lower() in {
    "1", "true", "yes", "on"
}


def as_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def ymd(date_str: str) -> str:
    return date_str.replace("-", "")


def race_ids(date_str: str) -> list[str]:
    return [
        str(r["race_id"])
        for r in fetch_all(
            """
            select race_id
            from v2_races
            where race_date=%s
            order by venue_id, race_no
            """,
            (date_str,),
        )
        if r.get("race_id")
    ]


def missing_result_ids(date_str: str) -> list[str]:
    return [
        str(r["race_id"])
        for r in fetch_all(
            """
            select r.race_id
            from v2_races r
            left join v2_results rs on rs.race_id=r.race_id
            where r.race_date=%s
              and rs.race_id is null
            order by r.venue_id, r.race_no
            """,
            (date_str,),
        )
    ]


def odds_state(date_str: str) -> tuple[list[str], list[str], list[str]]:
    rows = fetch_all(
        """
        with oc as (
            select race_id, count(distinct ticket) as ticket_count
            from v2_odds_trifecta
            where race_id >= %s and race_id < %s
            group by race_id
        )
        select r.race_id, coalesce(oc.ticket_count,0) as ticket_count
        from v2_races r
        left join oc on oc.race_id=r.race_id
        where r.race_date=%s
        order by r.venue_id, r.race_no
        """,
        (ymd(date_str), str(int(ymd(date_str)) + 1), date_str),
    )
    zero, partial, complete = [], [], []
    for row in rows:
        rid = str(row["race_id"])
        n = as_int(row.get("ticket_count"))
        if n == 0:
            zero.append(rid)
        elif n in (120, 60, 24):
            complete.append(rid)
        else:
            partial.append(rid)
    return zero, partial, complete


def historical_counts(date_str: str) -> dict[str, int]:
    start = ymd(date_str)
    end = str(int(start) + 1)
    tables = {
        "hist_weather": "v2_realtime_weather_snapshots",
        "hist_exhibition": "v2_realtime_exhibition_snapshots",
        "hist_race_condition": "v2_realtime_race_condition_snapshots",
        "hist_racer_condition": "v2_realtime_racer_condition_snapshots",
    }
    out: dict[str, int] = {}
    for key, table in tables.items():
        try:
            row = fetch_one(
                f"""
                select count(*) as n
                from {table}
                where race_id >= %s and race_id < %s
                  and snapshot_label='historical'
                """,
                (start, end),
            ) or {}
            out[key] = as_int(row.get("n"))
        except Exception:
            out[key] = -1
    return out


def audit(date_str: str) -> dict[str, Any]:
    rr = fetch_one(
        """
        select count(*) as races,
               count(*) filter(where deadline_at is not null) as deadline_ready
        from v2_races
        where race_date=%s
        """,
        (date_str,),
    ) or {}
    er = fetch_one(
        """
        select count(*) as entry_rows,
               count(distinct race_id) as entry_races
        from v2_race_entries
        where race_id >= %s and race_id < %s
        """,
        (ymd(date_str), str(int(ymd(date_str)) + 1)),
    ) or {}
    full6 = fetch_one(
        """
        select count(*) as full6
        from (
            select race_id
            from v2_race_entries
            where race_id >= %s and race_id < %s
            group by race_id
            having count(*)=6
        ) x
        """,
        (ymd(date_str), str(int(ymd(date_str)) + 1)),
    ) or {}
    rs = fetch_one(
        """
        select count(*) as result_rows,
               count(*) filter(
                   where trifecta_ticket is not null
                     and trifecta_payout_yen > 0
               ) as valid_results
        from v2_results
        where race_id >= %s and race_id < %s
        """,
        (ymd(date_str), str(int(ymd(date_str)) + 1)),
    ) or {}
    zero, partial, complete = odds_state(date_str)
    hist = historical_counts(date_str)
    out = {
        "date": date_str,
        "races": as_int(rr.get("races")),
        "deadline_ready": as_int(rr.get("deadline_ready")),
        "entry_rows": as_int(er.get("entry_rows")),
        "entry_races": as_int(er.get("entry_races")),
        "full6": as_int(full6.get("full6")),
        "result_rows": as_int(rs.get("result_rows")),
        "valid_results": as_int(rs.get("valid_results")),
        "odds_zero": len(zero),
        "odds_partial": len(partial),
        "odds_complete": len(complete),
        "missing_results": len(missing_result_ids(date_str)),
        **hist,
    }
    print(
        "OUTAGE_GAP_AUDIT "
        + " ".join(f"{k}={v}" for k, v in out.items()),
        flush=True,
    )
    if partial:
        print(
            "OUTAGE_GAP_PARTIAL_ODDS "
            f"date={date_str} count={len(partial)} "
            f"sample={','.join(partial[:20])}",
            flush=True,
        )
    return out


def run_child(script: str, env: dict[str, str], title: str) -> None:
    base = Path(__file__).resolve().parent
    path = base / script
    if not path.exists():
        raise FileNotFoundError(path)
    child = os.environ.copy()
    child.update(env)
    child["PYTHONUNBUFFERED"] = "1"
    print(f"OUTAGE_GAP_STAGE_START title={title}", flush=True)
    p = subprocess.run(
        [sys.executable, "-u", str(path)],
        cwd=str(base),
        env=child,
        text=True,
        check=False,
    )
    print(
        f"OUTAGE_GAP_STAGE_END title={title} returncode={p.returncode}",
        flush=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"{title} failed returncode={p.returncode}")


def repair(date_str: str) -> None:
    # Phase 1: refresh only race-card/static entry data for this date.
    run_child(
        "repair_month_all_pg.py",
        {
            "REPAIR_START_DATE": date_str,
            "REPAIR_END_DATE": date_str,
            "REPAIR_DO_RACES": "1",
            "REPAIR_DO_RESULTS": "0",
            "REPAIR_DO_ODDS": "0",
            "REPAIR_WORKERS": "4",
            "REPAIR_ODDS_WORKERS": "1",
            "REPAIR_SLEEP_SEC": "0.1",
            "REPAIR_SOURCE": "outage_gap_repair_20260828_30",
        },
        "race_entry_refresh",
    )

    # Phase 2: only races with no v2_results row.
    missing_results = missing_result_ids(date_str)
    print(
        f"OUTAGE_GAP_RESULT_TARGETS date={date_str} count={len(missing_results)}",
        flush=True,
    )
    if missing_results:
        run_child(
            "repair_month_all_pg.py",
            {
                "REPAIR_START_DATE": date_str,
                "REPAIR_END_DATE": date_str,
                "REPAIR_RACE_IDS": ",".join(missing_results),
                "REPAIR_DO_RACES": "0",
                "REPAIR_DO_RESULTS": "1",
                "REPAIR_DO_ODDS": "0",
                "REPAIR_WORKERS": "4",
                "REPAIR_ODDS_WORKERS": "1",
                "REPAIR_SLEEP_SEC": "0.1",
                "REPAIR_SOURCE": "outage_gap_repair_20260828_30",
            },
            "missing_results_only",
        )

    # Phase 3: only races with zero odds rows. Existing partial/complete rows are preserved.
    zero_odds, partial_odds, _ = odds_state(date_str)
    print(
        f"OUTAGE_GAP_ZERO_ODDS_TARGETS date={date_str} count={len(zero_odds)}",
        flush=True,
    )
    print(
        f"OUTAGE_GAP_PARTIAL_ODDS_PRESERVED date={date_str} count={len(partial_odds)}",
        flush=True,
    )
    if zero_odds:
        run_child(
            "repair_month_all_pg.py",
            {
                "REPAIR_START_DATE": date_str,
                "REPAIR_END_DATE": date_str,
                "REPAIR_RACE_IDS": ",".join(zero_odds),
                "REPAIR_DO_RACES": "0",
                "REPAIR_DO_RESULTS": "0",
                "REPAIR_DO_ODDS": "1",
                "ODDS_IS_FINAL": "1",
                "REPAIR_WORKERS": "2",
                "REPAIR_ODDS_WORKERS": "2",
                "REPAIR_SLEEP_SEC": "0.1",
                "REPAIR_SOURCE": "outage_gap_repair_20260828_30",
            },
            "zero_odds_only",
        )

    # Phase 4: reconstruct historical-only beforeinfo snapshots.
    if RUN_BEFOREINFO:
        run_child(
            "backfill_historical_beforeinfo_pg.py",
            {
                "HIST_START_DATE": date_str,
                "HIST_END_DATE": date_str,
                "HIST_SNAPSHOT_LABEL": "historical",
                "HIST_WORKERS": "4",
                "HIST_REQUIRE_SIX_EXHIBITION": "1",
            },
            "historical_beforeinfo",
        )

    audit(date_str)


def main() -> None:
    print(f"OUTAGE_GAP_VERSION={VERSION}", flush=True)
    print(
        "OUTAGE_GAP_POLICY=fixed_dates_no_line_no_model_no_shadow_forward_recreation",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    if MODE == "audit":
        for d in ALLOWED_DATES:
            audit(d)
        print("OUTAGE_GAP_RESULT=PASS_READ_ONLY", flush=True)
        return

    if MODE != "repair":
        raise RuntimeError("OUTAGE_GAP_MODE must be audit or repair")
    if TARGET_DATE not in ALLOWED_DATES:
        raise RuntimeError("OUTAGE_GAP_DATE is not in fixed allowlist")

    print(f"OUTAGE_GAP_REPAIR_DATE={TARGET_DATE}", flush=True)
    repair(TARGET_DATE)
    print("OUTAGE_GAP_RESULT=REPAIR_COMPLETE_VERIFY_AUDIT", flush=True)


if __name__ == "__main__":
    main()
