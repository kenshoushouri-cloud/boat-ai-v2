# -*- coding: utf-8 -*-
"""Repeat-safe PRE window wrapper.

This wrapper is dormant unless PRE_NOTIFICATION_DEDUPE_ENABLED=1. It leaves the
existing PRE selection logic untouched and only guards the LINE send path against
re-sending the exact same selected race/ticket set.

The dedupe reservation is stored in v2_line_notifications. A unique partial index
covers active pending/sent reservations. Failed reservations leave the index and
can be retried. Stale pending reservations are released after a short TTL.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from psycopg.types.json import Jsonb

from db_pg import execute
import run_pre_window_pg as pre


DEDUPE_ENABLED = (os.getenv("PRE_NOTIFICATION_DEDUPE_ENABLED", "0") or "0").strip().lower() in {
    "1", "true", "yes", "y", "on"
}
PENDING_TTL_MIN = max(2, int(os.getenv("PRE_NOTIFICATION_DEDUPE_PENDING_TTL_MIN", "10")))


def _build_dedupe_key(core, selected: List[Dict[str, Any]]) -> str:
    identities = sorted(
        {
            f"{str(row.get('race_id') or '').strip()}|{str(row.get('ticket') or '').strip()}"
            for row in selected
            if str(row.get("race_id") or "").strip() and str(row.get("ticket") or "").strip()
        }
    )
    payload = {
        "target_date": core.TARGET_DATE,
        "pre_session": core.PRE_SESSION,
        "selector_mode": core.SELECTOR_MODE,
        "test_mode": bool(core.TEST_MODE),
        "selected": identities,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "pre-v1:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_dedupe_schema() -> None:
    execute("alter table v2_line_notifications add column if not exists dedupe_key text;")
    execute(
        """
        create unique index if not exists ux_v2_line_notifications_pre_dedupe_active
        on v2_line_notifications (dedupe_key)
        where notification_type = 'push_pre_candidate'
          and dedupe_key is not null
          and status in ('pending','sent');
        """
    )


def _release_stale_pending() -> int:
    return execute(
        """
        update v2_line_notifications
        set status = 'failed',
            error_message = 'stale_pending_released_for_retry'
        where notification_type = 'push_pre_candidate'
          and dedupe_key is not null
          and status = 'pending'
          and sent_at < now() - make_interval(mins => %s);
        """,
        (PENDING_TTL_MIN,),
    )


def _reserve(core, message: str, selected: List[Dict[str, Any]], dedupe_key: str) -> bool:
    first = selected[0] if selected else {}
    raw = {
        "selected": selected,
        "pre_session": core.PRE_SESSION,
        "test_mode": core.TEST_MODE,
        "dry_run": core.DRY_RUN,
        "dedupe_key": dedupe_key,
        "dedupe_state": "pending",
    }
    rowcount = execute(
        """
        insert into v2_line_notifications (
            sent_at,
            notification_type,
            race_id,
            message,
            status,
            raw,
            race_date,
            venue_id,
            venue_code,
            race_no,
            decision_id,
            line_to,
            message_type,
            message_text,
            selector_version,
            selector_mode,
            mode_name,
            ticket,
            odds,
            line_response_status,
            line_response_body,
            error_message,
            dedupe_key
        )
        values (
            now(), %s, %s, %s, 'pending', %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        on conflict do nothing;
        """,
        (
            "push_pre_candidate",
            first.get("race_id"),
            message,
            Jsonb(raw),
            core.TARGET_DATE,
            first.get("venue_id"),
            first.get("venue_id"),
            first.get("race_no"),
            None,
            core.LINE_TO if not core.DRY_RUN else "DRY_RUN",
            "push_pre_candidate",
            message,
            "v24_pre_candidate_notifier_pg",
            core.SELECTOR_MODE,
            f"pre_{core.PRE_SESSION}",
            first.get("ticket"),
            first.get("odds"),
            None,
            "",
            "",
            dedupe_key,
        ),
    )
    return rowcount == 1


def _mark_failed(dedupe_key: str, error: str) -> None:
    execute(
        """
        update v2_line_notifications
        set status = 'failed',
            error_message = %s
        where notification_type = 'push_pre_candidate'
          and dedupe_key = %s
          and status = 'pending';
        """,
        (error[:1000], dedupe_key),
    )


def _finalize(core, dedupe_key: str, message: str, status: str, resp: Dict[str, Any], selected: List[Dict[str, Any]]) -> None:
    raw = {
        "selected": selected,
        "pre_session": core.PRE_SESSION,
        "test_mode": core.TEST_MODE,
        "dry_run": core.DRY_RUN,
        "dedupe_key": dedupe_key,
        "dedupe_state": status,
    }
    execute(
        """
        update v2_line_notifications
        set sent_at = now(),
            message = %s,
            status = %s,
            raw = %s,
            message_text = %s,
            line_response_status = %s,
            line_response_body = %s,
            error_message = %s
        where notification_type = 'push_pre_candidate'
          and dedupe_key = %s
          and status = 'pending';
        """,
        (
            message,
            status,
            Jsonb(raw),
            message,
            resp.get("status_code"),
            resp.get("body"),
            "" if status == "sent" else str(resp.get("body") or "")[:1000],
            dedupe_key,
        ),
    )


def _run_v24_with_dedupe(script_path: Path) -> None:
    import v24_pre_candidate_notifier_pg as core

    _ensure_dedupe_schema()
    stale = _release_stale_pending()
    print(f"PRE_DEDUPE_ENABLED=1 stale_pending_released={stale}", flush=True)

    state: Dict[str, Any] = {}
    original_build = core._build_pre_message
    original_send = core._send_line_message

    def build_message(selected):
        state["selected"] = selected
        state["dedupe_key"] = _build_dedupe_key(core, selected)
        return original_build(selected)

    def send_message(message):
        selected = state.get("selected") or []
        dedupe_key = str(state.get("dedupe_key") or "")
        if not dedupe_key:
            raise RuntimeError("PRE dedupe key was not prepared before send")
        if not _reserve(core, message, selected, dedupe_key):
            state["dedupe_skipped"] = True
            print(f"PRE_DEDUPE_RESULT=SKIPPED_DUPLICATE key:{dedupe_key}", flush=True)
            return {
                "dry_run": core.DRY_RUN,
                "status_code": 200,
                "body": "PRE_DEDUPE_SKIPPED_DUPLICATE",
                "dedupe_skipped": True,
            }
        state["reserved"] = True
        try:
            return original_send(message)
        except Exception as exc:
            _mark_failed(dedupe_key, f"send_exception:{type(exc).__name__}:{exc}")
            raise

    def save_notification(message, status, resp, selected):
        if resp.get("dedupe_skipped"):
            return
        dedupe_key = str(state.get("dedupe_key") or "")
        if not dedupe_key or not state.get("reserved"):
            raise RuntimeError("PRE dedupe reservation missing before finalize")
        _finalize(core, dedupe_key, message, status, resp, selected)
        print(f"PRE_DEDUPE_RESULT=FINALIZED status:{status} key:{dedupe_key}", flush=True)

    core._build_pre_message = build_message
    core._send_line_message = send_message
    core._save_pre_notification = save_notification
    core.main()


def _patched_run_script(script_path: Path, display_name: str, *, required: bool) -> None:
    if script_path.name != "v24_pre_candidate_notifier_pg.py":
        return _ORIGINAL_RUN_SCRIPT(script_path, display_name, required=required)

    if not DEDUPE_ENABLED:
        print("PRE_DEDUPE_ENABLED=0; existing notifier path is unchanged", flush=True)
        return _ORIGINAL_RUN_SCRIPT(script_path, display_name, required=required)

    if not script_path.exists():
        if required:
            raise FileNotFoundError(script_path)
        print(f"WARNING: {display_name} が見つかりません: {script_path}", flush=True)
        return

    print(f"{display_name} をrepeat-safe dedupe wrapperで実行します。", flush=True)
    _run_v24_with_dedupe(script_path)


_ORIGINAL_RUN_SCRIPT = pre._run_script
pre._run_script = _patched_run_script


if __name__ == "__main__":
    pre.main()
