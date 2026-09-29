# -*- coding: utf-8 -*-
"""Build historical applied-term Course proxy from official BOAT RACE K files.

Purpose
-------
Provide a leakage-safe historical Course feature for V4/V5 research when
same-day official racer-course snapshots do not exist.

The proxy uses only races from a completed six-month aggregation period that
ended before the application period. It is therefore known before every target
race in that application period.

This does NOT impersonate the Production Course contract:
- source is distinct;
- snapshot_date is the training period end, not the target race date;
- Production V4 requires exact target-date source='boatrace_official_racer_course',
  so these rows are ignored by Production.

Writes are gated by CONFIRM_HISTORICAL_COURSE_DB_WRITE=YES and use INSERT
... ON CONFLICT DO NOTHING. Existing rows are never updated or deleted.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

import audit_k_day_all_pg as kfile


SOURCE = "boatrace_official_k_applied_term_proxy"
WRITE_CONFIRM = "YES"


@dataclass(frozen=True)
class TermSpec:
    key: str
    training_start: date
    training_end: date
    application_start: date
    application_end: date


TERM_SPECS = {
    "2025H2": TermSpec(
        "2025H2",
        date(2024, 11, 1),
        date(2025, 4, 30),
        date(2025, 7, 1),
        date(2025, 12, 31),
    ),
    "2026H1": TermSpec(
        "2026H1",
        date(2025, 5, 1),
        date(2025, 10, 31),
        date(2026, 1, 1),
        date(2026, 6, 30),
    ),
    "2026H2": TermSpec(
        "2026H2",
        date(2025, 11, 1),
        date(2026, 4, 30),
        date(2026, 7, 1),
        date(2026, 12, 31),
    ),
}


def date_range(a: date, b: date):
    cur = a
    while cur <= b:
        yield cur
        cur += timedelta(days=1)


def _finite(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def aggregate_entries(day_races: list[dict[str, Any]], acc: dict[int, dict[str, Any]]) -> None:
    for race in day_races:
        for e in race.get("entries") or []:
            racer = int(e.get("racer_number") or 0)
            course = int(e.get("start_course") or 0)
            if racer <= 0 or course not in range(1, 7):
                continue
            row = acc.setdefault(
                racer,
                {
                    "total_course_starts": 0,
                    "courses": {
                        c: {
                            "starts": 0,
                            "top3": 0,
                            "st_sum": 0.0,
                            "st_n": 0,
                        }
                        for c in range(1, 7)
                    },
                },
            )
            row["total_course_starts"] += 1
            c = row["courses"][course]
            c["starts"] += 1
            finish = e.get("finish_position")
            if isinstance(finish, int) and 1 <= finish <= 3:
                c["top3"] += 1
            st = _finite(e.get("start_timing"))
            if st is not None:
                c["st_sum"] += st
                c["st_n"] += 1


def build_rows(acc: dict[int, dict[str, Any]], spec: TermSpec) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for racer, payload in sorted(acc.items()):
        total = int(payload["total_course_starts"])
        if total <= 0:
            continue
        for course in range(1, 7):
            c = payload["courses"][course]
            starts = int(c["starts"])
            if starts <= 0:
                continue
            entry_rate = 100.0 * starts / total
            top3_rate = 100.0 * int(c["top3"]) / starts
            avg_st = c["st_sum"] / c["st_n"] if c["st_n"] else None
            out.append(
                {
                    "racer_number": racer,
                    "snapshot_date": spec.training_end,
                    "course": course,
                    "entry_rate": round(entry_rate, 6),
                    "top3_rate": round(top3_rate, 6),
                    "avg_st": round(avg_st, 6) if avg_st is not None else None,
                    "source": SOURCE,
                    "raw": {
                        "contract": "HISTORICAL_APPLIED_TERM_COURSE_PROXY_V1",
                        "term": spec.key,
                        "training_start": spec.training_start.isoformat(),
                        "training_end": spec.training_end.isoformat(),
                        "application_start": spec.application_start.isoformat(),
                        "application_end": spec.application_end.isoformat(),
                        "course_starts": starts,
                        "total_course_starts": total,
                        "top3_count": int(c["top3"]),
                        "st_count": int(c["st_n"]),
                        "historical_reconstruction": True,
                        "prospective_evidence": False,
                    },
                }
            )
    return out


def fetch_and_aggregate(spec: TermSpec, *, sleep_sec: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    acc: dict[int, dict[str, Any]] = {}
    days_ok = 0
    days_missing = 0
    races = 0
    entries = 0

    for d in date_range(spec.training_start, spec.training_end):
        ds = d.isoformat()
        kfile.TARGET_DATE = ds
        try:
            text = kfile.get_k_text(ds)
        except Exception as exc:
            # There can be non-racing/missing archive dates. Keep the manifest.
            print(
                f"HIST_COURSE_K_DAY=date:{ds} status:missing error:{type(exc).__name__}",
                flush=True,
            )
            days_missing += 1
            time.sleep(max(0.0, sleep_sec))
            continue

        sections = kfile.split_venue_sections(text.splitlines())
        day_races: list[dict[str, Any]] = []
        for section in sections:
            day_races.extend(kfile.parse_section(section))
        aggregate_entries(day_races, acc)
        days_ok += 1
        races += len(day_races)
        entries += sum(len(x.get("entries") or []) for x in day_races)
        print(
            f"HIST_COURSE_K_DAY=date:{ds} status:ok races:{len(day_races)} "
            f"entries:{sum(len(x.get('entries') or []) for x in day_races)}",
            flush=True,
        )
        time.sleep(max(0.0, sleep_sec))

    rows = build_rows(acc, spec)
    manifest = {
        "term": spec.key,
        "training_start": spec.training_start.isoformat(),
        "training_end": spec.training_end.isoformat(),
        "application_start": spec.application_start.isoformat(),
        "application_end": spec.application_end.isoformat(),
        "days_ok": days_ok,
        "days_missing": days_missing,
        "races": races,
        "entries": entries,
        "racers": len(acc),
        "rows": len(rows),
    }
    return rows, manifest


def insert_rows(db: str, rows: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = 0
    conflicts = 0
    with psycopg.connect(db, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set local statement_timeout='180s'")
            for row in rows:
                cur.execute(
                    """
                    insert into v2_racer_course_stats_snapshots
                      (racer_number,snapshot_date,course,entry_rate,top3_rate,avg_st,
                       source,raw,created_at,updated_at)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,now(),now())
                    on conflict (racer_number,snapshot_date,course) do nothing
                    """,
                    (
                        row["racer_number"],
                        row["snapshot_date"],
                        row["course"],
                        row["entry_rate"],
                        row["top3_rate"],
                        row["avg_st"],
                        row["source"],
                        Jsonb(row["raw"]),
                    ),
                )
                if int(cur.rowcount or 0):
                    inserted += 1
                else:
                    conflicts += 1
        conn.commit()
    return inserted, conflicts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", choices=sorted(TERM_SPECS), required=True)
    ap.add_argument(
        "--sleep-sec",
        type=float,
        default=float(os.getenv("HIST_COURSE_OFFICIAL_SLEEP_SEC", "0.05")),
    )
    ap.add_argument(
        "--output",
        default=os.getenv(
            "HIST_COURSE_OUTPUT",
            "historical-applied-term-course-manifest.json",
        ),
    )
    args = ap.parse_args()
    spec = TERM_SPECS[args.term]
    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_COURSE_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )

    print("HIST_COURSE_SOURCE=BOATRACE_OFFICIAL_K_FILES", flush=True)
    print(f"HIST_COURSE_PROXY_SOURCE={SOURCE}", flush=True)
    print("HIST_COURSE_TARGET_OUTCOME_LEAKAGE=0", flush=True)
    print("HIST_COURSE_PRODUCTION_CONTRACT_CHANGED=0", flush=True)
    print("HIST_COURSE_LINE=0 BUY=0 STAKE_CHANGE=0", flush=True)
    print(f"HIST_COURSE_WRITE_ENABLED={int(write_enabled)}", flush=True)

    rows, manifest = fetch_and_aggregate(spec, sleep_sec=args.sleep_sec)

    inserted = conflicts = 0
    if write_enabled:
        db = (os.getenv("DATABASE_URL") or "").strip()
        if not db:
            raise RuntimeError("DATABASE_URL required in write mode")
        inserted, conflicts = insert_rows(db, rows)

    payload = {
        "contract": "HISTORICAL_APPLIED_TERM_COURSE_PROXY_V1",
        "source": SOURCE,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "production_v4_accepted_source": False,
        "write_enabled": write_enabled,
        "inserted": inserted,
        "conflicts_preserved": conflicts,
        **manifest,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print("HIST_COURSE_SUMMARY=" + json.dumps(payload, sort_keys=True), flush=True)
    print("HIST_COURSE_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
