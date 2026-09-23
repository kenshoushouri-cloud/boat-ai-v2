# V4 timing-safe profit gate — 2026-09-23

Status: `RESEARCH_ONLY / READ_ONLY_DB / PREDEADLINE_ODDS / FIXED_POLICY_GRID / NO_PRODUCTION_CHANGE`

## Objective

The current V4 research has narrowed the model question to a practical economics
question:

> Can the current two-point or shadow three-point ticket ranking become profitable
> if we **skip bets whose pre-deadline market odds do not justify the model
> probability**?

This study does not change the six-race selector, model coefficients or Production
ticket count.

## Strict train/test split

The position-conditional tail model is trained only on historical blocks ending
**2026-08-09**.

The profit test is **2026-08-25 through 2026-09-22**.

No test-period result updates the model.

Two probability sources are evaluated:

- `current`: current V4 distribution;
- `alpha025`: current V4 blended 25% with the position-conditional tail model
  frozen before the profit-test period.

## Timing-safe odds

Odds source: `v2_realtime_odds_snapshots`.

For each already-selected V4 race, use only the latest snapshot label satisfying:

- exactly 120 rows;
- exactly 120 valid distinct trifecta tickets;
- every odd > 1.0;
- label timestamp spread <= 60 seconds;
- final ticket timestamp <= race deadline minus **5 minutes**.

If no such snapshot exists, the race is not evaluated for the value policy. It is
never replaced with another race and final/result-time odds are never substituted.

## Fixed policy grid

No threshold is learned from the test outcomes.

For each probability source:

- point cap: 2 or 3 ranked tickets;
- raw EV gate: no gate, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25;
- raw EV = frozen model probability × observed timing-safe odds;
- flat stake 100 yen for each ticket that passes;
- if no ticket passes, skip the race.

This gives 28 fixed policies.

## Market-residual diagnostic

On the same timing-safe settled races, report exact-ticket:

- de-vigged inverse-odds market LogLoss and Brier;
- current V4 LogLoss/Brier;
- alpha0.25 LogLoss/Brier.

This determines whether model probability contains useful information relative to
the market before interpreting EV output.

## Historical profit-candidate gate

A fixed policy is tagged only as a **research Forward hypothesis** when all hold:

- at least 30 bets;
- overall realized ROI > 100%;
- both pre-fixed chronological halves have ROI > 100%;
- largest single hit contributes < 50% of total gross return;
- deterministic day-bootstrap P(ROI > 100%) >= 90%.

Passing this gate does **not** authorize Production. Multiple fixed policies are
tested, so any historical positive result still requires a separately
preregistered prospective Forward shadow.

## Safety

- all distributions, odds snapshots and policy ticket sets freeze before result read;
- DB transaction is READ ONLY;
- no Production write/persistence;
- no threshold/model/selector/ticket-count mutation;
- no LINE;
- no purchase;
- `purchase_action=false`.

`FIXED_2V3 / FIXED_EV_GRID / DEADLINE_MINUS_5M / RESULT_AFTER_FREEZE / NO_POST_HOC_THRESHOLD / FORWARD_HYPOTHESIS_ONLY`


## Cutoff correction before economic interpretation

The initial execution used a 15-minute cutoff and produced zero evaluable V4 races.
A separate result-free coverage ladder then showed, for the exact 174 selected V4
races in the test period:

- any realtime odds rows: 174 / 174;
- coherent complete 120-ticket label: 127 / 174;
- complete by deadline: 121 / 174;
- complete by deadline-5m: 71 / 174;
- complete by deadline-10m: 18 / 174;
- complete by deadline-15m: 0 / 174.

This does **not** justify choosing 5 minutes from profitability. No profitability
was observable in the 15-minute run.

The 5-minute cutoff is instead anchored to the pre-existing Production operating
contract documented on main before this research:

- `docs/DEVELOPMENT_STATUS.md`: FINAL market-late window = **0–7 minutes before deadline**;
- `docs/OPS_STATUS_2026-08-24.md`: market-late = **0–7 minutes**, including an
  exact-120 live capture at 5.46 minutes before deadline;
- current FINAL collector code accepts races inside its configured pre-deadline
  window and rejects only passed deadlines.

Five minutes is therefore a fixed, operationally feasible point inside the existing
late-market decision window while retaining a nonzero manual-action buffer. It is
not to be moved again in response to ROI.


## Coverage-only cutoff refinement — before ROI inspection

The first 15-minute run produced zero evaluable policies because the independent
no-result coverage ladder found:

- complete coherent 120-ticket labels by deadline-15m: 0 / 174 selected races;
- by deadline-10m: 18 / 174;
- by deadline-5m: 71 / 174;
- by deadline: 121 / 174.

No result, payout, ROI or profit value was used to choose the refinement.

The next fixed evaluation therefore uses:

- **5 minutes before deadline: primary timing-safe profit audit**;
- **10 minutes before deadline: conservative low-coverage diagnostic**.

The 0-minute cutoff is excluded from profit-candidate consideration because it
does not preserve enough operational action time. The 15-minute result remains
recorded as `NOT_EVALUABLE_ZERO_COVERAGE`.

The EV threshold grid, point counts, probability sources, training cutoff,
profit-test dates and research candidate gate are unchanged. No further cutoff
movement is allowed in response to the 5m/10m ROI results.


## Completed 5-minute result — 2026-09-23

The frozen deadline-5m audit completed successfully before the later transient
database-lock retry failures.

Immutable evidence:
- workflow run `35855288398`;
- 5m artifact ID `10747441900`;
- artifact ZIP SHA-256 `d9809649d7a25bedec46f5ca11fe394e939a5580a23e9f2c2ca5ad26b6a2bcbb`;
- timing-safe settled races: 71.

Probability quality on the exact same 71 races:
- de-vigged market LogLoss: 3.53741458;
- alpha0.25 LogLoss: 3.84490151;
- current V4 LogLoss: 3.88598104.

Flat ticket results:
- current 2pt: 142 bets, 10 hits, ROI 56.268%, profit -6,210 JPY;
- alpha0.25 2pt: 142 bets, 10 hits, ROI 51.056%, profit -6,950 JPY;
- current 3pt: 213 bets, 13 hits, ROI 50.892%, profit -10,460 JPY;
- alpha0.25 3pt: 213 bets, 13 hits, ROI 45.869%, profit -11,530 JPY.

Direct model-EV filtering did not rescue profitability:
- current 2pt EV>=1.00: 10 bets, ROI 85.0%, with the late fixed half at 0%;
- alpha0.25 2pt EV>=1.00: 14 bets, ROI 60.714%, late half 0%;
- alpha0.25 3pt EV>=1.00: 30 bets, ROI 28.333%, late half 0%;
- all stricter tested EV thresholds failed;
- no policy passed the preregistered research candidate gate.

Conclusion:
- do not loosen or retune the direct EV thresholds;
- current/alpha model probabilities are materially worse than the 5m market on this
  sample;
- the next research direction is market-first residual value: use the market as the
  baseline, choose model residual strength by predictive loss only, then test value
  tickets across the full 120-ticket market on held-out chronological blocks.
