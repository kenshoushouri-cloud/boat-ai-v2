# Manual S03_M2 Forward checkpoint

This workflow is manual only and keeps the frozen `S03_M2_POSITIVE_V1` rule unchanged.

Trigger:
- `workflow_dispatch`
- optional `end_date=YYYY-MM-DD`
- blank end date resolves to current JST date

Frozen:
- start date 2026-09-13
- exact Motor2 score definition and `score > 0`
- stored `snapshot_at < deadline_at`
- common Forward economic semantics
- invalid_result = void / zero investment

Outputs:
- source/positive/evaluated/invalid/pending counts
- ROI/profit/hit rate
- largest-hit share
- max DD / max losing streak
- chronological halves
- whole-day bootstrap
- remaining evaluated observations to the 100-observation review

The 2026-09-27 baseline remains exact-parity checked. Later dates are read-only checkpoints, not retunes.

No schedule, DB write, Railway config mutation, LINE, BUY, model/threshold change, or promotion action.

`MANUAL_ONLY / FROZEN_S03_M2 / STRICT_PREDEADLINE / COMMON_ECONOMICS / REVIEW_TARGET_100 / NO_RETUNE`
