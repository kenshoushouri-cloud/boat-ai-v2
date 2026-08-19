# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import itertools
import time
import importlib
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import Any, Dict, List, Optional, Tuple

JST = timezone(timedelta(hours=9))

VERSION = "2026-08-20-window-progress-timeout-v3.3-motor2-scope"

WINDOW_PRESETS = {
    "morning": ("08:30", "10:15"),
    "day": ("09:45", "15:00"),
    "night": ("14:45", None),
}


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _resolve_window() -> Tuple[str, Optional[str], str]:
    name = (os.getenv("WINDOW_NAME") or "").strip().lower()
    start = (os.getenv("WINDOW_START") or "").strip()
    end = (os.getenv("WINDOW_END") or "").strip()

    if not start:
        if name in WINDOW_PRESETS:
            start, default_end = WINDOW_PRESETS[name]
            if not end:
                end = default_end or ""
        else:
            name = "morning"
            start, default_end = WINDOW_PRESETS[name]
            end = default_end or ""

    if not name:
        name = f"{start}-{end or 'end'}"

    return start, (end or None), name


def _normalize_date(value: Any) -> str:
    return "" if value is None else str(value)[:10]


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL ãæªè¨­å®ã§ã")

    try:
        import psycopg  # type: ignore
        return psycopg.connect(url)
    except Exception:
        import psycopg2  # type: ignore
        return psycopg2.connect(url)


def _fetch_dicts(
    query: str,
    params: Tuple[Any, ...],
) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            cols = [
                getattr(description, "name", None) or description[0]
                for description in cur.description
            ]
            return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def select_window_races(
    target_date: str,
    start: str,
    end: Optional[str],
) -> List[Dict[str, Any]]:
    if end:
        if start <= end:
            query = """
                SELECT
                    race_id,
                    race_date::text AS race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                FROM v2_races
                WHERE race_date = %s
                  AND deadline_time IS NOT NULL
                  AND deadline_time >= %s
                  AND deadline_time < %s
                ORDER BY deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
        else:
            query = """
                SELECT
                    race_id,
                    race_date::text AS race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                FROM v2_races
                WHERE race_date = %s
                  AND deadline_time IS NOT NULL
                  AND (
                        deadline_time >= %s
                     OR deadline_time < %s
                  )
                ORDER BY deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
    else:
        query = """
            SELECT
                race_id,
                race_date::text AS race_date,
                venue_code,
                venue_name,
                race_no,
                deadline_time,
                deadline_at
            FROM v2_races
            WHERE race_date = %s
              AND deadline_time IS NOT NULL
              AND deadline_time >= %s
            ORDER BY deadline_time, venue_code, race_no
        """
        params = (target_date, start)

    return _fetch_dicts(query, params)


ALL_LANES = {1, 2, 3, 4, 5, 6}


def _expected_ticket_set(active_lanes: set[int]) -> set[str]:
    return {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations(sorted(active_lanes), 3)
    }


def _evaluate_ticket_snapshot(tickets: List[str]) -> Dict[str, Any]:
    """
    DBã«ä¿å­æ¸ã¿ã®ä¸é£åticketéåãè©ä¾¡ããã

    6è=120ã5è=60ã4è=24éããè¨±å¯ãããã
    ä»¶æ°ã ãã§ã¯ãªããæå¹èéåã®å¨é åã¨å®å¨ä¸è´ããå ´åã®ã¿
    complete=True ã¨ããã
    """
    normalized = [str(ticket or "").strip() for ticket in tickets]
    unique_tickets = set(normalized)
    duplicate_count = len(normalized) - len(unique_tickets)

    active_lanes: set[int] = set()
    malformed_count = 0

    for ticket in unique_tickets:
        parts = ticket.split("-")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            malformed_count += 1
            continue

        lanes = [int(part) for part in parts]
        if (
            any(lane not in ALL_LANES for lane in lanes)
            or len(set(lanes)) != 3
        ):
            malformed_count += 1
            continue

        active_lanes.update(lanes)

    lane_count_valid = 4 <= len(active_lanes) <= 6
    expected_tickets = (
        _expected_ticket_set(active_lanes)
        if lane_count_valid
        else set()
    )
    missing_count = len(expected_tickets - unique_tickets)
    unexpected_count = len(unique_tickets - expected_tickets)
    expected_count = len(expected_tickets)

    complete = (
        lane_count_valid
        and malformed_count == 0
        and duplicate_count == 0
        and len(normalized) == expected_count
        and len(unique_tickets) == expected_count
        and missing_count == 0
        and unexpected_count == 0
    )

    return {
        "valid_tickets": len(unique_tickets),
        "active_lanes": sorted(active_lanes),
        "scratched_lanes": sorted(ALL_LANES - active_lanes),
        "expected_count": expected_count,
        "complete": complete,
        "duplicates": duplicate_count,
        "malformed": malformed_count,
        "missing": missing_count,
        "unexpected": unexpected_count,
    }


def select_odds_statuses(
    race_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not race_ids:
        return {}

    query = """
        SELECT race_id, ticket
        FROM v2_odds_trifecta
        WHERE race_id = ANY(%s)
        ORDER BY race_id, ticket
    """

    try:
        rows = _fetch_dicts(query, (race_ids,))
    except Exception:
        placeholders = ",".join(["%s"] * len(race_ids))
        query = f"""
            SELECT race_id, ticket
            FROM v2_odds_trifecta
            WHERE race_id IN ({placeholders})
            ORDER BY race_id, ticket
        """
        rows = _fetch_dicts(query, tuple(race_ids))

    grouped: Dict[str, List[str]] = {
        str(race_id): []
        for race_id in race_ids
    }
    for row in rows:
        grouped.setdefault(str(row["race_id"]), []).append(
            str(row.get("ticket") or "")
        )

    return {
        race_id: _evaluate_ticket_snapshot(tickets)
        for race_id, tickets in grouped.items()
    }


def _run_fetch_batch(
    repair,
    races: List[Dict[str, Any]],
    workers: int,
    label: str,
    heartbeat_sec: float,
    warn_sec: float,
):
    """
    åRå®äºãã¨ã«é²æãè¡¨ç¤ºããã

    ThreadPoolExecutorèªä½ã§ã¯å®è¡ä¸­Futureãå®å¨ã«å¼·å¶çµäºã§ããªãããã
    å®HTTPã¿ã¤ã ã¢ã¦ãã¯ repair_month_all_pg.py ã® HTTP_TIMEOUT /
    HTTP_MAX_RETRIES ãWINDOWå´ããå¶éããã
    """
    total_saved = 0
    success = 0
    failed: List[Tuple[str, str]] = []

    if not races:
        return success, failed, total_saved

    started_at = time.monotonic()
    future_started: Dict[Any, float] = {}
    warned: set[Any] = set()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures: Dict[Any, Dict[str, Any]] = {}

        for race in races:
            future = executor.submit(
                repair.process_race,
                _normalize_date(race["race_date"]),
                str(race["venue_code"]).zfill(2),
                int(race["race_no"]),
                True,
            )
            futures[future] = race
            future_started[future] = time.monotonic()

        pending = set(futures)
        completed_count = 0

        while pending:
            done, still_pending = wait(
                pending,
                timeout=max(1.0, heartbeat_sec),
                return_when=FIRST_COMPLETED,
            )

            if not done:
                now = time.monotonic()
                longest = sorted(
                    (
                        (
                            now - future_started[future],
                            str(futures[future]["race_id"]),
                        )
                        for future in still_pending
                    ),
                    reverse=True,
                )
                sample = ", ".join(
                    f"{race_id}:{elapsed:.0f}s"
                    for elapsed, race_id in longest[:5]
                )
                print(
                    f"heartbeat {label}: "
                    f"completed={completed_count}/{len(futures)} "
                    f"pending={len(still_pending)} "
                    f"longest=[{sample}]",
                    flush=True,
                )

                for future in still_pending:
                    elapsed = now - future_started[future]
                    if elapsed >= warn_sec and future not in warned:
                        warned.add(future)
                        race_id = str(futures[future]["race_id"])
                        print(
                            f"â ï¸ SLOW_RACE {label} "
                            f"race_id={race_id} elapsed={elapsed:.1f}s",
                            flush=True,
                        )

                pending = still_pending
                continue

            for future in done:
                race = futures[future]
                race_id = str(race["race_id"])
                completed_count += 1
                elapsed = time.monotonic() - future_started[future]
                saved_rows = 0
                status = "OK"
                error_text = ""

                try:
                    result = future.result()
                except Exception as exc:
                    status = "EXCEPTION"
                    error_text = repr(exc)
                    failed.append((race_id, error_text))
                else:
                    if result.ok:
                        success += 1
                        saved_rows = int(result.odds_saved or 0)
                        total_saved += saved_rows
                    else:
                        status = "FAILED"
                        error_text = str(result.error)
                        failed.append(
                            (
                                str(result.race_id),
                                error_text,
                            )
                        )

                print(
                    f"progress {label}: "
                    f"{completed_count}/{len(futures)} "
                    f"race_id={race_id} "
                    f"status={status} "
                    f"elapsed={elapsed:.1f}s "
                    f"saved_rows={saved_rows} "
                    f"success={success} "
                    f"failed={len(failed)} "
                    f"saved_total={total_saved}",
                    flush=True,
                )

                if error_text:
                    print(
                        f"  error race_id={race_id} {error_text}",
                        flush=True,
                    )

            pending = still_pending

    batch_elapsed = time.monotonic() - started_at
    print(
        f"batch_done {label}: "
        f"races={len(races)} success={success} "
        f"failed={len(failed)} saved_rows={total_saved} "
        f"elapsed={batch_elapsed:.1f}s",
        flush=True,
    )
    return success, failed, total_saved


def main() -> None:
    print(
        f"â run_odds_window_pg.py VERSION {VERSION}",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()

    workers = int(
        os.getenv("WINDOW_WORKERS")
        or os.getenv("ODDS_WORKERS")
        or "2"
    )
    max_retries = max(
        0,
        int(os.getenv("WINDOW_ODDS_RETRIES", "2")),
    )
    retry_wait = max(
        0.0,
        float(os.getenv("WINDOW_ODDS_RETRY_WAIT_SEC", "30")),
    )

    heartbeat_sec = max(
        1.0,
        float(os.getenv("WINDOW_ODDS_HEARTBEAT_SEC", "15")),
    )
    race_warn_sec = max(
        heartbeat_sec,
        float(os.getenv("WINDOW_ODDS_RACE_WARN_SEC", "45")),
    )
    window_http_timeout = max(
        5,
        int(os.getenv("WINDOW_HTTP_TIMEOUT", "20")),
    )
    window_http_max_retries = max(
        0,
        int(os.getenv("WINDOW_HTTP_MAX_RETRIES", "1")),
    )

    os.environ["HTTP_TIMEOUT"] = str(window_http_timeout)
    os.environ["HTTP_MAX_RETRIES"] = str(window_http_max_retries)

    # windowåå¾ã¯ç· ååã®äºåãªããºå°ç¨ãç¢ºå®æ±ãããªãã
    os.environ["ODDS_IS_FINAL"] = "0"

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(f"WINDOW_WORKERS={workers}", flush=True)
    print(f"WINDOW_ODDS_RETRIES={max_retries}", flush=True)
    print(f"WINDOW_ODDS_RETRY_WAIT_SEC={retry_wait}", flush=True)
    print(f"WINDOW_ODDS_HEARTBEAT_SEC={heartbeat_sec}", flush=True)
    print(f"WINDOW_ODDS_RACE_WARN_SEC={race_warn_sec}", flush=True)
    print(f"WINDOW_HTTP_TIMEOUT={window_http_timeout}", flush=True)
    print(f"WINDOW_HTTP_MAX_RETRIES={window_http_max_retries}", flush=True)
    print(
        f"DATABASE_URL="
        f"{'OK' if os.getenv('DATABASE_URL') else 'MISSING'}",
        flush=True,
    )
    print(
        "ODDS_IS_FINAL=False "
        "(forced by run_odds_window_pg.py)",
        flush=True,
    )
    print(
        "odds_save_mode=NON_FINAL_UPSERT",
        flush=True,
    )

    all_races = select_window_races(
        target_date,
        window_start,
        window_end,
    )

    # ------------------------------------------------------------
    # Motor2 Forward Shadow target scope export
    # ------------------------------------------------------------
    # STEP1ã§é¸æããããã®windowã®å¨race_idããã
    # run_window_pipeline_pg.py ã®STEP1.5ã¸åä¸processã®ç°å¢å¤æ°ã§æ¸¡ãã
    # skip_full_oddsã§ä»åHTTPåå¾ãçç¥ããRããæ¢ã«å®å¨ãªããºãDBã«ãããã
    # Shadowå¯¾è±¡ããã¯å¤ããªãã
    window_race_ids = [
        str(race.get("race_id") or "").strip()
        for race in all_races
        if str(race.get("race_id") or "").strip()
    ]
    os.environ["MOTOR2_SHADOW_TARGET_RACE_IDS"] = ",".join(window_race_ids)

    print(f"target_races={len(all_races)}", flush=True)
    print(
        f"MOTOR2_SHADOW_TARGET_RACE_IDS exported: "
        f"{len(window_race_ids)} races",
        flush=True,
    )

    if not all_races:
        print(
            "å¯¾è±¡ã¬ã¼ã¹ãªããçµäºãã¾ãã",
            flush=True,
        )
        return

    races = all_races

    if (os.getenv("WINDOW_SKIP_FULL_ODDS") or "0") == "1":
        statuses = select_odds_statuses(
            [str(race["race_id"]) for race in races]
        )
        before = len(races)
        races = [
            race
            for race in races
            if not statuses.get(str(race["race_id"]), {}).get("complete", False)
        ]

        print(
            f"skip_full_odds=1 "
            f"before={before} "
            f"after={len(races)}",
            flush=True,
        )

        if not races:
            print(
                "å¨å¯¾è±¡ã¬ã¼ã¹ã§æå¾ãããä¸é£åã®å¨çµã¿åãããæã£ã¦ãã¾ãã",
                flush=True,
            )
            return

    os.environ["REPAIR_DO_RACES"] = "0"
    os.environ["REPAIR_DO_RESULTS"] = "0"
    os.environ["REPAIR_DO_ODDS"] = "1"
    os.environ.setdefault(
        "REPAIR_SLEEP_SEC",
        os.getenv("SLEEP_SEC", "0.1"),
    )
    os.environ.setdefault(
        "REPAIR_ODDS_WORKERS",
        str(workers),
    )

    repair = importlib.import_module("repair_month_all_pg")

    total_success = 0
    total_saved = 0
    all_failed: List[Tuple[str, str]] = []

    success, failed, saved = _run_fetch_batch(
        repair,
        races,
        workers,
        "initial",
        heartbeat_sec,
        race_warn_sec,
    )
    total_success += success
    total_saved += saved
    all_failed.extend(failed)

    pending = races

    for retry_no in range(1, max_retries + 1):
        statuses = select_odds_statuses(
            [str(race["race_id"]) for race in pending]
        )
        pending = [
            race
            for race in pending
            if not statuses.get(str(race["race_id"]), {}).get("complete", False)
        ]

        if not pending:
            print(
                f"retry_check={retry_no}: "
                "å¨ã¬ã¼ã¹æå¾çµã¿åããå®äº",
                flush=True,
            )
            break

        print(
            f"retry_check={retry_no}: "
            f"incomplete_races={len(pending)}",
            flush=True,
        )

        for race in pending[:30]:
            race_id = str(race["race_id"])
            status = statuses.get(race_id, {})
            print(
                f"  {race_id} "
                f"valid_tickets={status.get('valid_tickets', 0)} "
                f"expected_count={status.get('expected_count', 0)} "
                f"active_lanes={status.get('active_lanes', [])} "
                f"missing={status.get('missing', 0)} "
                f"unexpected={status.get('unexpected', 0)}",
                flush=True,
            )

        if retry_wait > 0:
            print(
                f"retry_wait={retry_wait} sec",
                flush=True,
            )
            time.sleep(retry_wait)

        success, failed, saved = _run_fetch_batch(
            repair,
            pending,
            workers,
            f"retry-{retry_no}",
            heartbeat_sec,
            race_warn_sec,
        )
        total_success += success
        total_saved += saved
        all_failed.extend(failed)

    final_statuses = select_odds_statuses(
        [str(race["race_id"]) for race in all_races]
    )
    incomplete = [
        (
            str(race["race_id"]),
            final_statuses.get(str(race["race_id"]), {}),
        )
        for race in all_races
        if not final_statuses.get(
            str(race["race_id"]),
            {},
        ).get("complete", False)
    ]

    print("=== odds window finished ===", flush=True)
    print(f"target_races={len(all_races)}", flush=True)
    print(
        f"fetch_success_total={total_success}",
        flush=True,
    )
    print(
        f"fetch_failed_total={len(all_failed)}",
        flush=True,
    )
    print(
        f"saved_odds_rows_total={total_saved}",
        flush=True,
    )
    print(
        f"complete_expected={len(all_races) - len(incomplete)}",
        flush=True,
    )
    print(f"incomplete={len(incomplete)}", flush=True)

    if incomplete:
        print("incomplete sample:", flush=True)
        for race_id, status in incomplete[:50]:
            print(
                f"  {race_id} "
                f"valid_tickets={status.get('valid_tickets', 0)} "
                f"expected_count={status.get('expected_count', 0)} "
                f"active_lanes={status.get('active_lanes', [])} "
                f"scratched_lanes={status.get('scratched_lanes', [])} "
                f"duplicates={status.get('duplicates', 0)} "
                f"malformed={status.get('malformed', 0)} "
                f"missing={status.get('missing', 0)} "
                f"unexpected={status.get('unexpected', 0)}",
                flush=True,
            )

    if all_failed:
        print("failed sample:", flush=True)
        for race_id, error in all_failed[:50]:
            print(
                f"  {race_id} {error}",
                flush=True,
            )


if __name__ == "__main__":
    main()