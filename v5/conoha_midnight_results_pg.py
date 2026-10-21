"""ConoHa V5: bounded post-race official-result catch-up (research/collection only).

Runs AFTER a racing day, including midnight boat races. A query-only preview
is the default. --apply fetches official race results for already-known races
that lack verified results; no pre-deadline features, odds, bets, or LINE.
Missing/unparseable web pages stay PENDING and never overwrite results.
Designed to run separately from the daily collector under the SAME flock lock.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
FINAL_NONWINNING = frozenset(("cancelled", "trifecta_invalid"))
RACE_ID = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
TICKET = re.compile(r"([1-6])-([1-6])-([1-6])\Z")


def resolved(status: object, ticket: object, payout: object) -> bool:
    """Fail closed. Incomplete or weakly labelled results remain eligible for retry."""
    if status in FINAL_NONWINNING:
        return True
    if status != "official" or not isinstance(ticket, str):
        return False
    match = TICKET.fullmatch(ticket)
    if not match or len(set(match.groups())) != 3:
        return False
    return type(payout) is int and payout > 0


def target_date(raw: str | None, today: date | None = None) -> date:
    now_date = today or datetime.now(JST).date()
    if raw is None:
        return now_date - timedelta(days=1)
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("expected YYYY-MM-DD") from exc
    if parsed.isoformat() != raw:
        raise ValueError("expected YYYY-MM-DD")
    if parsed >= now_date:
        raise ValueError("only completed previous days may be fetched")
    if parsed < date(2025, 7, 1):
        raise ValueError("day is outside V5 history range")
    return parsed


def pending_rows(day: date) -> tuple[int, list[str]]:
    from db_pg import get_conn
    from psycopg import sql
    from v5_core_read_routes import core_relation

    query = sql.SQL("""SELECT r.race_id, x.result_status, x.trifecta_ticket,
                          x.trifecta_payout_yen
                   FROM {} r
                   LEFT JOIN {} x ON x.race_id = r.race_id
                   WHERE r.race_date = %s
                   ORDER BY r.race_id""").format(
        core_relation("v2_races"), core_relation("v2_results"),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (day.isoformat(),),
            )
            rows = cur.fetchall()
    pending = [
        row["race_id"]
        for row in rows
        if (isinstance(row["race_id"], str)
            and RACE_ID.fullmatch(row["race_id"])
            and row["race_id"][:8] == day.strftime("%Y%m%d")
            and not resolved(
                row["result_status"],
                row["trifecta_ticket"],
                row["trifecta_payout_yen"],
            ))
    ]
    return len(rows), pending


def recover_one(race_id: str, day: date) -> str:
    # Imported lazily: preview mode must not create an HTTP session or fetch.
    from repair_month_all_pg import _fetch, _looks_no_race, _official_url, parse_result, upsert_rows

    _, venue, race = race_id.split("_")
    url = _official_url("raceresult", day.isoformat(), venue, int(race))
    html = _fetch(url)
    if _looks_no_race(html):
        return "PENDING_NO_PAGE"
    parsed = parse_result(html)
    status = parsed.get("result_status")
    if status == "official" and not resolved(
        status, parsed.get("trifecta_ticket"), parsed.get("trifecta_payout_yen")
    ):
        return "PENDING_UNVERIFIED"
    if status not in FINAL_NONWINNING and status != "official":
        return "PENDING_UNVERIFIED"
    parsed["race_id"] = race_id
    parsed["race_date"] = day.isoformat()
    upsert_rows("v2_results", [parsed], "race_id", chunk_size=1)
    return "SAVED_" + str(status).upper()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="completed racing day, YYYY-MM-DD; default yesterday JST")
    parser.add_argument("--apply", action="store_true", help="fetch and upsert VERIFIED results; default read-only")
    parser.add_argument("--max-races", type=int, default=48, help="maximum official requests (1..288)")
    parser.add_argument("--sleep-sec", type=float, default=1.5, help="seconds between requests (>=0.5)")
    args = parser.parse_args(argv)
    if not 1 <= args.max_races <= 288 or args.sleep_sec < 0.5:
        parser.error("max-races must be 1..288 and sleep-sec >=0.5")
    try:
        day = target_date(args.date)
    except ValueError as exc:
        parser.error(str(exc))
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL required; use local ConoHa PostgreSQL only")

    count, pending = pending_rows(day)
    print("V5_RESULTS_CATCHUP_DATE=" + day.isoformat(), flush=True)
    print("V5_RESULTS_KNOWN_RACES=" + str(count), flush=True)
    print("V5_RESULTS_PENDING_BEFORE=" + str(len(pending)), flush=True)
    print("V5_RESULTS_MODE=" + ("APPLY" if args.apply else "PREVIEW"), flush=True)
    if not args.apply:
        print("V5_RESULTS_CATCHUP_NO_WRITES=1", flush=True)
        print("V5_RESULTS_PENDING_IDS=" + ",".join(pending[:12]), flush=True)
        return 0
    if count == 0:
        print("V5_RESULTS_GATE=NO_KNOWN_RACES", flush=True)
        return 3

    # Set before importing the legacy parser, whose SOURCE setting is read on import.
    os.environ["REPAIR_SOURCE"] = "conoha_v5_postrace_catchup"
    os.environ.setdefault("HTTP_TIMEOUT", "12")
    os.environ.setdefault("HTTP_MAX_RETRIES", "1")
    saved = 0
    for i, race_id in enumerate(pending[:args.max_races]):
        if i:
            time.sleep(args.sleep_sec)
        try:
            outcome = recover_one(race_id, day)
        except Exception as exc:
            outcome = "PENDING_ERROR_" + type(exc).__name__
        print("V5_RESULTS_RACE=" + race_id + " " + outcome, flush=True)
        if outcome.startswith("SAVED_"):
            saved += 1

    _, remaining = pending_rows(day)
    print("V5_RESULTS_SAVED=" + str(saved), flush=True)
    print("V5_RESULTS_PENDING_AFTER=" + str(len(remaining)), flush=True)
    print("V5_RESULTS_GATE=" + ("COMPLETE" if not remaining else "PENDING"), flush=True)
    return 0 if not remaining else 3


if __name__ == "__main__":
    sys.exit(main())
