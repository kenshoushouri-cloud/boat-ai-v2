# PRE LINE Limit Alias Review — 2026-09-12

Research-only note. No Production configuration or runtime behavior is changed by this branch.

## 1. PRE-specific limit alias gap

Read-only Railway config inspection shows `cron-window-morning`, `cron-window-day`, and `cron-window-night` expose `PRE_DAILY_LINE_LIMIT`, while current `v24_pre_candidate_notifier_pg.py` reads `DAILY_LINE_LIMIT` (default `3`) and current `run_pre_window_pg.py` does not map the PRE-specific variable to that legacy name.

Therefore the configured `PRE_DAILY_LINE_LIMIT` value is not consumed by the current non-deduped PRE path. The effective PRE daily line limit falls back to `DAILY_LINE_LIMIT` if separately supplied, otherwise `3`.

The pure contract in this Draft freezes only a proposed future precedence: `PRE_DAILY_LINE_LIMIT` -> legacy `DAILY_LINE_LIMIT` -> default `3`. Invalid/nonpositive configured values fail closed.

## 2. Current daily counter is not PRE-specific

The current v24 PRE `_count_sent_notifications()` query counts every `v2_line_notifications` row with `status='sent'` for the date/month. It does not filter `notification_type='push_pre_candidate'`.

That is conservative for LINE capacity because other successful notification types can consume the PRE guard, but it does not implement a truly independent PRE quota. In particular, a FINAL/report notification sent earlier the same day may make the PRE guard stop sooner than a PRE-only policy would.

This Draft does **not** choose or change that policy. Any future runtime change must explicitly decide whether PRE quota accounting should remain global/conservative or become PRE-type-specific.

## 3. DRY_RUN rows also consume the current counter

In the base v24 PRE path, `_send_line_message()` returns synthetic HTTP 200 during `DRY_RUN`, after which the caller records the notification row with `status='sent'`. `_save_pre_notification()` marks `line_to='DRY_RUN'` and preserves `raw.dry_run=true`, but `_count_sent_notifications()` does not exclude those rows.

Therefore a same-day PRE dry-run against the Production database can consume the current daily/monthly guard even though no external LINE API call occurred. This fails safe against over-sending, but can suppress a later legitimate live PRE notification. The existing ticket-level dedupe identity correctly distinguishes dry-run from live; quota accounting currently does not.

No runtime change is made here. Any later quota-policy change must explicitly decide whether dry-run rows count toward the operational LINE quota.

## 4. Overlapping PRE windows and dormant dedupe

The configured PRE windows overlap: morning is 08:30–10:15 and day is 09:45–15:00. Current natural logs show `PRE_NOTIFICATION_DEDUPE_ENABLED=False`, and the three PRE Railway services do not expose that variable, so the existing `run_pre_window_deduped_pg.py` wrapper is dormant.

The base v24 notifier has no ticket-level duplicate suppression. Therefore an unchanged candidate in the 09:45–10:15 overlap can in principle be selected again in the later day window, subject to the existing global daily/monthly guards.

A dormant dedupe implementation already exists in main with concurrency-safe per-ticket claims, message-level dedupe, historical sent-row backfill, retryable failed/stale claims, and PostgreSQL/safety tests. Enabling it is a separate Production configuration/schema behavior decision and is **not** authorized by this research note.

## 5. PRE vs FINAL are separate stages

FINAL notification dedupe intentionally ignores PRE candidate notices. A PRE candidate notice followed by a later FINAL BUY notice for the same race/ticket is therefore stage-specific behavior, not an accidental same-stage duplicate. This review does not propose merging those stages.

## Safe next review

Before any Production change, review these independently:

- the intended numeric value of `PRE_DAILY_LINE_LIMIT`;
- whether PRE quota accounting should count only PRE messages or all sent LINE notifications;
- whether PRE dry-run rows should be excluded from the operational live-send quota;
- whether to enable the already-tested PRE ticket-level dedupe wrapper for overlap/retry protection;
- observability showing the effective PRE limit, its source variable, quota scope, and dedupe state in natural logs.

Gate: `CONFIG_ALIAS_GAP_CONFIRMED / GLOBAL_COUNTER_SCOPE_CONFIRMED / DRYRUN_SENT_ROWS_COUNT_TOWARD_CURRENT_GUARD / OVERLAP_DUPLICATE_PATH_POSSIBLE_WITH_DEDUPE_DISABLED / EXISTING_DEDUPE_WRAPPER_REVIEWABLE / FINAL_STAGE_SEPARATE / NO_PRODUCTION_CHANGE`.
