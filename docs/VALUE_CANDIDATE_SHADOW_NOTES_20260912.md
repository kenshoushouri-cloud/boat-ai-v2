# Initial Notes

- Existing Production method remains unchanged and is the control.
- The research objective is stable small-stake profitability, not merely more candidates.
- The older/current-base v24 `prob * odds` signal is now a diagnostic baseline only: PR #104 showed poor historical realized ROI across value thresholds, and PR #106 selected market-only (`alpha=0.00`) in every train-only future split.
- Do not lower Production gates or reinterpret a high base-model `prob * odds` value as proof of edge.
- The new research path should first test newer fixed timing-clean variants for residual information beyond the market. Priority evidence includes Racer Course 0.50 + Opponent Pressure 1.0, which already improved the model-side Forward metrics on a common timing-clean sample but has not yet proven market-relative profitability.
- Low odds such as 2.0x remain eligible only when a calibrated, timing-safe probability variant passes the market-residual gate and realized forward value evidence.
- High odds remain eligible under the same standard; odds range alone is not a value signal.
- First profitability evaluation should use fixed 100 yen ticket stakes and race caps before any dynamic sizing.
- Use odds that were actually observable before the decision deadline for formal forward profitability. Historical/final odds may be used only as clearly labeled diagnostics.
- No Production storage expansion is permitted for this research path.
- No Production model, coefficient, BUY/WATCH/SKIP threshold, LINE behavior, or purchase action changes are authorized by this Draft PR.
