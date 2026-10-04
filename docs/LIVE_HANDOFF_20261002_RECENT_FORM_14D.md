# Live Handoff 2026-10-02 — Recent Form 14-day stage

## Protection / SoT
- GitHub `main` = code SoT. Production data SoT = `postgres-hobby-fullhistory-candidate-v4`.
- Railway Active Plan = Hobby.
- Protect candidate-v4, history archive, escrow key, active writers/reports/backtest/historical services, and TOTO.
- Never call `list_variables`. No purchase/plan/volume-size changes. Do not touch the TOTO staged patch.
- **Operating-cost hard target: keep Railway at or below USD 20/month even after missing-data acquisition/backfills resume; lower is better.** Cost is a first-class design constraint, but do not reduce required Production, backtest, live-test, learning, data-acquisition, restore-safety, or system-building capability merely to save cost.
- **Default cost policy: do not increase cost without reducing system quality.** Prefer existing Hobby resources and sleep/retire unused compute first. Before any new always-on service, Volume/Replica, plan change, or other recurring-cost increase, state the necessity, expected monthly impact, and lower-cost alternative, then obtain explicit user approval.
- **Do not use Railway Agent / Railway AI.** Its token usage can affect Railway billing and has already affected a prior invoice. Use direct read-only Railway status/metrics/logs/docs calls instead.
- For missing-data/backfill work, prefer short-lived execution using existing resources (e.g. GitHub Actions -> candidate-v4) and avoid new always-on Railway compute/DB/replicas unless explicitly approved.
- Cost reduction applied 2026-10-03: candidate-v3 is `SLEEPING` with its 5GB volume/data preserved; `production-pg-audit-readiness` and `snapshot-audit-readonly` have `sleepApplication=true`. Production candidate-v4 and active crons remain unchanged.
- One task at a time; keep output short.

## Cost investigation 2026-10-04
- candidate-v3 is confirmed `SLEEPING`; its last sleep transition stopped the container about 10 minutes after startup with no meaningful network activity. Keep its 5GB volume/data preserved unless separately approved for deletion.
- candidate-v4 was explicitly approved and redeployed once on 2026-10-04 to ensure `sleepApplication=true` applied to a fresh container. New deployment: `f7e44bc7-661b-47c6-97d8-4545f5fee343`; deployment reached SUCCESS and PostgreSQL became ready normally.
- After the redeploy, candidate-v4 had no application TCP/DNS traffic for >15 minutes; only two startup multicast ingress packets were observed. Despite this, the deployment remained Online/SUCCESS and no `Stopping Container` event occurred.
- v3/v4 live Railway config, source image, region/replica count, TCP proxy shape, volume size, tracing state, and variable-name set are effectively identical; tracing/auto-instrumentation are OFF for both.
- Read-only `pg_stat_activity` diagnostic after redeploy showed total=9, client_backends=1, active=1, idle=0; the single client backend is consistent with the diagnostic connection itself, so no persistent idle client connection was found.
- Conclusion: candidate-v4 Serverless non-sleep is not explained by an obvious app connection, tracing, variable-name/config difference, or visible network traffic. Treat it as a Railway/runtime behavior issue until a safer cause is identified. Do not repeatedly redeploy Production just to test sleep.
- Missing-data recent_form backfill itself is cheap: successful 14-day GitHub Actions run `37099767217` spent about 4m49s in the DB backfill step. Prefer this short-lived GitHub Actions -> candidate-v4 path; do not add a new always-on Railway runner.
- The temporary Railway recent-form runner approach via `test-beforeinfo-extra` failed with `python3: command not found`; do not rely on it as the normal cost path.
- Direct Railway billing month-to-date is not available through current non-Agent tools. Do not estimate invoice from stale Sleep-state RAM metrics alone.
- 2026-10-04 post-redeploy live cgroup read-only diagnostic: `memory.current=83,251,200 bytes (~0.083GB)`; `anon=9,699,328`, `file=67,502,080`, `shmem=42,029,056`, `kernel=5,914,624`. This strongly supports that prior 1-3GB memory growth was dominated by reclaimable file/page cache rather than PostgreSQL private/anon memory.
- The 08:00 JST `cron-learning-all` and `cron-final-check` executions completed normally after the redeploy; candidate-v4 remained around 0.08GB immediately afterward.
- Existing `railway-current-usage-readonly.yml` was tried without Railway Agent, but `railway usage` exited 1 under the current GitHub Railway token before JSON was produced; do not repeatedly retry unless token/billing scope is deliberately changed.
- Candidate-v4 currently has an 8GB memory limit. A lower per-replica memory cap (candidate: ~1GB) may bound page-cache-driven billing, but it is a Production resource-limit change and requires explicit approval plus post-change monitoring before use.

## Cost change 2026-10-04
- candidate-v4 RAM cap = 1GB. Verified live cgroup `memory.max=999997440` bytes.
- Post-change sample: `memory.current=653467648`, `anon=9334784`, `file=635535360`, `shmem=78368768` bytes.
- candidate-v4 remained Online/SUCCESS; no OOM/crash seen; recent `cron-learning-all` and `cron-final-check` completed normally.
- Keep the 1GB cap for now. Do not lower further without explicit approval and representative workload evidence.

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

`RECENT_FORM_14D_NEXT / HOBBY / PURCHASE_FALSE / TOKEN_COMPACT / COST_LE_20 / NO_RAILWAY_AGENT`
