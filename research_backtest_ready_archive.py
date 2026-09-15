# -*- coding: utf-8 -*-
"""Research-only historical readiness check backed by a verified archive partition.

This helper is intentionally not used by Production PRE/FINAL services. It keeps
entries/results in read-only PostgreSQL while loading historical base trifecta
odds from a verified JSONL.gz archive manifest. With
ARCHIVE_READY_COMPARE_ONLINE=1 it also proves per-race ticket-count equality
against the still-online source rows before any future retention change.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import os
from typing import Any

from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource


def _parse_date(name: str, default: str) -> date:
    raw = os.getenv(name, default).strip()
    try:
        return date.fromisoformat(raw)
    except Exception as exc:
        raise ValueError(f"invalid {name}: {raw!r}") from exc


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _race_prefix(value: date) -> str:
    return value.strftime("%Y%m%d")


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    manifest_path = os.getenv("ARCHIVE_MANIFEST", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    if not manifest_path:
        raise RuntimeError("ARCHIVE_MANIFEST is required")

    start_date = _parse_date("CHECK_START_DATE", "2026-07-01")
    end_date = _parse_date("CHECK_END_DATE", "2026-07-31")
    if start_date > end_date:
        raise ValueError("CHECK_START_DATE must be <= CHECK_END_DATE")

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_odds_trifecta",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
    if not source.covers(query):
        raise RuntimeError("archive manifest does not exactly cover requested readiness period")

    archive_rows = source.fetch(query)
    archive_tickets: dict[str, set[str]] = defaultdict(set)
    for row in archive_rows:
        race_id = str(row.get("race_id") or "")
        ticket = str(row.get("ticket") or "")
        if not race_id or not ticket:
            raise RuntimeError("archive row has empty race_id/ticket")
        archive_tickets[race_id].add(ticket)

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c timezone=UTC -c statement_timeout=120000",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()["transaction_read_only"]).lower() != "on":
                raise RuntimeError("read-only guard failed")

            cur.execute(
                """
                select
                    r.race_id::text as race_id,
                    r.race_date,
                    r.venue_id,
                    r.race_no,
                    count(distinct e.lane)::int as entries_count,
                    max(case
                        when coalesce(res.trifecta_payout_yen, 0) > 0
                         and (
                            coalesce(nullif(res.trifecta_ticket, ''), '') <> ''
                            or (
                                res.first_lane is not null
                                and res.second_lane is not null
                                and res.third_lane is not null
                            )
                         )
                        then 1 else 0 end)::int as result_ok
                from v2_races r
                left join v2_race_entries e on e.race_id = r.race_id
                left join v2_results res on res.race_id = r.race_id
                where r.race_date between %s and %s
                group by r.race_id, r.race_date, r.venue_id, r.race_no
                order by r.race_date, r.race_id
                """,
                (start_date, end_date),
            )
            races = list(cur.fetchall())

            if os.getenv("ARCHIVE_READY_COMPARE_ONLINE", "0").strip() == "1":
                end_exclusive = end_date + timedelta(days=1)
                cur.execute(
                    """
                    select race_id::text as race_id, count(distinct ticket)::int as odds_count
                    from v2_odds_trifecta
                    where race_id >= %s and race_id < %s
                    group by race_id
                    """,
                    (_race_prefix(start_date), _race_prefix(end_exclusive)),
                )
                online_counts = {
                    str(row["race_id"]): _safe_int(row["odds_count"])
                    for row in cur.fetchall()
                }
                archive_counts = {rid: len(tickets) for rid, tickets in archive_tickets.items()}
                all_ids = set(online_counts) | set(archive_counts)
                mismatches = [
                    (rid, online_counts.get(rid, 0), archive_counts.get(rid, 0))
                    for rid in sorted(all_ids)
                    if online_counts.get(rid, 0) != archive_counts.get(rid, 0)
                ]
                if mismatches:
                    sample = mismatches[:10]
                    raise AssertionError(
                        f"archive-vs-online odds coverage mismatch count={len(mismatches)} sample={sample}"
                    )
                print(
                    f"ARCHIVE_READY_COMPARE=PASS races={len(all_ids)} archive_rows={len(archive_rows)}",
                    flush=True,
                )

    month_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total_races": 0,
            "entries_full": 0,
            "result_ok": 0,
            "odds_full_120": 0,
            "backtest_ready": 0,
            "missing_odds_rows": 0,
        }
    )
    total = {
        "total_races": 0,
        "entries_full": 0,
        "result_ok": 0,
        "odds_full_120": 0,
        "backtest_ready": 0,
        "missing_odds_rows": 0,
    }

    worst: list[tuple[int, str, str, int, int]] = []
    for row in races:
        rid = str(row["race_id"])
        odds_count = len(archive_tickets.get(rid, set()))
        entries_full = _safe_int(row.get("entries_count")) == 6
        result_ok = _safe_int(row.get("result_ok")) == 1
        odds_full = odds_count == 120
        ready = entries_full and result_ok and odds_full
        missing = max(0, 120 - odds_count)
        month = str(row["race_date"])[:7]
        bucket = month_stats[month]

        for target in (total, bucket):
            target["total_races"] += 1
            target["entries_full"] += int(entries_full)
            target["result_ok"] += int(result_ok)
            target["odds_full_120"] += int(odds_full)
            target["backtest_ready"] += int(ready)
            target["missing_odds_rows"] += missing

        if missing:
            worst.append((missing, rid, str(row["race_date"]), _safe_int(row.get("race_no")), odds_count))

    print(
        "ARCHIVE_READY_TOTAL "
        + " ".join(f"{k}={v}" for k, v in total.items()),
        flush=True,
    )
    for month in sorted(month_stats):
        bucket = month_stats[month]
        print(
            f"ARCHIVE_READY_MONTH month={month} "
            + " ".join(f"{k}={v}" for k, v in bucket.items()),
            flush=True,
        )

    worst.sort(key=lambda x: (-x[0], x[2], x[1]))
    for missing, rid, race_date, race_no, odds_count in worst[:10]:
        print(
            f"ARCHIVE_READY_MISSING race_id={rid} date={race_date} race_no={race_no} "
            f"odds={odds_count}/120 missing={missing}",
            flush=True,
        )

    print(f"ARCHIVE_READY_SOURCE={source.name}", flush=True)
    print("ARCHIVE_READY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
