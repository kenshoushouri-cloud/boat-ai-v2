# Live Handoff 2026-10-02 — Recent Form 14-day stage

## Protection / SoT
- GitHub `main` = code SoT. Production data SoT = `postgres-hobby-fullhistory-candidate-v4`.
- Railway Active Plan = Hobby.
- Protect candidate-v4, history archive, escrow key, active writers/reports/backtest/historical services, and TOTO.
- Never call `list_variables`. No purchase/plan/volume-size changes. Do not touch the TOTO staged patch.
- One task at a time; keep output short.

## Historical Recent Form status
- Method: Official K prior-day only / fill-missing-only.
- Required invariants: SAME_DAY_RESULT_USED=0, FUTURE_RESULT_USED=0, FILL_MISSING_ONLY=1, BUY=0, PROD_MODEL_CHANGE=0.
- Completed through 2025-09-17.
- 2025-09-04..09-17 run `37021852663`: SUCCESS, 12,019 rows updated, fillable_rows=12,019, target_empty_rows=12,024, PASS.
- A prior run `37003791680` failed during Railway CLI download with ECONNRESET before parse/DB work; no DB write occurred.
- After the 14-day PASS, candidate-v4 DISK_USAGE_GB was ~4.1372 current / 4.3526 24h max, below 5GB.
- Fixed command target is now **2025-09-18..2025-10-01 (14 days)**.
- Target update commit: `1001b66710fda889c2990f35b7e1d9d2cb10ed87`.

## Next single task
1. User posts to Issue #42: `/railway historical-recent-form-next`.
2. After user says complete, live-check only the newest Historical prior-day recent_form `issue_comment` run.
3. If running: do not write anything else.
4. If completed: verify SUCCESS/FAILURE, per-day updated counts, HIST_RECENT_FORM_RESULT, SAME_DAY_RESULT_USED=0, FUTURE_RESULT_USED=0, fill-missing-only.
5. Only after SUCCESS, separately re-check candidate-v4 DISK_USAGE_GB.

## Token / timeout control
- Do **not** call the bulk `fetch_issue_comments` for Issue #42; its history is huge and quickly fills chat context.
- Prefer latest Actions run + job logs. If Issue #42 tail is truly needed, fetch only a small paginated tail through the GitHub REST endpoint.
- Do not load old handoffs unless a specific historical decision is required.
- Do not re-fetch unrelated Railway inventory, variables, or services.
- Re-fetch only live state needed for the current single task.

`RECENT_FORM_14D_NEXT / HOBBY / PURCHASE_FALSE / TOKEN_COMPACT`
