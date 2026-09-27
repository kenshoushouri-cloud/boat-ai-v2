# V4 day-strength seed for 2026-09-28

The first future-only shadow target is 2026-09-28.

Its reference must be computed **before 9/28 outcomes exist**, using only the seven immediately prior FORMAL_AVAILABLE immutable artifacts:
- 2026-09-21
- 2026-09-22
- 2026-09-23
- 2026-09-24
- 2026-09-25
- 2026-09-26
- 2026-09-27

CI downloads the exact already-known formal artifact IDs, verifies their archive SHA256 values, reads only the pre-result formal JSON, computes each formal TOP6 mean `race_score`, and freezes the median as the 9/28 reference.

No result/payout/odds/DB read is performed.

This seed does not classify any historical day and does not alter the formal V4 action.

`INPUT_ONLY_PRIOR7 / TARGET_20260928 / NO_RESULT_READ / NO_RETROSPECTIVE_GATE_TEST`
