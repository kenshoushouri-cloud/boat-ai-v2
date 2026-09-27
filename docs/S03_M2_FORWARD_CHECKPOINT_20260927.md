# S03 M2 Forward checkpoint — 2026-09-27

This Draft is a read-only checkpoint refresh for the already frozen `S03_M2_POSITIVE_V1` rule.

Frozen rule remains unchanged from the 2026-09-12 preregistration:
- source rule: `S03`
- feature: lane `motor_place2_rate`
- six-lane within-race z-score
- ticket weights: `1.0 / 0.6 / 0.3`
- beta: `0.06`
- retain only `score > 0.0`
- flat stake: 100 JPY
- prospective start: 2026-09-13 JST
- checkpoints: 30 / 50 / 100 evaluated observations

This refresh fixes the evaluation end date at **2026-09-27**. It does not change the rule, threshold, beta, weights, source population, stake, or start date.

Review outputs:
- eligible / evaluated / pending
- hits / hit rate
- investment / return / profit / ROI
- largest-hit share
- month breakdown
- 30 / 50 / 100 checkpoint status

Safety:
- PostgreSQL transaction is READ ONLY
- no DB write
- no Railway variable enumeration
- no Railway configuration change
- no LINE send
- no BUY
- no Production selector/model/threshold/candidate/stake change
- `promotion_allowed=false`
- `purchase_action=false`

Interpretation remains prospective research only. A checkpoint result does not authorize Production promotion.
