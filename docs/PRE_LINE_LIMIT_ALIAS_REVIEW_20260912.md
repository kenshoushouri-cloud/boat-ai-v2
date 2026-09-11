# PRE LINE Limit Alias Review — 2026-09-12

Research-only note. No Production configuration or runtime behavior is changed by this branch.

Read-only Railway config inspection shows `cron-window-morning`, `cron-window-day`, and `cron-window-night` expose `PRE_DAILY_LINE_LIMIT`, while current `v24_pre_candidate_notifier_pg.py` reads `DAILY_LINE_LIMIT` (default `3`) and current `run_pre_window_pg.py` does not map the PRE-specific variable to that legacy name.

Therefore the configured `PRE_DAILY_LINE_LIMIT` value is not consumed by the current non-deduped PRE path. The effective PRE daily line limit falls back to `DAILY_LINE_LIMIT` if separately supplied, otherwise `3`.

A safe correction should be reviewed separately, remain PRE-only, preserve the monthly limit, not alter FINAL notification limits, and add explicit observability/tests before any Production wiring.

Gate: `CONFIG_ALIAS_GAP_CONFIRMED / EFFECTIVE_PRE_DEFAULT_3_UNLESS_GENERIC_SET / FINAL_PATH_UNCHANGED / NO_PRODUCTION_CHANGE`.
