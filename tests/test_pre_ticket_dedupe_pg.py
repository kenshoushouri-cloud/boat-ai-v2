# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from types import SimpleNamespace

import psycopg
from psycopg.types.json import Jsonb

os.environ.setdefault("PRE_NOTIFICATION_DEDUPE_ENABLED", "1")

import run_pre_window_deduped_pg as dedupe


DB = os.environ["DATABASE_URL"]


def reset_schema() -> None:
    with psycopg.connect(DB, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("drop table if exists v2_pre_notification_claims cascade")
            cur.execute("drop table if exists v2_line_notifications cascade")
            cur.execute(
                """
                create table v2_line_notifications (
                    id bigserial primary key,
                    sent_at timestamptz,
                    notification_type text,
                    race_id text,
                    message text,
                    status text,
                    raw jsonb,
                    race_date date,
                    venue_id text,
                    venue_code text,
                    race_no integer,
                    decision_id bigint,
                    line_to text,
                    message_type text,
                    message_text text,
                    selector_version text,
                    selector_mode text,
                    mode_name text,
                    ticket text,
                    odds numeric,
                    line_response_status integer,
                    line_response_body text,
                    error_message text
                )
                """
            )


def scalar(sql: str, params=()):
    with psycopg.connect(DB, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None


def main() -> None:
    reset_schema()
    dedupe._ensure_dedupe_schema()

    historical = {
        "selected": [{"race_id": "20260824_10_01", "ticket": "1-2-3"}],
        "pre_session": "day",
        "test_mode": True,
        "dry_run": False,
    }
    with psycopg.connect(DB, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into v2_line_notifications (
                    sent_at,notification_type,race_id,status,raw,race_date,
                    selector_mode,mode_name,ticket
                ) values (now(),'push_pre_candidate','20260824_10_01','sent',%s,
                          '2026-08-24','balanced','pre_day','1-2-3')
                """,
                (Jsonb(historical),),
            )

    backfilled = dedupe._backfill_sent_claims()
    assert backfilled == 1, backfilled

    core = SimpleNamespace(
        TARGET_DATE="2026-08-24",
        PRE_SESSION="day",
        SELECTOR_MODE="balanced",
        TEST_MODE=True,
        DRY_RUN=False,
        LINE_TO="test-line-to",
    )

    already = [{"race_id": "20260824_10_01", "ticket": "1-2-3"}]
    assert dedupe._claim_unseen(core, already) == []

    fresh = [{
        "race_id": "20260824_10_01",
        "ticket": "1-3-2",
        "venue_id": "10",
        "race_no": 1,
        "odds": 12.3,
    }]
    claimed = dedupe._claim_unseen(core, fresh)
    assert len(claimed) == 1
    key = dedupe._build_dedupe_key(core, claimed)
    assert key.startswith("pre-v2:")
    assert dedupe._reserve(core, "test message", claimed, key) is True
    assert dedupe._reserve(core, "test message", claimed, key) is False
    dedupe._finalize(core, key, "test message", "sent", {"status_code": 200, "body": "OK"}, claimed)
    dedupe._mark_claims(core, claimed, "sent", key, "")
    assert dedupe._claim_unseen(core, fresh) == []

    retry_item = [{"race_id": "20260824_10_02", "ticket": "2-1-3"}]
    retry_claim = dedupe._claim_unseen(core, retry_item)
    assert len(retry_claim) == 1
    dedupe._mark_claims(core, retry_claim, "failed", "", "synthetic_failure")
    assert len(dedupe._claim_unseen(core, retry_item)) == 1

    stale_item = [{"race_id": "20260824_10_03", "ticket": "3-1-2"}]
    assert len(dedupe._claim_unseen(core, stale_item)) == 1
    with psycopg.connect(DB, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update v2_pre_notification_claims
                set claimed_at=now()-interval '30 minutes'
                where race_id='20260824_10_03' and ticket='3-1-2' and status='pending'
                """
            )
    released = dedupe._release_stale_pending()
    assert released >= 1
    assert len(dedupe._claim_unseen(core, stale_item)) == 1

    dry_core = SimpleNamespace(**vars(core))
    dry_core.DRY_RUN = True
    assert dedupe._build_dedupe_key(dry_core, fresh) != dedupe._build_dedupe_key(core, fresh)
    assert len(dedupe._claim_unseen(dry_core, already)) == 1

    sent_claims = scalar("select count(*) from v2_pre_notification_claims where status='sent'")
    assert sent_claims >= 2, sent_claims
    print("PRE_TICKET_DEDUPE_POSTGRES_TEST=PASS")


if __name__ == "__main__":
    main()
