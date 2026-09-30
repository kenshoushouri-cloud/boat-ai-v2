# boat-ai-v2 Project Handoff

This file is intentionally compact. It is a **stable orientation pointer**, not a cumulative event log.

## Read first

1. `docs/HANDOFF_LATEST.md`
2. the compact live handoff linked there
3. `docs/NEXT_CHAT_START_HERE.md`

Only when deep history is required:
- `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
- dated `LIVE_HANDOFF_*.md` files
- Git history

## Stable project contract

Goal: build a reproducible positive-expectation boat-race system using only information that was available before each race deadline, without result leakage, hindsight reconstruction, or outcome-guided tuning.

Source of Truth:
- GitHub `main` = code
- Railway PostgreSQL Production = data

Permanent boundaries:
- 2026-09-29 formal V4 is permanently UNAVAILABLE.
- V5 core gate is V4 >=20 resolved FORMAL_AVAILABLE days + S03_M2 >=100 officially evaluated observations + clean evidence contract.
- Historical reconstruction never receives prospective gate credit.
- Monthly net-profit +50,000 JPY is a later scaling objective; it must not drive selector/threshold relaxation.
- `purchase_action=false`.
- Production model/selector/stake/LINE/purchase and Railway Production changes require explicit approval.
- Read-only audits, research/backtests, safe evidence, Draft PRs, CI and docs may continue without approval.
- Never enumerate Railway plaintext variable values.

## Maintenance rule

Do **not** add another `LATEST OVERRIDE` block here.

Current mutable state belongs in exactly one compact live handoff referenced by `docs/HANDOFF_LATEST.md`. Historical snapshots remain available through Git history and dated historical documents.

`STABLE_ORIENTATION_ONLY / CURRENT_STATE_IN_HANDOFF_LATEST / PURCHASE_FALSE`
