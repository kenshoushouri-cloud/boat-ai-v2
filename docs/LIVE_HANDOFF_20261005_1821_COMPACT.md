# Compact Handoff — 2026-10-05 18:21 JST

## Fixed
- Production=V4. V5/V5.1=research-only.
- Formal backtest=2025-07-01 onward.
- Recent Form last5=rejected as model input; retain/collect.
- Railway pre-profit target <= USD20/month, ideally <=15. Agent/AI forbidden.
- One small task at a time. Do not change Production purchase/LINE/stake/plan/TOTO.
- Do not restart Production DB without explicit approval.

## DB/cost
- Production Postgres-EKp2: RAM limit 2.4GB, latest observed RAM ~1.62GB. Keep floor.
- candidate-v4: RAM limit 0.9GB, Serverless applied, latest RAM ~0.060GB. Retain.
- archive: Serverless applied, latest RAM ~0.065GB. Retain.
- candidate-v3: sleeping, RAM 0. Do not reuse/wipe without approval.
- Latest DB-only current-value estimate ~USD19.73/month. Stop aggressive reduction for now.

## Historical Exhibition Time
Use research/historical_beforeinfo_backfill_pg.py, mode exhibition-time-only.
Missing-fill only; historical parser v3; exact 6-lane gate; no result/odds/payout read.

Known:
- July terminal: official_partial 39 / official_absent 14.
- 8/2..8/5 target=0.
- 8/6 target=1; official_partial 5 lanes; DB write=0.
- 8/7..8/13 plan target=23.
- 8/7..8/13 actual: partial 11 / absent 12 / complete 0 / DB write 0.
These 23 should be terminal/unfillable and must not be re-HTTPed.

Efficiency:
- Use 7-day plan-only ranges, not day-by-day.
- Workflow: .github/workflows/historical-exhibition-time-plan-range.yml
- It is max 7 days, read-only, HTTP=0, DB write=0.
- Target-ID output was added in commit ddec16fa9970210d16c0c56f55b754d18a9b30a4.

## Current in-flight
Issue #42 comment id 5991646864 already posted:
/railway historical-exhibition-plan-range 2026-08-07 2026-08-13
Purpose: obtain HIST_BEFOREINFO_TARGET_IDS for the 23 terminal races.
Result not checked before chat ended.

## Next ONE task
1. Check Issue #42 comments after id 5991646864 only.
2. Extract HIST_BEFOREINFO_TARGET_IDS.
3. Add exactly those 23 IDs to research/historical_exhibition_terminal_unfillable.json with a neutral terminal reason if per-ID partial/absent classification is unavailable.
4. Do not re-HTTP those 23.
5. Then next range is 2026-08-14..08-20 plan-only.

## Capacity rules
Read only HANDOFF_LATEST -> current compact -> NEXT_CHAT_START_HERE.
Do not reread old handoffs/PROJECT_HISTORY/long workflows.
Live values only when needed. One task per turn, 1-3 tool calls, no repeated polling.
