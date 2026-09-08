"""Fixed-date, read-only audit of the 2026-09-08 odds gaps.

No HTTP, DDL, data repair, production decisions, or notification calls.
Current base-table timestamps are not first-observation evidence.
"""
from __future__ import annotations

import itertools
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

TARGET_DATE = "2026-09-08"
JST = timezone(timedelta(hours=9))
ALL_TICKETS = tuple(
    f"{a}-{b}-{c}" for a, b, c in itertools.permutations(range(1, 7), 3)
)
TARGET_RACES = (
    "20260908_10_02", "20260908_14_02", "20260908_10_03",
    "20260908_14_03", "20260908_11_02", "20260908_11_03",
    "20260908_11_04", "20260908_03_03", "20260908_13_05",
    "20260908_11_05", "20260908_03_04", "20260908_13_06",
    "20260908_11_06", "20260908_11_07", "20260908_13_08",
    "20260908_11_08", "20260908_03_08", "20260908_13_09",
    "20260908_11_09",
)
assert len(TARGET_RACES) == len(set(TARGET_RACES)) == 19


def as_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt.replace(tzinfo=JST) if dt.tzinfo is None else dt.astimezone(JST)


def ticket_status(tickets: list[str], active_lanes: list[int] | None = None) -> dict:
    """Use the entry list, not observed tickets, to determine expected lanes."""
    lanes = sorted(set(active_lanes if active_lanes is not None else range(1, 7)))
    valid_lanes = len(lanes) in (4, 5, 6) and all(1 <= x <= 6 for x in lanes)
    expected = {
        f"{a}-{b}-{c}" for a, b, c in itertools.permutations(lanes, 3)
    } if valid_lanes else set()
    counts = Counter(str(t).strip() for t in tickets)
    actual = set(counts)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    return {
        "active_lanes": lanes, "expected": len(expected),
        "observed": len(tickets), "distinct": len(actual),
        "missing": missing, "unexpected": unexpected,
        "duplicates": sum(n - 1 for n in counts.values()),
        "complete": valid_lanes and not missing and not unexpected
                    and all(n == 1 for n in counts.values()),
    }


def review_snapshot(row: dict, deadline: datetime | None) -> dict:
    """A frozen complete market observation is evidence, not an ROI approval."""
    captured = as_time(row.get("captured_at"))
    stored_deadline = as_time(row.get("deadline_at"))
    values = row.get("odds")
    phase = row.get("phase")
    source = row.get("source")
    reasons = []
    if phase not in ("early", "late"):
        reasons.append("unknown_phase")
    if source != "official_odds3t":
        reasons.append("source_not_verified")
    if not isinstance(values, (list, tuple)) or len(values) != 120:
        reasons.append("not_exact120")
    else:
        try:
            if any(float(x) <= 0 for x in values):
                reasons.append("nonpositive_odds")
        except (TypeError, ValueError):
            reasons.append("invalid_odds")
    if captured is None or deadline is None or captured >= deadline:
        reasons.append("not_proven_before_deadline")
    if stored_deadline is None or deadline is None or stored_deadline != deadline:
        reasons.append("deadline_mismatch")
    if captured is not None and deadline is not None:
        lead = (deadline - captured).total_seconds() / 60
        if phase == "early" and not 20 <= lead <= 30:
            reasons.append("outside_early_window")
        if phase == "late" and not 0 <= lead <= 7:
            reasons.append("outside_late_window")
    return {
        "phase": phase, "captured_at": captured.isoformat() if captured else None,
        "source": source, "schema_version": row.get("schema_version"),
        "status": "FROZEN_OBSERVATION" if not reasons else "UNVERIFIED",
        "reasons": reasons,
    }


def analyze(races: list[dict], entries: list[dict], base: list[dict],
            snapshots: list[dict], schema: dict) -> dict:
    entry_by = defaultdict(list)
    for row in entries:
        entry_by[str(row["race_id"])].append(int(row["lane"]))
    base_by = defaultdict(list)
    for row in base:
        base_by[str(row["race_id"])].append(row)
    snap_by = defaultdict(list)
    for row in snapshots:
        snap_by[str(row["race_id"])].append(row)
    by_race = {str(row["race_id"]): row for row in races}
    frequencies = Counter()
    report = []
    for rid in TARGET_RACES:
        race = by_race.get(rid)
        if race is None:
            report.append({"race_id": rid, "status": "RACE_NOT_FOUND"})
            continue
        deadline = as_time(race.get("deadline_at"))
        if deadline is None and race.get("deadline_time"):
            deadline = as_time(f"{TARGET_DATE}T{str(race['deadline_time'])[:5]}:00+09:00")
        rows = base_by[rid]
        status = ticket_status([r.get("ticket", "") for r in rows], entry_by[rid])
        frequencies.update(status["missing"])
        times = [as_time(r.get("fetched_at")) for r in rows if r.get("fetched_at")]
        times = [t for t in times if t is not None]
        evidence = [review_snapshot(s, deadline) for s in snap_by[rid]]
        report.append({
            "race_id": rid, "deadline_at": deadline.isoformat() if deadline else None,
            "base": status,
            "base_fetched_at_min": min(times).isoformat() if times else None,
            "base_fetched_at_max": max(times).isoformat() if times else None,
            "base_timestamp_semantics": "latest_saved_value_not_first_observation",
            "base_final_flags": dict(Counter(str(r.get("is_final")) for r in rows)),
            "snapshots": evidence,
            "predeadline_evidence": "FROZEN_OBSERVATION" if any(
                e["status"] == "FROZEN_OBSERVATION" for e in evidence
            ) else "UNKNOWN",
            "root_cause": "UNDETERMINED",
        })
    return {
        "audit_date": TARGET_DATE, "mode": "read_only_no_http_no_writes",
        "schema": schema, "races": report,
        "missing_ticket_frequency": dict(sorted(frequencies.items())),
        "root_cause": "UNDETERMINED",
        "production_promotion": "BLOCKED",
    }


def read_database(url: str) -> dict:
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '15000ms'")
            cur.execute("SET LOCAL lock_timeout = '2000ms'")
            def read(query: str, params: tuple = ()) -> list[dict]:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
            schema_rows = read("""SELECT table_name,column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name IN
                ('v2_races','v2_race_entries','v2_odds_trifecta','v2_bao_market_shadow_snapshots')""")
            schema = defaultdict(set)
            for row in schema_rows:
                schema[row["table_name"]].add(row["column_name"])
            required = {
                "v2_races": {"race_id", "race_date", "deadline_at", "deadline_time"},
                "v2_race_entries": {"race_id", "lane"},
                "v2_odds_trifecta": {"race_id", "ticket", "fetched_at", "is_final"},
            }
            for table, cols in required.items():
                if not cols <= schema[table]:
                    raise RuntimeError(f"Missing required columns: {table}")
            snapshot_cols = {"race_id", "phase", "captured_at", "deadline_at", "odds", "source", "schema_version"}
            has_snapshots = snapshot_cols <= schema["v2_bao_market_shadow_snapshots"]
            ids = list(TARGET_RACES)
            races = read("""SELECT race_id,deadline_at,deadline_time FROM v2_races
                WHERE race_date=%s AND race_id=ANY(%s) ORDER BY race_id""", (TARGET_DATE, ids))
            entries = read("""SELECT race_id,lane FROM v2_race_entries
                WHERE race_id=ANY(%s) ORDER BY race_id,lane""", (ids,))
            base = read("""SELECT race_id,ticket,fetched_at,is_final FROM v2_odds_trifecta
                WHERE race_id=ANY(%s) ORDER BY race_id,ticket""", (ids,))
            snapshots = read("""SELECT race_id,phase,captured_at,deadline_at,odds,source,schema_version
                FROM v2_bao_market_shadow_snapshots WHERE race_id=ANY(%s)
                ORDER BY race_id,phase""", (ids,)) if has_snapshots else []
            conn.rollback()
    return analyze(races, entries, base, snapshots,
                   {"bao_snapshots_available": has_snapshots})


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=TARGET_DATE)
    args = parser.parse_args()
    if args.date != TARGET_DATE:
        parser.error("Only 2026-09-08 is supported")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    result = read_database(url)
    print("ODDS_EVIDENCE_AUDIT=" + json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
