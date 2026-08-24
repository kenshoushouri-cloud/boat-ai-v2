# -*- coding: utf-8 -*-
"""Repeat-safe PRE window wrapper.

This wrapper is dormant unless PRE_NOTIFICATION_DEDUPE_ENABLED=1. It leaves the
existing PRE selection/model logic untouched and guards only the LINE send path.

Two levels of concurrency-safe reservation are used:
1. Per-candidate claims keyed by race/date/session/selector/test/dry-run + ticket.
   This prevents the same race/ticket from being re-sent when the surrounding
   selected set changes on a later refresh.
2. A message-level dedupe key in v2_line_notifications as a final guard.

Failed/stale pending reservations become retryable. Existing sent PRE rows are
backfilled into the claim table when dedupe is enabled so enabling this wrapper
does not forget notifications sent before the ticket-level claim table existed.
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
        "dry_run": bool(core.DRY_RUN),
        "selected": identities,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "pre-v2:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    execute(
        """
        create table if not exists v2_pre_notification_claims (
            id bigserial primary key,
            race_date date not null,
            pre_session text not null,
            selector_mode text not null,
            test_mode boolean not null,
            dry_run boolean not null default false,
            race_id text not null,
            ticket text not null,
            status text not null,
            claimed_at timestamptz not null default now(),
            notification_dedupe_key text,
            error_message text not null default ''
        );
        """
    )
    execute(
        """
        create unique index if not exists ux_v2_pre_notification_claims_active
        on v2_pre_notification_claims (
            race_date, pre_session, selector_mode, test_mode, dry_run, race_id, ticket
        )
        where status in ('pending','sent');
        """
    )


def _backfill_sent_claims() -> int:
    """Seed ticket-level claims from existing successful PRE notification JSON."""
    return execute(
        """
        insert into v2_pre_notification_claims (
            race_date, pre_session, selector_mode, test_mode, dry_run,
            race_id, ticket, status, claimed_at, notification_dedupe_key,
            error_message
        )
        select distinct
            n.race_date,
            coalesce(nullif(n.raw::jsonb ->> 'pre_session', ''),
                     nullif(replace(coalesce(n.mode_name, ''), 'pre_', ''), ''),
                     'unknown'),
            coalesce(nullif(n.selector_mode, ''), 'unknown'),
            case lower(coalesce(n.raw::jsonb ->> 'test_mode', 'false'))
                when 'true' then true when '1' then true else false end,
            case lower(coalesce(n.raw::jsonb ->> 'dry_run', 'false'))
                when 'true' then true when '1' then true else false end,
            item ->> 'race_id',
            item ->> 'ticket',
            'sent',
            coalesce(n.sent_at, now()),
            n.dedupe_key,
            'backfilled_from_v2_line_notifications'
        from v2_line_notifications n
        cross join lateral jsonb_array_elements(
            case
                when n.raw is not null
                 and jsonb_typeof(n.raw::jsonb -> 'selected') = 'array'
                then n.raw::jsonb -> 'selected'
                else '[]'::jsonb
            end
        ) item
        where n.notification_type = 'push_pre_candidate'
          and n.status = 'sent'
          and n.race_date is not null
          and coalesce(item ->> 'race_id', '') <> ''
          and coalesce(item ->> 'ticket', '') <> ''
        on conflict do nothing;
        """
    )


def _release_stale_pending() -> int:
    message_rows = execute(
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
    claim_rows = execute(
        """
        update v2_pre_notification_claims
        set status = 'failed',
            error_message = 'stale_pending_released_for_retry'
        where status = 'pending'
          and claimed_at < now() - make_interval(mins => %s);
        """,
        (PENDING_TTL_MIN,),
    )
    return message_rows + claim_rows


def _claim_unseen(core, selected: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    claimed: List[Dict[str, Any]] = []
    for row in selected:
        race_id = str(row.get("race_id") or "").strip()
        ticket = str(row.get("ticket") or "").strip()
        if not race_id or not ticket:
            continue
        rowcount = execute(
            """
            insert into v2_pre_notification_claims (
                race_date, pre_session, selector_mode, test_mode, dry_run,
                race_id, ticket, status, claimed_at, error_message
            )
            values (%s,%s,%s,%s,%s,%s,%s,'pending',now(),'')
            on conflict do nothing;
            """,
            (
                core.TARGET_DATE,
                core.PRE_SESSION,
                core.SELECTOR_MODE,
                bool(core.TEST_MODE),
                bool(core.DRY_RUN),
                race_id,
                ticket,
            ),
        )
        if rowcount == 1:
            claimed.append(row)
    return claimed


def _mark_claims(
    core,
    selected: List[Dict[str, Any]],
    status: str,
    dedupe_key: str,
    error: str = "",
) -> None:
    for row in selected:
        race_id = str(row.get("race_id") or "").strip()
        ticket = str(row.get("ticket") or "").strip()
        if not race_id or not ticket:
            continue
        execute(
            """
            update v2_pre_notification_claims
            set status = %s,
                notification_dedupe_key = %s,
                error_message = %s
            where race_date = %s
              and pre_session = %s
              and selector_mode = %s
              and test_mode = %s
              and dry_run = %s
              and race_id = %s
              and ticket = %s
              and status = 'pending';
            """,
            (
                status,
                dedupe_key or None,
                error[:1000],
                core.TARGET_DATE,
                core.PRE_SESSION,
                core.SELECTOR_MODE,
                bool(core.TEST_MODE),
                bool(core.DRY_RUN),
                race_id,
                ticket,
            ),
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
    backfilled = _backfill_sent_claims()
    stale = _release_stale_pending()
    print(
        f"PRE_DEDUPE_ENABLED=1 ticket_level=1 backfilled_claims={backfilled} "
        f"stale_pending_released={stale}",
        flush=True,
    )

    state: Dict[str, Any] = {}
    original_build = core._build_pre_message
    original_send = core._send_line_message

    def build_message(selected):
        original_count = len(selected)
        claimed = _claim_unseen(core, selected)
        selected[:] = claimed
        state["selected"] = selected
        state["original_count"] = original_count
        if not selected:
            state["no_new_items"] = True
            print(
                f"PRE_DEDUPE_ITEMS=original:{original_count} new:0 already_claimed:{original_count}",
                flush=True,
            )
            return original_build(selected)

        state["dedupe_key"] = _build_dedupe_key(core, selected)
        print(
            f"PRE_DEDUPE_ITEMS=original:{original_count} new:{len(selected)} "
            f"already_claimed:{original_count-len(selected)}",
            flush=True,
        )
        return original_build(selected)

    def send_message(message):
        selected = state.get("selected") or []
        if state.get("no_new_items"):
            state["dedupe_skipped"] = True
            print("PRE_DEDUPE_RESULT=SKIPPED_ALL_ALREADY_SENT", flush=True)
            return {
                "dry_run": core.DRY_RUN,
                "status_code": 200,
                "body": "PRE_DEDUPE_SKIPPED_ALL_ALREADY_SENT",
                "dedupe_skipped": True,
            }

        dedupe_key = str(state.get("dedupe_key") or "")
        if not dedupe_key:
            _mark_claims(core, selected, "failed", "", "missing_message_dedupe_key")
            raise RuntimeError("PRE dedupe key was not prepared before send")
        if not _reserve(core, message, selected, dedupe_key):
            _mark_claims(core, selected, "failed", dedupe_key, "message_reservation_conflict")
            state["dedupe_skipped"] = True
            print(f"PRE_DEDUPE_RESULT=SKIPPED_DUPLICATE_MESSAGE key:{dedupe_key}", flush=True)
            return {
                "dry_run": core.DRY_RUN,
                "status_code": 200,
                "body": "PRE_DEDUPE_SKIPPED_DUPLICATE_MESSAGE",
                "dedupe_skipped": True,
            }
        state["reserved"] = True
        try:
            return original_send(message)
        except Exception as exc:
            error = f"send_exception:{type(exc).__name__}:{exc}"
            _mark_failed(dedupe_key, error)
            _mark_claims(core, selected, "failed", dedupe_key, error)
            raise

    def save_notification(message, status, resp, selected):
        if resp.get("dedupe_skipped"):
            return
        dedupe_key = str(state.get("dedupe_key") or "")
        if not dedupe_key or not state.get("reserved"):
            _mark_claims(core, selected, "failed", dedupe_key, "reservation_missing_before_finalize")
            raise RuntimeError("PRE dedupe reservation missing before finalize")
        _finalize(core, dedupe_key, message, status, resp, selected)
        claim_status = "sent" if status == "sent" else "failed"
        claim_error = "" if claim_status == "sent" else str(resp.get("body") or "")[:1000]
        _mark_claims(core, selected, claim_status, dedupe_key, claim_error)
        print(
            f"PRE_DEDUPE_RESULT=FINALIZED status:{status} items:{len(selected)} key:{dedupe_key}",
            flush=True,
        )

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

    print(f"{display_name} をticket-level repeat-safe dedupe wrapperで実行します。", flush=True)
    _run_v24_with_dedupe(script_path)


_ORIGINAL_RUN_SCRIPT = pre._run_script
pre._run_script = _patched_run_script


if __name__ == "__main__":
    pre.main()
