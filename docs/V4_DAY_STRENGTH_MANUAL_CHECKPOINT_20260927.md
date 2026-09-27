# Manual V4 day-strength shadow checkpoint

Main-integration target for the frozen #411 future-only diagnostic.

Manual workflow:
`.github/workflows/research-v4-day-strength-shadow-manual.yml`

Properties:
- workflow_dispatch only;
- no schedule;
- target date >= 2026-09-28;
- provider inventory/arbitration occurs with DB/result/payout/odds reads = 0;
- only provider-selected FORMAL_AVAILABLE immutable artifacts are materialized;
- archive SHA256 values are verified;
- target artifact and immediately prior seven FORMAL_AVAILABLE artifacts are read locally;
- classification is KEEP_SHADOW / SKIP_SHADOW / NOT_READY;
- formal TOP6/TOP2 action is never changed.

Frozen rule:
`day_strength = mean(race_score of formal TOP6)`

Reference:
median of immediately prior seven FORMAL_AVAILABLE day strengths.

For the first target 2026-09-28, the preregistered input-only seed remains:
`reference_strength = 0.93817204`.

This workflow may run as soon as the immutable target formal artifact exists; it does not wait for or inspect race results.

No DB access, Railway access, odds, payout, LINE, BUY, persistence, selector change, or Production action.

`FUTURE_ONLY / RESULT_BLIND / PROVIDER_SELECTED_ARTIFACTS / SHADOW_ONLY / PURCHASE_FALSE`
