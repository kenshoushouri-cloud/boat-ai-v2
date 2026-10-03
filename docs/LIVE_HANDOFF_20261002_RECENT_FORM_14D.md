# Live Handoff 2026-10-02 — Recent Form 14-day stage

## Protection / SoT
- GitHub `main` = code SoT. Production data SoT = `postgres-hobby-fullhistory-candidate-v4`.
- Railway Active Plan = Hobby.
- Protect candidate-v4, history archive, escrow key, active writers/reports/backtest/historical services, and TOTO.
- Never call `list_variables`. No purchase/plan/volume-size changes. Do not touch the TOTO staged patch.
- **Default cost policy: do not increase cost without reducing system quality.** Prefer existing Hobby resources and sleep/retire unused compute first. Before any new always-on service, Volume/Replica, plan change, or other recurring-cost increase, state the necessity, expected monthly impact, and lower-cost alternative, then obtain explicit user approval.
- Cost reduction applied 2026-10-03: candidate-v3 is `SLEEPING` with its 5GB volume/data preserved; `production-pg-audit-readiness` and `snapshot-audit-readonly` have `sleepApplication=true`. Production candidate-v4 and active crons remain unchanged.
- One task at a time; keep output short.

## Historical Recent Form status
- Method: Official K prior-day only / fill-missing-only.
- Required invariants: SAME_DAY_RESULT_USED=0, FUTURE_RESULT_USED=0, FILL_MISSING_ONLY=1, BUY=0, PROD_MODEL_CHANGE=0.
- Completed through 2026-02-18.
- 2026-02-05..2026-02-18 run `37099767217`: SUCCESS, 12,095 rows updated, fillable_rows=12,095, target_empty_rows=12,096, PASS.
- A prior run `37003791680` failed during Railway CLI download with ECONNRESET before parse/DB work; no DB write occurred.
- After the 14-day PASS, candidate-v4 DISK_USAGE_GB was ~4.4714 current / 4.5053 24h max, below 5GB.
- Fixed command target is now **2026-02-19..2026-03-04 (14 days)**.
- Target update commit: `8fbaf37eb522781a4b99cc7b45dc06916e332fd8`.

## V5 status
- V5 is a **research candidate only**; there is no V5 Production Railway database/service to run or pay for. Production remains V4.
- Target: **2026-10-15 V5 core freeze review**.
- Mandatory gates: V4 >=20 resolved `FORMAL_AVAILABLE` days; S03_M2 >=100 officially evaluated observations; evidence contract clean.
- Last documented settled baseline: V4 **8/20** through 2026-09-28; S03_M2 **63/100** through 2026-09-29. Treat these as last confirmed documented values, not live current counts, until a fresh checkpoint is verified.
- Historical reconstruction gives zero prospective gate credit. No automatic Production/model/selector/stake/purchase activation.

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
