# Current formal V4 × F-count companion compatibility proof — 2026-09-27

Status: `STACKED ON #400 / SYNTHETIC F-COUNT ONLY / NO LIVE CAPTURE`

## Purpose

Prove that the already-frozen #398/#400 companion contract can consume the **actual current 2026-09-27 formal V4 artifact** without modifying the formal core.

Formal source:
- workflow_dispatch run: `36279479671`
- artifact: `10918742073`
- archive SHA256: `d251c0d918964e3dc8c467b8f43038cae0571892a2b0539ad8ccf27a39d98da0`
- canonical formal-core SHA256: `8907e2443a172d7938395145824497479f3f3bf23d3170943973545adc47f8d3`
- generated: 2026-09-27 08:29:31 JST
- earliest formal feed deadline: 08:32 JST
- outcome/payout read: false
- purchase_action: false

## Compatibility method

CI:
1. downloads the exact immutable formal artifact by GitHub artifact ID;
2. verifies the archive SHA256;
3. extracts the formal JSON;
4. verifies the canonical core SHA256;
5. creates exactly 36 **synthetic sentinel** `race_id/lane/f_count` rows;
6. uses capture timestamp 08:29:45 JST, after formal freeze and before all six deadlines;
7. passes those synthetic rows through the exact #400 adapter and #398 companion contract;
8. verifies formal core SHA before == after and companion hash binding.

Synthetic F counts are not observations and must never be used as research evidence.

## Boundary

This proof performs:
- no Boat DB read;
- no real F-count read;
- no result/payout/odds read;
- no companion upload or persistence;
- no scheduled capture;
- no Railway change;
- no Production behavior change;
- no LINE/purchase.

A successful compatibility proof only reduces activation risk. Actual prospective F-count read/capture/persistence remains a separate explicit approval gate.

`CURRENT_FORMAL_ARTIFACT_COMPAT / SYNTHETIC_FCOUNT_ONLY / NO_CAPTURE / NO_PERSISTENCE / EXPLICIT_APPROVAL_STILL_REQUIRED`
