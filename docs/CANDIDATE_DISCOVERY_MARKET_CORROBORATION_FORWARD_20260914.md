# Candidate Discovery market corroboration — prospective freeze from 2026-09-14

Status: **research-only / promotion blocked / purchase_action=false**

This document freezes the next prospective market-corroboration hypothesis after the historical proxy work completed on 2026-09-13 JST. It does not change Production prediction, selection, LINE, persistence, stake, or purchase behavior.

## Why a prospective freeze is required

Historical fixed-grid work rejected ticket-type / point-count / A-B-C rearrangement as a profitability solution. A 30-day A+B trio TOP1 signal near ROI 102% fell to ROI 83.012% over the unchanged 2025-07-01..2026-09-12 long period.

Late Bao corroboration was too sparse for an economic conclusion: only 11 structural-TOP6 overlap races were available in its first proxy audit.

A broader timing-safe market proxy produced 109 structural-overlap races, but generic market agreement was not consistently beneficial. In particular, TOP1 agreement was not robust across bet types.

The only surviving descriptive signal is **market TOP2 support in the already-established Bao late market window (0-7 minutes before deadline)**. This window predates the ROI study and was not selected from outcomes.

Historical proxy, 2026-08-14..2026-09-12:

| Track | Evaluated | ROI | Profit | Note |
|---|---:|---:|---:|---|
| Trifecta late-window baseline | 56 | 104.107% | +230 JPY | proxy only |
| Trifecta late-window market TOP2 support | 34 | 107.941% | +270 JPY | too small |
| Trio late-window baseline | 56 | 100.179% | +10 JPY | proxy only |
| Trio late-window market TOP2 support | 47 | 109.149% | +430 JPY | too small |
| Exacta late-window market TOP2 support | 43 | 53.488% | -2,000 JPY | negative/control track |

The positive amounts are small and do not justify promotion. They only justify prospective observation.

## Frozen prospective hypothesis family

Name: `MKT_LATE07_TOP2_SUPPORT_V1`

Prospective start: **2026-09-14 JST**.

No race before 2026-09-14 may count as prospective evidence for this hypothesis.

The historical 2026-08-14..2026-09-12 sample remains development evidence only. The 2026-09-13 V4 pre-result freeze remains an independent immutable Forward artifact and must not be reclassified into this new hypothesis after results become available.

### Structural side

For historical proxy diagnostics the structural side is Candidate Discovery V2 `MOTOR2_FACTOR` TOP6/TOP1. This is explicitly **not equivalent to the V4 Production candidate feed**.

For future V4 Forward evidence, only a ticket that was already present in the immutable pre-result V4 artifact may be annotated. Market data must never create, replace, or delete a V4 Stage-1 candidate.

### Market side

A market observation is eligible only when all of the following are true before the race deadline:

- complete coherent 120-ticket trifecta snapshot;
- 120 distinct tickets;
- all odds positive and greater than 1.0;
- one snapshot label;
- within-label snapshot spread <= 60 seconds;
- market snapshot timestamp <= deadline;
- lead time is within the pre-existing Bao late window: **0.0 to 7.0 minutes before deadline**.

The market distribution is de-vigged from `1 / odds`. Exacta/trio probabilities, when reported, are aggregations of the same 120-ticket market distribution.

### Frozen support view

`market_top2_support = structural_top1 ticket is among market top 2 tickets for the same bet type`.

No TOP3/TOP4 expansion, odds-band filter, EV threshold, venue/race-number carveout, tier carveout, or lead-time sub-window may be added after 2026-09-13 outcomes to improve this version.

TOP1 agreement is retained only as a diagnostic negative/control view because historical proxy results were inconsistent and sometimes worse than baseline.

## Prospective reporting tracks

Keep all three bet types visible so the study cannot silently discard a negative track:

- trifecta — primary descriptive track;
- trio — primary descriptive track;
- exacta — negative/control track unless future evidence materially changes.

This does **not** authorize changing the V4 bet type. It is a research comparison only.

## Evidence milestones

Report at **30 / 50 / 100 evaluated market-TOP2-support cases**. Do not promote at a milestone merely because ROI is above 100%.

At each milestone report at minimum:

- evaluated cases and days;
- hits / hit rate;
- flat-100-JPY investment, return, profit, ROI;
- maximum losing-race streak;
- maximum drawdown;
- positive-day rate;
- maximum single-hit share of total returns;
- baseline late-window results over the same eligible race universe;
- whether evidence came from exact immutable V4 Forward artifacts or from the V2 proxy.

## Fail / hold rules

- If timing-safe late market is unavailable, record unavailable; do not substitute later/final odds.
- If the pre-result structural artifact is unavailable, do not reconstruct it after outcome.
- Do not retune the 0-7 minute window or TOP2 definition from observed results.
- A positive ROI with sparse hits or dominant single-hit share remains research-only.
- Historical proxy evidence cannot by itself authorize Production promotion.
- Production promotion requires a separate explicit decision and user approval.

## Negative control result

The pre-existing Bao early window (20-30 minutes before deadline) was tested as a timing control, but historical overlap was only **1 structural race on 1 day**. The resulting high single-race ROIs are non-informative and must not be used as evidence that early timing is better or worse than late timing.

## Provenance

Long fixed-grid validation:
- run `34742356084`
- artifact `10312598871`
- ZIP SHA-256 `3ac75d0c6f77c9e9a1acd7646a9e28cffc3fded5119450da4202c847e7c877bd`

Bao corroboration proxy:
- run `34743971344`
- artifact `10313388905`
- ZIP SHA-256 `2555ec3418296bebc6fe687decefa1274a1010847971e12f0f47d35a170b4156`

General timing-safe market proxy:
- run `34744177031`
- artifact `10312829753`
- ZIP SHA-256 `3f0d0020fe1deb27c36d463e4339879fc189eee62b593d5b4de5fecaf901fa51`

Pre-existing Bao late-window proxy:
- run `34744315812`
- artifact `10313557493`
- ZIP SHA-256 `0c22219e713b288d2c064c2dba693e1fc70ba2452b316ff9357569027117f7b2`

Pre-existing Bao early-window negative control:
- run `34744453973`
- artifact `10313294604`
- ZIP SHA-256 `532cc99bb2fb563479458f8192bece8486a960904e80ffd003a2f03ac0b962d3`

## Safety boundary

- DB write: 0
- schema change: 0
- LINE send: 0
- purchase action: false
- Railway Production config/Cron/service change: 0
- Production selector/model/threshold change: 0
- Production persistence change: 0
