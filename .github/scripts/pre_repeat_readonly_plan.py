# -*- coding: utf-8 -*-
"""Read-only planner for repeated PRE execution.

Reuses the production v24 selection code against current Railway PostgreSQL rows,
but suppresses schema DDL, LINE sending, notification persistence, and candidate
Shadow collection. It is intended to answer: if PRE were evaluated again now,
which active window(s) are ready and how many candidates would be selected?
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from typing import Dict, List

JST = timezone(timedelta(hours=9))
WINDOWS = {
    "morning": ("08:30", "10:15"),
    "day": ("09:45", "15:00"),
    "night": ("14:45", None),
}


def _clock(date_str: str, hhmm: str) -> datetime:
    return datetime.strptime(f"{date_str} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def _active_windows(now: datetime, date_str: str) -> List[str]:
    out: List[str] = []
    for name, (start, end) in WINDOWS.items():
        start_at = _clock(date_str, start)
        end_at = _clock(date_str, end) if end else _clock(date_str, "23:59") + timedelta(minutes=1)
        if start_at <= now < end_at:
            out.append(name)
    return out


def _run_child(window_name: str) -> int:
    import run_pre_window_pg as win

    target_date = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
    start, end = WINDOWS[window_name]
    raw = win.select_window_races(target_date, start, end)
    races, run_class, skipped = win._apply_live_guard(raw, target_date)
    if run_class != "live":
        print(
            f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} result:BLOCKED_NONLIVE "
            f"run_class:{run_class}",
            flush=True,
        )
        return 0

    race_ids = [str(r.get("race_id") or "") for r in races if str(r.get("race_id") or "")]
    session = "night" if window_name == "night" else "day"
    os.environ["TARGET_DATE"] = target_date
    os.environ["WINDOW_NAME"] = window_name
    os.environ["PRE_SESSION"] = session
    os.environ["TARGET_RACE_IDS"] = ",".join(race_ids)
    os.environ["DRY_RUN"] = "1"
    os.environ["TEST_MODE"] = "1"
    os.environ.setdefault("SELECTOR_MODE", "balanced")

    print(
        f"PRE_REPEAT_PLAN_SCOPE=window:{window_name} session:{session} "
        f"window_races:{len(raw)} future_races:{len(races)} live_guard_skipped:{skipped}",
        flush=True,
    )
    if not race_ids:
        print(
            f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} races:0 ready:0 candidates:0 selected:0 "
            "result:NO_FUTURE_RACES",
            flush=True,
        )
        return 0

    import v24_pre_candidate_notifier_pg as core

    core._ensure_line_notification_columns = lambda: None
    core.DRY_RUN = True
    core.TEST_MODE = True
    core.TARGET_RACE_ID_SET = set(race_ids)

    selected_rows: List[Dict[str, object]] = []

    def _capture_message(selected):
        selected_rows[:] = [dict(row) for row in selected]
        return "PRE_REPEAT_READ_ONLY_MESSAGE_SUPPRESSED"

    def _suppress_send(_message):
        return {"dry_run": True, "status_code": 200, "body": "PRE_REPEAT_READ_ONLY_SEND_SUPPRESSED"}

    def _suppress_save(_message, _status, _resp, _selected):
        return None

    core._build_pre_message = _capture_message
    core._send_line_message = _suppress_send
    core._save_pre_notification = _suppress_save

    buf = io.StringIO()
    with redirect_stdout(buf):
        core.main()
    output = buf.getvalue()

    summary = re.search(
        r"races=(\d+) ready_races=(\d+) candidates=(\d+) selected=(\d+) "
        r"skipped_not_ready=(\d+) skipped_entries=(\d+) skipped_odds=(\d+) "
        r"skipped_session=(\d+)",
        output,
    )
    if summary:
        values = [int(x) for x in summary.groups()]
        print(
            f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} races:{values[0]} ready:{values[1]} "
            f"candidates:{values[2]} selected:{values[3]} skipped_not_ready:{values[4]} "
            f"skipped_entries:{values[5]} skipped_odds:{values[6]} skipped_session:{values[7]} "
            "result:PASS_READ_ONLY",
            flush=True,
        )
    else:
        guard = re.search(r"LINE送信上限ガード: ([^\n]+)", output)
        if guard:
            print(
                f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} result:LIVE_USAGE_GUARD "
                f"detail:{guard.group(1).strip()}",
                flush=True,
            )
        elif "仮候補はありません" in output:
            print(
                f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} candidates:0 selected:0 "
                "result:PASS_READ_ONLY_NO_SELECTION",
                flush=True,
            )
        else:
            print(
                f"PRE_REPEAT_PLAN_WINDOW=name:{window_name} result:UNEXPECTED_OUTPUT",
                flush=True,
            )
            return 2

    if selected_rows:
        sample = ",".join(
            f"{str(row.get('race_id') or '')}:{str(row.get('ticket') or '')}:{float(row.get('odds') or 0):.1f}"
            for row in selected_rows[:10]
        )
        print(
            f"PRE_REPEAT_PLAN_SELECTED_SAMPLE=window:{window_name} count:{len(selected_rows)} items:{sample}",
            flush=True,
        )
    else:
        print(
            f"PRE_REPEAT_PLAN_SELECTED_SAMPLE=window:{window_name} count:0 items:none",
            flush=True,
        )
    print(
        f"PRE_REPEAT_PLAN_SUPPRESSION=window:{window_name} ddl:off line_send:off notification_save:off candidate_shadow:off",
        flush=True,
    )
    return 0


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    now = datetime.now(JST)
    target_date = (os.getenv("TARGET_DATE") or now.strftime("%Y-%m-%d")).strip()
    today = now.strftime("%Y-%m-%d")
    child_window = (os.getenv("PRE_REPEAT_CHILD_WINDOW") or "").strip().lower()

    if child_window:
        if child_window not in WINDOWS:
            raise ValueError(f"invalid PRE_REPEAT_CHILD_WINDOW: {child_window}")
        return _run_child(child_window)

    print("PRE_REPEAT_PLAN_MODE=read_only_existing_v24_selection", flush=True)
    print("PRE_REPEAT_PLAN_POLICY=no_ddl_no_db_writes_no_line_no_candidate_shadow_no_final", flush=True)
    print(f"PRE_REPEAT_PLAN_DATE={target_date}", flush=True)
    print(f"PRE_REPEAT_PLAN_NOW_JST={now.isoformat(timespec='seconds')}", flush=True)
    if target_date != today:
        print(f"PRE_REPEAT_PLAN_RESULT=BLOCKED_NONLIVE_DATE today:{today}", flush=True)
        return 0

    active = _active_windows(now, target_date)
    print(f"PRE_REPEAT_PLAN_ACTIVE_WINDOWS={','.join(active) if active else 'none'}", flush=True)
    if not active:
        print("PRE_REPEAT_PLAN_RESULT=PASS_READ_ONLY_NO_ACTIVE_WINDOW", flush=True)
        return 0

    rc = 0
    for name in active:
        env = os.environ.copy()
        env["TARGET_DATE"] = target_date
        env["PRE_REPEAT_CHILD_WINDOW"] = name
        proc = subprocess.run(
            [sys.executable, "-u", __file__],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.returncode != 0:
            rc = proc.returncode
            print(f"PRE_REPEAT_PLAN_CHILD_ERROR=window:{name} returncode:{proc.returncode}", flush=True)
            if proc.stderr:
                print(f"PRE_REPEAT_PLAN_CHILD_STDERR=window:{name} suppressed_nonprefixed_error", flush=True)

    print(f"PRE_REPEAT_PLAN_RESULT={'PASS_READ_ONLY' if rc == 0 else 'FAIL'}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
