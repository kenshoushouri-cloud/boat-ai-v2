# PRE Ticket Dedupe Enablement Runbook — 2026-09-12

Status: review-only. **Do not execute without explicit Production DB-schema + Railway configuration approval.**

## Why this exists

Current PRE windows overlap: morning covers 08:30–10:15 and day covers 09:45–15:00. Current Production logs show `PRE_NOTIFICATION_DEDUPE_ENABLED=False`, so the base v24 PRE notifier can select the same race/ticket again in a later overlapping window if it remains eligible.

The repeat-safe wrapper is already implemented and tested in main, but dormant by default.

## Existing evidence

- PR #163 merged ticket-level claims and message-level dedupe.
- PR #165 merged disposable PostgreSQL integration tests.
- Claim identity includes race date, PRE session, selector mode, test mode, dry-run mode, race_id, and ticket.
- Morning and day normally both resolve to PRE session `day`, so an unchanged day candidate can be suppressed across the overlap when selector/test/dry-run identity also matches.
- Night candidates remain a distinct PRE session.
- PRE and FINAL remain separate notification stages; FINAL intentionally does not use PRE history as a suppression key.

## First activation side effects

Enabling `PRE_NOTIFICATION_DEDUPE_ENABLED=1` switches `run_window_pipeline_pg.py` from `run_pre_window_pg.py` to `run_pre_window_deduped_pg.py`.

The wrapper's first activation performs idempotent Production DDL before sending:

1. adds `dedupe_key` to `v2_line_notifications` if absent;
2. creates a partial unique active-message dedupe index if absent;
3. creates `v2_pre_notification_claims` if absent;
4. creates its partial unique active-claim index if absent;
5. backfills successful historical PRE selected race/tickets into claims;
6. releases stale pending reservations before normal claim/send processing.

Therefore this is not a flag-only operational change. It crosses the Production DB-schema approval boundary.

## Required prechecks before approval/execution

- Confirm Boat Production `stagedChanges=null`.
- Confirm current PRE services still use main and `run_window_pipeline_pg.py`.
- Confirm no overlapping PRE pipeline is currently executing.
- Confirm current DB capacity/headroom.
- Confirm the intended `PRE_DAILY_LINE_LIMIT` value and resolve the separate alias gap before or together with enablement.
- Decide explicitly whether the PRE daily quota should remain the current global successful-LINE count or become PRE-type-specific. Do not silently change quota semantics as part of dedupe rollout.
- Re-run/verify existing dedupe PostgreSQL safety tests and repository isolation checks.

## Minimal approved rollout sequence

If separately approved:

1. Apply only the reviewed schema/enablement changes; do not change model logic, selector thresholds, Course/Opponent coefficients, FINAL behavior, purchase behavior, or LINE recipient/token.
2. Enable the same dedupe setting on all PRE window services so morning/day overlap has consistent semantics.
3. Let the next natural PRE window run; do not manually backfill or manually rerun a candidate window.
4. Require logs to show `PRE_DEDUPE_ENABLED=1` and record backfilled/stale counts.
5. If candidates exist, verify only newly claimed race/tickets are sent.
6. Verify a later overlapping PRE window cannot resend an already-sent day race/ticket with the same selector/test/dry-run identity.
7. Verify FINAL remains independent and can still send a later FINAL BUY notification when legitimately eligible.
8. Verify LINE daily/monthly capacity guards still behave according to the separately chosen quota policy.

## Fail/rollback rule

If any schema, claim, send, or compatibility error appears:

- disable `PRE_NOTIFICATION_DEDUPE_ENABLED` on PRE services;
- do not delete dedupe history or claims during incident handling;
- do not drop schema automatically;
- do not manually resend candidate messages;
- investigate from logs and immutable sent/claim records first.

Leaving the additive dedupe schema in place while the flag is disabled is safer than destructive rollback.

## Promotion boundary

Successful natural operation permits only continued use/review of PRE dedupe. It does not authorize model/threshold changes, Course/Opponent promotion, auto-purchase, or changes to FINAL notification semantics.

Gate: `RUNBOOK_ONLY / EXISTING_DEDUPE_CODE_AND_DISPOSABLE_PG_TESTS_PRESENT / PRODUCTION_DDL_REQUIRED_FOR_FIRST_ENABLE / ALL_PRE_SERVICES_MUST_BE_CONSISTENT / NATURAL_RUN_VALIDATION_REQUIRED / NO_EXECUTION_AUTHORIZED`.
