# Bao-style architecture applicability for boat-ai-v2

## Scope

This note does **not** reproduce or infer proprietary formulas from 馬王/馬王Z. It maps publicly described ideas—database-driven analysis, indexes/scores, odds-aware value selection, simulation/backtest, and disciplined ticket selection—to the current boat-ai-v2 architecture.

## Publicly described ideas worth adapting

1. Large historical database as the foundation.
2. Multiple predictive indexes/scores rather than a single raw statistic.
3. Separation of prediction strength from betting value.
4. Use of actual odds when selecting tickets.
5. Simulation/backtest to discover robust purchase conditions.
6. Extensibility: new features can be added and evaluated without immediately changing production behavior.

## Boat-racing translation

### 1. Database layer
Use Railway PostgreSQL as the authoritative historical/live store. Favor high-quality official data and compact derived features. Do not duplicate large raw datasets unless reproducibility requires it.

### 2. Boat-performance index layer
Instead of a horse time index, construct boat-race-specific latent strength components, for example:
- racer baseline ability and lane ability;
- venue x lane structural baseline;
- opponent class/lane structure;
- motor maturity-adjusted motor strength;
- exhibition-time rank and exhibition ST;
- weather/wave/wind interaction;
- entry-course change and start behavior;
- condition-dependent racer effects only when OOS support exists.

These components should first remain separate so their OOS contribution can be measured. A composite score should only be built after calibration and stability tests.

### 3. Probability layer
Scores are not probabilities. The system should explicitly estimate/calibrate probabilities for relevant outcomes before comparing with odds. Candidate targets include:
- first-place probability for each boat;
- place/top-3 probability;
- trifecta combination probability or a coherent approximation derived from calibrated boat-level probabilities.

Calibration quality matters at least as much as ranking quality for value betting.

### 4. Value layer
For each available trifecta ticket, compare model probability with market odds. A generic value quantity is expected return = estimated hit probability x decimal payout odds. Apply safety margins for estimation error, market movement, and late odds changes.

### 5. Ticket-selection layer
Do not buy every positive estimated-value ticket. Require:
- minimum calibrated confidence;
- sufficient historical sample/support for contributing features;
- OOS/walk-forward stability;
- protection against correlated tickets and overconcentration;
- ticket-count/budget constraints;
- late-odds re-evaluation where practical.

### 6. Validation layer
Keep the current promotion path:
read-only audit -> multi-split OOS -> walk-forward -> Shadow -> live forward -> Production.

High backtest ROI alone is not sufficient. Require robustness across time periods, venues, odds bands, hit-rate bands, and payout concentration.

## Current conclusion

The overall Bao-style philosophy is highly compatible with boat-ai-v2, especially the separation of:

**data -> indexes/features -> calibrated probability -> odds/value -> ticket selection -> simulation/live validation**

The biggest gap to verify is not feature quantity; it is whether the current scores/decisions are calibrated enough to support explicit expected-value selection without overfitting.

## Next checks

1. Static readiness audit of current code for score/probability/odds/ROI/OOS components.
2. Identify the canonical location where a calibrated probability layer could be added without touching Production decisions.
3. Build a read-only probability-calibration audit on historical outcomes.
4. Only after calibration passes, test expected-value ticket selection in replay/Shadow.
