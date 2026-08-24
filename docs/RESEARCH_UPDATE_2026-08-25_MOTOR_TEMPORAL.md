# Research Update: Motor temporal stability

Date: 2026-08-25 JST

This note records the confirmed read-only finding from PR #214 for future handoff/history consolidation.

## Scope

Five venues with previously verified official current-generation motor start dates only: 03, 05, 12, 14, 23. Same v24 formula/coefficient set; baseline uses fixed motor2=33.0 and comparison uses race-card `motor_place2_rate`. No Production, LINE, Railway settings, N02, Bao, or PR #169 changes.

Fixed calendar blocks:
- 2026-05-11..2026-06-15
- 2026-06-16..2026-07-15
- 2026-07-16..2026-08-15

## Confirmed result

Evaluated 2,963 races. Actual motor rates improved both trifecta LogLoss and Brier in all 3 calendar blocks:
- B1: LogLoss delta -0.00358280, Brier delta -0.00007081
- B2: LogLoss delta -0.00219660, Brier delta -0.00004499
- B3: LogLoss delta -0.00170027, Brier delta -0.00005714

The effect is therefore not explained by one isolated time period.

## Maturity boundary

Using the fixed race-level minimum prior motor appearances among the six motors:
- P21+ (mature): LogLoss and Brier improved 3/3 blocks.
- P06-20: improved 2/3 blocks, with no B3 sample.
- P00-05 (young): improved only 1/3 blocks; later block samples were very small.

This changes the interpretation of PR #213: do not infer that very young motors are reliably safe merely because the aggregate early-observation bucket was positive. The stable evidence is strongest once motors have substantial observed history.

## Venue heterogeneity

Venue 23 improved both metrics 3/3. Other verified venues were mostly 2/3, with small period-specific reversals. A blanket all-venue Production substitution is therefore still premature.

## Decision

- Keep Production v24 unchanged.
- Treat actual motor2 as a strong normal-prediction candidate.
- Prefer maturity-aware / venue-aware validation rather than a universal substitution.
- Require independent Forward validation before Production use.
- DB first-seen remains forbidden as a proxy for official motor generation start.
