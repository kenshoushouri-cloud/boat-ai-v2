# Value Candidate Shadow Acceptance Criteria

Date: 2026-09-12 JST

The alternative method exists to solve a business problem: too few useful Boat candidates. It is not successful merely because it finds more bets.

## Minimum evidence to call the method promising

All of the following should be reviewed together:

1. **Frequency uplift** — materially more candidate races than the current Production control.
2. **Out-of-sample profitability** — ROI above 100% after realistic stake/payout accounting.
3. **Small-stake viability** — useful monthly profit must not require large per-race stakes.
4. **Stability** — performance should not depend on one venue, one month, or a few large payouts.
5. **Timing integrity** — only information available before the decision deadline may be used.
6. **Calibration** — low-odds tickets must have sufficiently accurate probability estimates; apparent value from overconfident probabilities is not accepted.
7. **Capacity safety** — no meaningful Production DB growth for the research path.
8. **Market-residual gate** — before treating `prob * odds` as a value signal, the probability variant must show fixed out-of-sample predictive information beyond the de-vigged market baseline. If a train-only residual blend selects market-only (`alpha=0`) or the variant fails to improve future market LogLoss/Brier, its `prob * odds` output stays diagnostic only and cannot be promoted as a value rule.

## Existing evidence that constrains this research

The market-residual gate is not theoretical. Existing merged read-only audits already showed that the older/current-base v24 probability should not be used as a presumed value engine:

- PR #104 historical full-market audit (2026-01-01..2026-08-22): naive `p_model * odds` thresholds were unprofitable overall. ROI was about 53.7% at `>=1.00`, 53.5% at `>=1.10`, 53.1% at `>=1.25`, and 52.4% at `>=1.50`.
- PR #106 train-only market-residual OOS: all four expanding future splits selected `alpha=0.00` (market-only). Combined future market LogLoss was 3.698498 versus 4.340241 for model-only.

Therefore this PR must not interpret a high `prob * odds` number from that base model as evidence of true edge.

There is, however, newer timing-clean feature evidence worth testing against the market:

- fixed Racer Course coefficient 0.50 + Opponent Pressure coefficient 1.0, evaluated on 1,144 common timing-clean Forward races, improved COURSE with COMBINED deltas of LogLoss -0.02814106, Brier -0.00082388, and rank -0.4685; paired-bootstrap 95% intervals excluded zero for all three metrics.

That evidence is predictive-relative-to-model, not yet proof of market value. The next value gate is therefore: test the fixed newer variants against a timing-safe market baseline, then evaluate realized ROI using odds that were actually available before the decision deadline. No coefficient search or post-hoc venue/date filtering is allowed.

## Practical target bands to report

Do not hard-code these as Production thresholds. They are reporting targets for business feasibility.

- 10+ candidate races/month: still low frequency; likely insufficient alone
- 20-40 candidate races/month: potentially useful if ROI and drawdown are strong
- 40-80 candidate races/month: suitable range for small-stake portfolio evaluation
- 80+ candidate races/month: attractive frequency, but over-selection/edge dilution must be checked carefully

For each range report the observed stake required to reach 10,000 / 20,000 / 30,000 yen monthly profit under the actual measured ROI. Do not assume target profit in advance.

## No forced frequency

If no odds/value segment can deliver both frequency and positive out-of-sample ROI, do not weaken gates to manufacture candidates. In that case the evidence supports keeping Boat as a low-frequency strategy and reconsidering a second domain.
