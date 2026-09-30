# boat-ai-v2 Current State

This file is intentionally short. **Live mutable state is not duplicated here.**

Current state pointer:
- `docs/HANDOFF_LATEST.md`
- read the compact live handoff linked there

Before work, always re-fetch:
- current `main`
- Issue #42 latest relevant evidence
- open Draft PR / exact-head CI
- active/queued GitHub Actions relevant to the task
- Railway Production status/fallback
- Production PostgreSQL evidence needed for the task

## Stable constraints

- GitHub `main` = code Source of Truth.
- Railway PostgreSQL Production = data Source of Truth.
- 2026-09-29 formal V4 is permanently UNAVAILABLE.
- V5 gate: V4 >=20 resolved FORMAL_AVAILABLE days; S03_M2 >=100 officially evaluated observations; evidence contract clean.
- Historical reconstruction never increments prospective gates.
- Do not tune selectors/thresholds to force notification count or monthly +50,000 JPY.
- `purchase_action=false`.
- Production-effect changes require explicit approval.
- Do not enumerate Railway plaintext variables.

## Handoff hygiene

Do not append historical snapshots or `LATEST OVERRIDE` blocks here. Replace current state only through the compact live handoff and update `HANDOFF_LATEST.md`.

For historical detail, use Git history or the dated deep-history documents.

`CURRENT_STATE_POINTER_ONLY / REFETCH_LIVE / PURCHASE_FALSE`
