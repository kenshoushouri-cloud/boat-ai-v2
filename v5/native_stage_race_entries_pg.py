"""V5 native single-race OFFICIAL racelist -> physical stage canary.

New collector makes its own official HTTP request, never invokes a legacy
collector, and writes only boat_data_stage.races / entries. It temporarily
reuses tested racelist *parser functions* (not legacy storage functions).
No automatic timer, results, odds, exhibition, bets or legacy writes.

PREVIEW is the default and has no database connection or writes.
APPLY intentionally refuses while the scheduled 2026-10-27 stage delta may
overwrite stage contents. It requires explicit gates and independent evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
import re
import subprocess
from typing import Any

JST = timezone(timedelta(hours=9))
RID = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
ALLOWED_COLUMNS = {
    "races": ("race_id", "race_date", "venue_code", "venue_id",
              "venue_name", "race_no", "race_name", "deadline_time",
              "deadline_at", "status", "data_quality_score",
              "missing_count", "updated_at"),
    "entries": ("race_id", "lane", "course", "racer_number", "racer_name",
                "racer_class", "racer_class_text", "branch", "origin",
                "f_count", "l_count", "avg_st", "national_win_rate",
                "national_place2_rate", "national_place3_rate",
                "local_win_rate", "local_place2_rate", "local_place3_rate",
                "motor_no", "motor_place2_rate", "motor_place3_rate",
                "boat_no", "boat_place2_rate", "boat_place3_rate",
                "recent_form", "updated_at"),
}
KEYS = {"races": ("race_id",), "entries": ("race_id", "lane")}
LOCK = 2026102503  # Same advisory lock as scheduled stage delta reconciliation.
STAGE_TIMER = "boat-v5-stage11-delta-20261027-recovery.timer"
STAGE_SERVICE = "boat-v5-stage11-delta-20261027-recovery.service"


def race_parts(race_id: str) -> tuple[str, str, int]:
    if not RID.fullmatch(race_id):
        raise ValueError("HOLD_INVALID_RACE_ID")
    day, venue, number = race_id.split("_")
    return f"{day[:4]}-{day[4:6]}-{day[6:]}", venue, int(number)


def validate_entries(race_id: str, entries: list[dict[str, Any]]) -> None:
    if len(entries) != 6 or {e.get("lane") for e in entries} != set(range(1, 7)):
        raise RuntimeError("HOLD_NOT_SIX_UNIQUE_LANES")
    racers = [e.get("racer_number") for e in entries]
    if any(type(n) is not int or n < 1 or n > 9999 for n in racers):
        raise RuntimeError("HOLD_INVALID_RACER_NUMBER")
    if len(set(racers)) != 6 or any(e.get("race_id") != race_id for e in entries):
        raise RuntimeError("HOLD_DUPLICATE_RACER_OR_BAD_RACE_ID")


def official_payload(race_id: str, html: str, captured: datetime):
    """Only the previously tested official racelist parser; zero DB writes."""
    import repair_month_all_pg as parser  # parser only; never process_race/upsert
    day, venue, race_no = race_parts(race_id)
    if parser._looks_no_race(html):
        raise RuntimeError("HOLD_NO_OFFICIAL_RACELIST")
    deadline_time = parser.parse_deadline_time(html, race_no)
    deadline_at = parser.make_deadline_at(day, deadline_time)
    if not deadline_time or not deadline_at:
        raise RuntimeError("HOLD_NO_VALID_OFFICIAL_DEADLINE")
    expiry = datetime.fromisoformat(deadline_at)
    if captured >= expiry - timedelta(seconds=180):
        raise RuntimeError("HOLD_RACE_TOO_LATE_FOR_CANARY")
    entries = parser.parse_entries(html, race_id)
    validate_entries(race_id, entries)
    now_iso = captured.isoformat()
    race = {
        "race_id": race_id, "race_date": day,
        "venue_code": venue, "venue_id": venue,
        "venue_name": parser.VENUE_NAMES.get(venue, venue),
        "race_no": race_no, "race_name": parser.parse_race_name(html),
        "deadline_time": deadline_time, "deadline_at": deadline_at,
        "status": "scheduled", "data_quality_score": 0,
        "missing_count": 0, "updated_at": now_iso,
    }
    for entry in entries:
        entry["updated_at"] = now_iso
    return race, entries


def official_fetch(race_id: str) -> tuple[str, datetime]:
    import requests
    day, venue, number = race_parts(race_id)
    url = ("https://www.boatrace.jp/owpc/pc/race/racelist"
           f"?rno={number}&jcd={venue}&hd={day.replace('-', '')}")
    with requests.Session() as session:
        resp = session.get(url, timeout=(8, 18), headers={
            "User-Agent": "Mozilla/5.0 (compatible; V5-stage-racelist-canary/1.0)"
        })
        resp.raise_for_status()
        if len(resp.content) > 1_500_000:
            raise RuntimeError("HOLD_OFFICIAL_PAGE_TOO_LARGE")
        captured = datetime.now(JST)
        return resp.text, captured


def blocked_by_stage_delta() -> None:
    # The nightly one-time sync's 03:05 start is already scheduled. Its
    # source-authoritative delta can undo/overwrite native V5 rows.
    now = datetime.now(JST)
    if now < datetime(2026, 10, 27, 6, 0, tzinfo=JST):
        raise RuntimeError("HOLD_NIGHT_STAGE_DELTA_PENDING_CHECK_27_OCT_AFTER_0600")
    if 3 <= now.hour < 6:
        raise RuntimeError("HOLD_STAGE_DELTA_WRITE_WINDOW")
    for unit in (STAGE_TIMER, STAGE_SERVICE):
        try:
            run = subprocess.run(
                ["systemctl", "is-active", unit],
                text=True, capture_output=True, timeout=2, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("HOLD_CANNOT_VERIFY_STAGE_DELTA_UNIT") from exc
        if run.returncode == 0 or run.stdout.strip() in {"active", "activating"}:
            raise RuntimeError("HOLD_STAGE_DELTA_UNIT_ACTIVE")
    if os.environ.get("V5_STAGE_DELTA_JOURNAL_VERIFIED") != "YES":
        raise RuntimeError("HOLD_STAGE_DELTA_JOURNAL_NOT_VERIFIED")


def apply_one(race: dict, entries: list[dict], now: datetime) -> tuple[int, int]:
    """Single transaction, insert-only, identity parity check, no old writes."""
    from psycopg import connect, sql
    from v5.direct_shared_primary_routes import canary_target
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_PG_ONLY")
    if os.environ.get("V5_NATIVE_CORE_STAGE_WRITE_APPROVED") != "YES":
        raise RuntimeError("HOLD_NO_EXPLICIT_CORE_WRITE_APPROVAL")
    if any(os.environ.get(x, "").upper() in {"YES", "TRUE", "ON", "1"}
           for x in ("BUY_ENABLED", "AUTO_BUY", "ENABLE_PURCHASE")):
        raise RuntimeError("HOLD_BUY_FLAG_PRESENT")
    blocked_by_stage_delta()
    # Both names are fixed; do not accept SQL identifiers from env or HTML.
    with connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5000ms'")
                cur.execute("SET LOCAL lock_timeout = '750ms'")
                cur.execute("SET LOCAL work_mem = '4MB'")
                cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK,))
                if not cur.fetchone()[0]:
                    raise RuntimeError("HOLD_STAGE_DELTA_ADVISORY_LOCK_BUSY")
                for family, source in (("races", "public.v2_races"),
                                       ("entries", "public.v2_race_entries")):
                    dst = f"boat_data_stage.{family}"
                    cur.execute("SELECT c.relkind FROM pg_class c WHERE c.oid=to_regclass(%s)",
                                (source,))
                    source_kind = cur.fetchone()
                    cur.execute("SELECT c.relkind FROM pg_class c WHERE c.oid=to_regclass(%s)",
                                (dst,))
                    stage_kind = cur.fetchone()
                    if (not source_kind or source_kind[0] not in ("r", "p")
                            or not stage_kind or stage_kind[0] not in ("r", "p")):
                        raise RuntimeError("HOLD_NOT_DISTINCT_PHYSICAL_STORAGE_" + family)
                    cur.execute("""SELECT attname FROM pg_attribute
                        WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped""",
                                (dst,))
                    columns = {r[0] for r in cur.fetchall()}
                    if not set(ALLOWED_COLUMNS[family]) <= columns:
                        raise RuntimeError("HOLD_STAGE_COLUMNS_MISSING_" + family)
                    cur.execute("""SELECT array_agg(a.attname ORDER BY k.ord)
                        FROM pg_index i
                        JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(num,ord)
                          ON k.ord <= i.indnkeyatts
                        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num
                        WHERE i.indrelid=to_regclass(%s)
                          AND i.indisunique AND i.indisvalid
                          AND i.indpred IS NULL AND i.indexprs IS NULL
                        GROUP BY i.indexrelid""", (dst,))
                    key_sets = {tuple(rec[0]) for rec in cur.fetchall()}
                    if KEYS[family] not in key_sets:
                        raise RuntimeError("HOLD_STAGE_CONFLICT_KEY_MISSING_" + family)
                    actual = canary_target(
                        source, env=os.environ, verified_physical=True,
                        verified_schema_and_keys=True, independent_native_writer=True,
                        legacy_destination_isolated=(source != dst),
                        live_buy_disabled=True)
                    if actual != dst:
                        raise RuntimeError("HOLD_UNEXPECTED_STAGE_DESTINATION")
                if datetime.now(JST) >= datetime.fromisoformat(race["deadline_at"]) - timedelta(seconds=180):
                    raise RuntimeError("HOLD_DEADLINE_EXPIRED_DURING_VALIDATION")
                inserted = {}
                for family, rows in (("races", [race]), ("entries", entries)):
                    cols = ALLOWED_COLUMNS[family]
                    target = sql.Identifier("boat_data_stage", family)
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING").format(
                        target,
                        sql.SQL(", ").join(map(sql.Identifier, cols)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in cols),
                        sql.SQL(", ").join(map(sql.Identifier, KEYS[family])),
                    )
                    inserted[family] = 0
                    for row in rows:
                        cur.execute(query, [row.get(k) for k in cols])
                        inserted[family] += cur.rowcount
                cur.execute("""SELECT lane, racer_number FROM boat_data_stage.entries
                               WHERE race_id=%s ORDER BY lane""", (race["race_id"],))
                saved = cur.fetchall()
                if saved != [(e["lane"], e["racer_number"]) for e in sorted(entries, key=lambda e:e["lane"])]:
                    raise RuntimeError("HOLD_STAGE_SIX_ENTRY_PARITY_ROLLBACK")
                cur.execute("""SELECT deadline_at FROM boat_data_stage.races WHERE race_id=%s""",
                            (race["race_id"],))
                actual_deadline = cur.fetchone()
                if not actual_deadline or actual_deadline[0] is None:
                    raise RuntimeError("HOLD_STAGE_RACE_DEADLINE_MISSING")
                # Presence + lane/racer identity checked; do not certify all content
                # or snapshot capture time here.
                return inserted["races"], inserted["entries"]


def main(argv=None) -> int:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--race-id", required=True)
    arg.add_argument("--apply", action="store_true")
    options = arg.parse_args(argv)
    race_parts(options.race_id)
    print("V5_OFFICIAL_NATIVE_CORE_MODE=" + ("CANARY_APPLY" if options.apply else "PREVIEW"), flush=True)
    html, captured = official_fetch(options.race_id)
    race, entries = official_payload(options.race_id, html, captured)
    print(f"V5_OFFICIAL_RACELIST_VALIDATED race={race['race_id']} entries={len(entries)} "
          f"captured={captured.isoformat()} deadline={race['deadline_at']}", flush=True)
    if not options.apply:
        print("V5_OFFICIAL_NATIVE_CORE_PREVIEW_NO_DB_NO_WRITES_NO_BUY", flush=True)
        return 0
    races_n, entries_n = apply_one(race, entries, captured)
    print(f"V5_CORE_STAGE_CANARY_COMMITTED race_insert={races_n} "
          f"entries_insert={entries_n} legacy_write=0 buy=OFF", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_NATIVE_CORE_HOLD " + type(exc).__name__ + ": " +
              str(exc).splitlines()[0][:140], flush=True)
        raise SystemExit(2)
