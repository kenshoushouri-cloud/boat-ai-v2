"""Fixed-date, SELECT-only diagnostic of the 2026-09-08 odds gaps.

This is research evidence, never a backtest, production or purchase approval.
No HTTP, DDL, repair, notification, model or production-decision calls.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

TARGET_DATE = "2026-09-08"
JST = timezone(timedelta(hours=9))
ALL_TICKETS = tuple(
    f"{a}-{b}-{c}" for a, b, c in itertools.permutations(range(1, 7), 3)
)
# Deadline times transcribed from the 20:55 JST Issue #42 health observation.
# These are reference observations, not a guarantee of the official deadline.
REFERENCE_DEADLINES = {
    "20260908_10_02": "08:58", "20260908_14_02": "09:10",
    "20260908_10_03": "09:24", "20260908_14_03": "09:36",
    "20260908_11_02": "11:06", "20260908_11_03": "11:36",
    "20260908_11_04": "12:03", "20260908_03_03": "12:08",
    "20260908_13_05": "12:28", "20260908_11_05": "12:32",
    "20260908_03_04": "12:35", "20260908_13_06": "12:56",
    "20260908_11_06": "13:01", "20260908_11_07": "13:38",
    "20260908_13_08": "14:03", "20260908_11_08": "14:09",
    "20260908_03_08": "14:24", "20260908_13_09": "14:33",
    "20260908_11_09": "14:40",
}
TARGET_RACES = tuple(REFERENCE_DEADLINES)
assert len(TARGET_RACES) == len(set(TARGET_RACES)) == 19
REFERENCE = "Issue #42, 2026-09-08 20:55 JST health observation"
MAX_ROWS = 5000


def as_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # An unzoned database timestamp is not independently interpretable.
    return None if dt.tzinfo is None else dt.astimezone(JST)


def iso(value: Any) -> str | None:
    dt = as_time(value)
    return dt.isoformat() if dt else None


def reference_deadline(race_id: str) -> datetime:
    return datetime.fromisoformat(
        f"{TARGET_DATE}T{REFERENCE_DEADLINES[race_id]}:00+09:00"
    )


def ticket_status(tickets: list[str]) -> dict:
    """All 19 reference races have six entrants; do not infer scratches."""
    counts = Counter(str(t).strip() for t in tickets)
    actual, expected = set(counts), set(ALL_TICKETS)
    return {
        "expected": 120, "observed": len(tickets), "distinct": len(actual),
        "missing": sorted(expected - actual),
        "unexpected": sorted(actual - expected),
        "duplicates": sum(n - 1 for n in counts.values()),
        "complete": actual == expected and all(n == 1 for n in counts.values()),
    }


def numeric_quality(values: Any) -> dict:
    """Check every odds value; NaN and infinity must not pass."""
    if not isinstance(values, (list, tuple)):
        return {"valid": False, "count": 0, "invalid": ["not_an_array"]}
    invalid = []
    for index, value in enumerate(values):
        try:
            number = float(value)
            if not math.isfinite(number) or number <= 0:
                invalid.append(index)
        except (TypeError, ValueError, OverflowError):
            invalid.append(index)
    return {"valid": len(values) == 120 and not invalid,
            "count": len(values), "invalid": invalid}


def review_snapshot(row: dict, deadline: datetime) -> dict:
    """A saved candidate is not independently authenticated market evidence."""
    captured = as_time(row.get("captured_at"))
    stored_deadline = as_time(row.get("deadline_at"))
    created = as_time(row.get("created_at"))
    phase, source = row.get("phase"), row.get("source")
    quality = numeric_quality(row.get("odds"))
    reasons = []
    if phase not in ("early", "late"):
        reasons.append("unknown_phase")
    if source != "official_odds3t":
        reasons.append("source_not_verified")
    if row.get("schema_version") != 3:
        reasons.append("schema_version_unverified")
    if not quality["valid"]:
        reasons.append("invalid_odds_vector")
    if captured is None or captured >= deadline:
        reasons.append("not_proven_before_reference_deadline")
    if stored_deadline != deadline:
        reasons.append("reference_deadline_mismatch")
    if created is None or captured is None or created < captured or created >= deadline:
        reasons.append("created_at_not_proven_before_deadline")
    if captured is not None:
        lead = (deadline - captured).total_seconds() / 60
        if phase == "early" and not 20 <= lead <= 30:
            reasons.append("outside_early_window")
        if phase == "late" and not 0 <= lead <= 7:
            reasons.append("outside_late_window")
    return {
        "phase": phase, "captured_at": iso(row.get("captured_at")),
        "created_at": iso(row.get("created_at")),
        "stored_deadline_at": iso(row.get("deadline_at")),
        "source": source, "schema_version": row.get("schema_version"),
        "odds_quality": quality,
        "status": "RECORDED_PREDEADLINE_CANDIDATE" if not reasons else "UNVERIFIED",
        "reasons": reasons,
        "provenance": "stored_metadata_only_not_independently_authenticated",
    }


def analyze(races: list[dict], entries: list[dict], base: list[dict],
            snapshots: list[dict], schema: dict) -> dict:
    grouped = defaultdict(list)
    for row in base:
        grouped[str(row["race_id"])].append(row)
    snap_by = defaultdict(list)
    for row in snapshots:
        snap_by[str(row["race_id"])].append(row)
    by_race = {str(row["race_id"]): row for row in races}
    entry_by = defaultdict(list)
    for row in entries:
        entry_by[str(row["race_id"])].append(row.get("lane"))
    frequencies, report = Counter(), []
    for rid in TARGET_RACES:
        deadline = reference_deadline(rid)
        race = by_race.get(rid)
        rows = grouped[rid]
        status = ticket_status([r.get("ticket", "") for r in rows])
        frequencies.update(status["missing"])
        entry_lanes = entry_by[rid]
        entry_status = "FULL6" if sorted(entry_lanes) == list(range(1, 7)) else "UNVERIFIED"
        stored_deadline = as_time(race.get("deadline_at")) if race else None
        times = [as_time(r.get("fetched_at")) for r in rows]
        times = [t for t in times if t is not None]
        evidence = [review_snapshot(s, deadline) for s in snap_by[rid]]
        report.append({
            "race_id": rid, "race_found": race is not None,
            "reference_deadline_at": deadline.isoformat(),
            "db_deadline_at": stored_deadline.isoformat() if stored_deadline else None,
            "deadline_matches_reference": stored_deadline == deadline,
            "entry_lanes": entry_lanes, "entry_status": entry_status,
            "base": status,
            "base_fetched_at_min": min(times).isoformat() if times else None,
            "base_fetched_at_max": max(times).isoformat() if times else None,
            "base_timestamp_semantics": "current_saved_value_not_first_observation",
            "base_final_flags": dict(Counter(str(r.get("is_final")) for r in rows)),
            "snapshots": evidence,
            "predeadline_evidence": "RECORDED_CANDIDATE" if any(
                e["status"] == "RECORDED_PREDEADLINE_CANDIDATE" for e in evidence
            ) else "UNKNOWN",
            "independent_source_verification": "NOT_PERFORMED",
            "root_cause": "UNDETERMINED",
        })
    return {
        "audit_date": TARGET_DATE, "reference": REFERENCE,
        "scope": "fixed_19_races_expected_120_each",
        "mode": "read_only_no_http_no_writes", "schema": schema,
        "races": report, "missing_ticket_frequency": dict(sorted(frequencies.items())),
        "root_cause": "UNDETERMINED", "production_promotion": "BLOCKED",
        "historical_roi_approval": "BLOCKED",
    }


def read_database(url: str) -> dict:
    import psycopg
    from psycopg.rows import dict_row
    # Both the session and the transaction are read-only. The role still needs
    # the least privileges available in the existing environment.
    with psycopg.connect(url, row_factory=dict_row, autocommit=False,
                         connect_timeout=10, application_name="odds_evidence_20260908") as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '15000ms'")
            cur.execute("SET LOCAL lock_timeout = '2000ms'")
            cur.execute("SET LOCAL idle_in_transaction_session_timeout = '30000ms'")
            def read(query: str, params: tuple = ()) -> list[dict]:
                cur.execute(query, params)
                rows = cur.fetchmany(MAX_ROWS + 1)
                if len(rows) > MAX_ROWS:
                    raise RuntimeError("Audit row limit exceeded")
                return [dict(row) for row in rows]
            schema_rows = read("""SELECT table_name,column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name IN
                ('v2_races','v2_race_entries','v2_odds_trifecta','v2_bao_market_shadow_snapshots')""")
            schema = defaultdict(set)
            for row in schema_rows:
                schema[row["table_name"]].add(row["column_name"])
            required = {
                "v2_races": {"race_id", "race_date", "deadline_at"},
                "v2_race_entries": {"race_id", "lane"},
                "v2_odds_trifecta": {"race_id", "ticket", "fetched_at", "is_final"},
            }
            for table, cols in required.items():
                if not cols <= schema[table]:
                    raise RuntimeError(f"Missing required columns: {table}")
            snapshot_cols = {"race_id", "phase", "captured_at", "created_at", "deadline_at", "odds", "source", "schema_version"}
            has_snapshots = snapshot_cols <= schema["v2_bao_market_shadow_snapshots"]
            ids = list(TARGET_RACES)
            races = read("""SELECT race_id,deadline_at FROM v2_races
                WHERE race_date=%s AND race_id=ANY(%s) ORDER BY race_id""", (TARGET_DATE, ids))
            entries = read("""SELECT race_id,lane FROM v2_race_entries
                WHERE race_id=ANY(%s) ORDER BY race_id,lane""", (ids,))
            base = read("""SELECT race_id,ticket,fetched_at,is_final FROM v2_odds_trifecta
                WHERE race_id=ANY(%s) ORDER BY race_id,ticket""", (ids,))
            snapshots = read("""SELECT race_id,phase,captured_at,created_at,deadline_at,odds,source,schema_version
                FROM v2_bao_market_shadow_snapshots WHERE race_id=ANY(%s)
                ORDER BY race_id,phase""", (ids,)) if has_snapshots else []
            conn.rollback()
    return analyze(races, entries, base, snapshots,
                   {"bao_snapshots_available": has_snapshots})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=TARGET_DATE)
    args = parser.parse_args()
    if args.date != TARGET_DATE:
        parser.error("Only 2026-09-08 is supported")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    result = read_database(url)
    print("ODDS_EVIDENCE_AUDIT=" + json.dumps(result, ensure_ascii=False, default=str, allow_nan=False))


if __name__ == "__main__":
    main()
