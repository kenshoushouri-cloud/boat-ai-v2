"""One-race V5 official-index discovery -> physical stage canary.

Official day index and official racelist only. Never reads public.v2_*.
Default PREVIEW: no DB access and no write. APPLY is opt-in after verified
stage-delta isolation; existing legacy collector remains unchanged.
Does not install timers, send messages, or buy tickets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import os

from v5.native_official_index_preview import (
    JST, choose_day, fetch_official_index, official_venues,
)
from v5.native_stage_race_entries_pg import (
    official_fetch, official_payload, apply_one, blocked_by_stage_delta,
)

REQUIRED = {
    "V5_NATIVE_CORE_STAGE_WRITE_APPROVED": "YES",
    "V5_SHARED_PRIMARY_MODE": "CANARY",
    "CONFIRM_V5_SHARED_PRIMARY_CANARY": "YES",
    "CONFIRM_LEGACY_WRITES_SEPARATELY": "YES",
}


def preflight_apply_without_http_or_db() -> None:
    """Fail before official HTTP if the request is not authorized."""
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_PG_ONLY")
    for key, required in REQUIRED.items():
        if os.environ.get(key) != required:
            raise RuntimeError("HOLD_MISSING_CANARY_GATE_" + key)
    for key in ("BUY_ENABLED", "AUTO_BUY", "ENABLE_PURCHASE"):
        if os.environ.get(key, "").upper() in {"1", "YES", "TRUE", "ON"}:
            raise RuntimeError("HOLD_BUY_MUST_BE_OFF")
    blocked_by_stage_delta()


def collect_single_official(day: str, max_venues: int):
    """Bounded site traffic: 1 day index plus <=3 individual 1R pages."""
    if not 1 <= max_venues <= 3:
        raise ValueError("HOLD_MAX_VENUES_1_TO_3")
    official_index = fetch_official_index(day)
    venues = official_venues(official_index, day)
    print("V5_DIRECT_OFFICIAL_VENUES=" + str(len(venues)), flush=True)
    if not venues:
        print("HOLD_NO_OFFICIAL_VENUES", flush=True)
        return None
    for venue in venues[:max_venues]:
        rid = f"{day}_{venue}_01"
        try:
            html, captured = official_fetch(rid)
            race, entries = official_payload(rid, html, captured)
        except Exception as exc:
            print("V5_DIRECT_RACE_SKIP " + rid + " " +
                  type(exc).__name__ + ":" + str(exc).splitlines()[0][:100],
                  flush=True)
            continue
        if race["race_id"] != rid or race["race_date"] != (
            f"{day[:4]}-{day[4:6]}-{day[6:]}"
        ) or len(entries) != 6:
            raise RuntimeError("HOLD_UNEXPECTED_OFFICIAL_RACE_IDENTITY")
        return race, entries, captured
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", default=None, help="JST today or tomorrow YYYYMMDD")
    parser.add_argument("--apply", action="store_true",
                        help="one-race INSERT-only stage canary, OFF by default")
    parser.add_argument("--max-venues", type=int, default=3, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    day = choose_day(datetime.now(JST), args.day)
    if args.apply:
        preflight_apply_without_http_or_db()
    print("V5_NATIVE_OFFICIAL_STAGE_MODE=" +
          ("ONE_RACE_CANARY" if args.apply else "PREVIEW"), flush=True)
    print("V5_NATIVE_OFFICIAL_STAGE_DAY=" + day, flush=True)
    sample = collect_single_official(day, args.max_venues)
    if sample is None:
        print("V5_NATIVE_STAGE_HOLD_NO_VALID_OFFICIAL_1R_NO_WRITES",
              flush=True)
        return 3 if args.apply else 0
    race, entries, captured = sample
    print("V5_NATIVE_STAGE_OFFICIAL_VALIDATED race=" + race["race_id"] +
          " entries=6 captured=" + captured.isoformat() +
          " deadline=" + race["deadline_at"], flush=True)
    if not args.apply:
        print("V5_NATIVE_STAGE_PREVIEW_NO_DB_NO_WRITES_NO_BUY", flush=True)
        return 0
    n_races, n_entries = apply_one(race, entries, captured)
    print("V5_NATIVE_STAGE_CANARY_COMMITTED race_insert=" +
          str(n_races) + " entries_insert=" + str(n_entries) +
          " legacy_write=0 buy=OFF", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_NATIVE_STAGE_STOP " + type(exc).__name__ + ":"
              + str(exc).splitlines()[0][:150], flush=True)
        raise SystemExit(2)
