# S03 M2 historical robustness — 2026-09-27

Purpose: evaluate the already-frozen `S03_M2_POSITIVE_V1` rule across **all available pre-freeze S03 PRE-shadow rows** without changing any rule parameter.

Frozen rule:
- source `S03`
- `motor_place2_rate` six-lane z-score
- ticket weights `1.0 / 0.6 / 0.3`
- beta `0.06`
- retain `score > 0`
- flat 100 JPY stake
- prospective freeze date 2026-09-13

Historical source boundary:
- use every available `S03` row with `race_date < 2026-09-13`;
- require stored PRE `snapshot_at < deadline_at`;
- do not choose a historical start date from ROI;
- no threshold / beta / weight / subgroup / date / venue / odds retuning.

Report:
- full coverage and timing rejects
- eligible fixed-rule ROI/profit/hit rate
- largest-hit share
- max drawdown and max losing streak
- calendar-month results
- four chronological blocks
- deterministic whole-day bootstrap
- nonpositive complement and all-S03 summaries for context only

This is robustness evidence, not a new optimizer. It does not authorize Production promotion.

Safety:
`READ_ONLY_DB / NO_VARIABLE_ENUMERATION / NO_DB_WRITE / NO_LINE / NO_BUY / NO_PRODUCTION_CHANGE / PROMOTION_FALSE`
