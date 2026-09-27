# V4 formal immutable-artifact settlement — 2026-09-27

Purpose: measure realized performance using only exact prospective artifacts that were frozen before results.

Evidence set:
- 2026-09-21: run 35549611949 / artifact 10617384166
- 2026-09-22: run 35667553345 / artifact 10670080150
- 2026-09-23: run 35797576979 / artifact 10724298102
- 2026-09-24: run 35933702258 / artifact 10782581362
- 2026-09-25: run 36072738431 / artifact 10838744179
- 2026-09-26: run 36201131582 / artifact 10891628808
- 2026-09-27: run 36279479671 / artifact 10918742073

For each ZIP, the GitHub artifact SHA-256 and the embedded canonical formal-core SHA-256 are pinned. The evaluator validates all five artifacts and freezes the exact 42 races / 84 formal tickets **before** opening a read-only result query.

Settlement reports:
- predicted-head accuracy;
- 1-point ROI/profit;
- formal 2-point ROI/profit;
- per-day results and profitable-day count;
- incomplete/invalid races separately.

No historical candidate regeneration is permitted. No odds are read. No result/payout data influences candidate selection because selection comes only from the exact immutable artifacts.

Safety:
`ARTIFACT_FIRST / EXACT_6R_12T / RESULT_AFTER_FREEZE / ODDS_READ_0 / DB_WRITE_0 / LINE_0 / BUY_0 / PROD_CHANGE_0 / PROMOTION_FALSE`
