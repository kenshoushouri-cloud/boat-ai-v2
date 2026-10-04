# Handoff Latest

**Current compact handoff:** `docs/LIVE_HANDOFF_20261002_RECENT_FORM_14D.md`

Read only:
1. this pointer
2. the current compact handoff above, in full
3. `docs/NEXT_CHAT_START_HERE.md`

Do not load old handoffs by default. Re-fetch only live state needed for the next single task.

Current:
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`
- Railway plan = Hobby
- Historical Recent Form completed through 2026-05-27
- next fixed target = 2026-05-28..2026-06-10 (14 days)
- next = user posts `/railway historical-recent-form-next` to Issue #42, then verify only latest run
- never bulk-fetch Issue #42 comments
- protect candidate-v4 / history archive / escrow / active writers / TOTO
- **operating-cost hard target = <= USD 20/month even after missing-data/backfill work resumes; lower is better.** Do not cut required Production/backtest/live-test/system-building data or services.
- default cost policy = **no recurring Railway cost increase**; sleep/retire unused compute before adding resources; any expected cost increase requires explicit cost check + user approval
- **never use Railway Agent / Railway AI** for this project; Agent token usage can affect the invoice. Use direct read-only Railway status/metrics/logs/docs instead.
- candidate-v3 is sleeping with volume/data preserved; candidate-v4 RAM cap = 1GB and a representative 14-day backfill passed with OOM=0; audit HTTP services `production-pg-audit-readiness` and `snapshot-audit-readonly` are sleep-enabled
- V5 = research-only; Production remains V4; core gate = V4 >=20 resolved formal days + S03_M2 >=100 official observations + clean evidence contract
- never call `list_variables`; no purchase/plan/volume changes
- one task at a time / short output

`READ_CURRENT_COMPACT / RECENT_FORM_14D_NEXT / TOKEN_COMPACT / PURCHASE_FALSE / COST_LE_20 / NO_RAILWAY_AGENT`
