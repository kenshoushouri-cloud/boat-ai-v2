# S03_M2_POSITIVE_V1 × common Forward economics parity — 2026-09-27

Stacked on #415.

This audit re-runs the exact frozen S03_M2 rule for 2026-09-13..09-27 under strict stored `snapshot_at < deadline_at`, then passes only the frozen `score > 0` subset into the shared Forward economics evaluator.

Expected current #405 checkpoint:
- positive rows 62;
- officially evaluated 53;
- invalid_result 1;
- pending 8;
- hits 4;
- investment 5,300 JPY;
- return 10,120 JPY;
- profit +4,820 JPY;
- ROI 190.9434%;
- max DD 1,600 JPY;
- max losing streak 16;
- first-half ROI 319.6154%;
- second-half ROI 67.0370%;
- whole-day bootstrap P(ROI>100%) 86.13%.

Exact parity is required.

No retuning, historical reconstruction, DB write, Railway mutation, LINE, BUY, or Production change.

`FROZEN_S03_M2 / STRICT_PREDEADLINE / COMMON_ECONOMICS / EXACT_PARITY / NO_RETUNE`
