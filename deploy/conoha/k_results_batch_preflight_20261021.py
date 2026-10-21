# -*- coding: utf-8 -*-
"""Read-only preflight for nine dates with missing per-racer BOATRACE K results.

No SQL writes. No automatic import. Source of truth remains the existing
public.v2_results, and the official K archive must agree on *race IDs*, not
just counts. Existing v2_result_entries rows veto any blind re-import.
Dates with missing overall results (Oct 8,15,16,17) are deliberately excluded.
Uses one official archive GET per day, serial and rate-limited.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta

import psycopg

# Script lives in deploy/conoha; source parsers live at repository root.
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import audit_k_day_all_pg as ka

DAYS = (
    "2026-10-07", "2026-10-09", "2026-10-10",
    "2026-10-11", "2026-10-12", "2026-10-13",
    "2026-10-14", "2026-10-18", "2026-10-19",
)


def read_existing(conn: psycopg.Connection, day: str) -> tuple[set[str], int, set[str]]:
    begin = day.replace("-", "") + "_"
    after = (date.fromisoformat(day) + timedelta(days=1)).strftime("%Y%m%d") + "_"
    with conn.cursor() as c:
        c.execute(
            "SELECT race_id FROM public.v2_results "
            "WHERE race_id >= %s AND race_id < %s",
            (begin, after),
        )
        saved = {str(row[0]) for row in c.fetchall()}
        c.execute(
            "SELECT race_id FROM public.v2_races "
            "WHERE race_id >= %s AND race_id < %s",
            (begin, after),
        )
        races = {str(row[0]) for row in c.fetchall()}
        c.execute(
            "SELECT COUNT(*) FROM public.v2_result_entries "
            "WHERE race_id >= %s AND race_id < %s",
            (begin, after),
        )
        detailed = int(c.fetchone()[0])
    return saved, detailed, races


def fetch_official_ids(day: str) -> tuple[set[str], int, list[str]]:
    ka.TARGET_DATE = day
    text = ka.get_k_text(day)
    sections = ka.split_venue_sections(text.splitlines())
    parsed = [race for section in sections for race in ka.parse_section(section)]
    ids = [str(r["race_id"]) for r in parsed]
    issues = []
    if not sections or not parsed:
        issues.append("NO_OFFICIAL_RACES")
    if len(ids) != len(set(ids)):
        issues.append("DUPLICATE_RACE_IDS")
    if any(len(r["entries"]) != 6 for r in parsed):
        issues.append("INCOMPLETE_SIX_LANES")
    if any(r["parse_failed_candidate_lines"] for r in parsed):
        issues.append("PARSER_FAILURE")
    return set(ids), len(parsed), issues


def main() -> int:
    if os.environ.get("CONFIRM_K_DB_WRITE"):
        raise SystemExit("ABORT: write authorization variable must NOT be set for preflight")
    print("K_BATCH_PREFLIGHT_MODE=READ_ONLY", flush=True)
    print("DB_WRITES=0 DAYS=9", flush=True)
    blocked = 0
    # options set at connect, not after, so even an accidental DML fails.
    with psycopg.connect(
        "postgresql:///railway",
        autocommit=True,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as conn:
        for index, day in enumerate(DAYS):
            try:
                saved, detail_count, recorded = read_existing(conn, day)
                if not saved:
                    print(f"{day} BLOCK no_saved_results", flush=True)
                    blocked += 1
                    continue
                official, count, issues = fetch_official_ids(day)
                missing = official - saved
                extra = saved - official
                if detail_count:
                    issues.append(f"DETAILS_ALREADY_PRESENT={detail_count}")
                if missing:
                    issues.append(f"MISSING_RESULTS={len(missing)} first={sorted(missing)[:2]}")
                if extra:
                    issues.append(f"NONOFFICIAL_RESULTS={len(extra)} first={sorted(extra)[:2]}")
                if recorded != official:
                    issues.append(
                        f"RACE_ID_MISMATCH recorded={len(recorded)} "
                        f"official={len(official)}"
                    )
                status = "PASS" if not issues else "BLOCK"
                if issues:
                    blocked += 1
                print(
                    f"{day} {status} k_races={count} results={len(saved)} "
                    f"race_rows={len(recorded)} detailed_rows={detail_count} "
                    f"issues={'; '.join(issues) if issues else 'none'}",
                    flush=True,
                )
            except Exception as exc:
                blocked += 1
                print(f"{day} BLOCK error={type(exc).__name__}: {exc}", flush=True)
            # Be polite to official source; never parallel GET requests.
            if index < len(DAYS) - 1:
                time.sleep(1)
    print(f"PREFLIGHT_DONE ready={len(DAYS)-blocked} blocked={blocked}", flush=True)
    return 0 if not blocked else 1


if __name__ == "__main__":
    sys.exit(main())
