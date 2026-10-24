# Initial Notes

- Existing Production method remains unchanged and is the control.
- The research objective is stable small-stake profitability, not merely more candidates.
- The older/current-base v24 `prob * odds` signal is a diagnostic baseline only: PR #104 showed poor historical realized ROI across value thresholds, and PR #106 selected market-only (`alpha=0.00`) in every train-only future split.
- Do not lower Production gates or reinterpret a high base-model `prob * odds` value as proof of edge.
- A timing-safe odds preflight on 2026-08-25..2026-09-12 found 1,264 of 1,503 Racer Course Forward races (84.10%) with a coherent complete 120-ticket realtime-odds label fully captured before deadline. This is sufficient for read-only market-relative research, not evidence of profitability by itself.
- Fixed Racer Course 0.50 + Opponent Pressure 1.0 was then tested against the de-vigged timing-safe market with expanding-train, non-overlapping future folds. Across 807 future-test races, the train-selected blend had LogLoss 3.94494084 and Brier 0.96601641 versus market-only 3.94466044 and 0.96591867. Overall status: `MARKET_RESIDUAL_NOT_ESTABLISHED`.
- The pure Course+Opponent model was materially worse than market-only on the same future tests (LogLoss 4.21015782, Brier 0.97849500, mean rank 24.1722 versus market 3.94466044, 0.96591867, 21.1252). This does not invalidate its model-relative improvement; it means it is not currently a validated probability source for a Value strategy.
- Do not tune Course/Opponent coefficients, alpha, date windows, venues, or other subgroups post hoc to force market-residual support. Production coefficients remain fixed and unchanged.
- Low odds such as 2.0x remain eligible only when a calibrated, timing-safe probability variant independently passes the market-residual gate and realized forward value evidence.
- High odds remain eligible under the same standard; odds range alone is not a value signal.
- First profitability evaluation for any future variant that passes the residual gate should use fixed 100 yen ticket stakes and race caps before any dynamic sizing.
- Use odds that were actually observable before the decision deadline for formal forward profitability. Historical/final odds may be used only as clearly labeled diagnostics.
- Motor2 currently has too little fixed-candidate evidence to substitute for this failed gate; continue collecting timing-clean Forward evidence rather than inferring edge from the current tiny sample.
- No Production storage expansion is permitted for this research path.
- No Production model, coefficient, BUY/WATCH/SKIP threshold, LINE behavior, or purchase action changes are authorized by this Draft PR.
