# boat-ai-v2 Current State

## LATEST OVERRIDE — 2026-09-23 13:28 JST

Freshly reverified state:

- main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production: `stagedChanges=null`; visible pending patch has `changes=[]`
- `postgres-recovery` 7d disk current 4.654747 GB / avg 4.548166 / min 4.425625 / max 4.657086
- #374 `05c2cdea...`: Draft / mergeable / 7/7 green; 9/24 real-fixture gate unchanged
- #375 `248f634b...`: Draft / mergeable / 5/5 green
- #376 `6123a882...`: Draft / mergeable / 5/5 green
- #377 `4c7be65f...`: Draft / mergeable / 5/5 green
- #378 `991fac34...`: Draft / mergeable / 7/7 exact-head workflows green

Research update:
- long history 2025-07-01..2026-09-22: 432 evaluable days / 2,592 races; 2pt ROI 75.069%, 3pt ROI 75.554%.
- selector challenger past-only test: 15.600% Top2 vs control 16.489%; selector replacement not supported.
- control error split: among head-correct Top2 misses, 62.225% fail at second-prefix and 37.775% at third completion.
- static tail place2 challenger past-only test: 16.280% Top2 vs control 16.624%; static place2 amplification not supported.
- tail challengers improve probability log loss but do not improve discrete Top2 ranking.
- next research target: position-conditional second/third model with strict past-only walk-forward.
- formal policy remains six races / two points; 3pt shadow only; no score gate / candidate-count change / retune; `purchase_action=false`.

Evidence:
- long history run `35815470386`, artifact `10731821585`, ZIP `7d0db4de...160728`
- selector run `35816984747`, artifact `10731444815`, ZIP `175cf329...8e5642`
- tail run `35817852992`, artifact `10732018221`, ZIP `756a89a2...b69964`

## LATEST OVERRIDE — 2026-09-23 12:02 JST

Freshly reverified state:

- main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none; pending work: none
- `postgres-recovery` 7d disk: current 4.652175 GB / avg 4.545401 / min 4.420073 / max 4.657086
- PostgreSQL volume config: 20,000 MB
- PR #374: `05c2cdea22c96fdcaaa45e565ff06450cc33fad5`, Draft / mergeable / 7/7 SUCCESS, real fixture gate still required
- PR #375: `248f634b587eae4c419a9194c5ae2e8c989c8fa1`, Draft / mergeable / 5/5 SUCCESS
- PR #376: `6123a8820f840081b7067f4015ea9f94257334f0`, Draft / mergeable / 5/5 SUCCESS
- new PR #377: `4c7be65f4c5cc8e813a6de031ed73f6d17b28abc`, Draft / mergeable / 5/5 SUCCESS, pure selector-rank Forward diagnostic only

Selector-rank research:
- immutable #376 artifact ZIP SHA-256 reverified: `426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`
- OOS ranks 1-3 vs 4-6 formal-2pt ROI: 79.203% vs 65.797%, +13.406 pp; bootstrap 95% CI crosses zero
- recent ranks 1-3 vs 4-6: 54.333% vs 36.333%, +18.000 pp; bootstrap 95% CI crosses zero
- race-score quartile ROI is non-monotonic; no absolute score gate supported
- no candidate-count reduction, threshold change, rerank, point-count change, or Production selector change authorized
- formal 2 points remains control; 3 points remains shadow/Forward comparison only

Before 2026-09-24 real fixture:
- keep main fixed for #374
- #375/#376/#377 stay Draft
- safe research/docs/read-only only
- `purchase_action=false`

Safety:
`MAIN_FIXED_FOR_REAL_FIXTURE_GATE / PURCHASE_FALSE / FORMAL_2_POINTS_UNCHANGED / SELECTOR_RANK_DIAGNOSTIC_ONLY / NO_SCORE_GATE / NO_RESULT_AFTER_RECONSTRUCTION / NO_PRODUCTION_MUTATION`


## LATEST OVERRIDE — 2026-09-23 11:42 JST

This section supersedes the 11:38 JST override below where they differ.

### Final handoff checkpoint

The current chat has reached its token/capacity limit. Continue in a new chat using the paste-ready handoff prompt provided to the user.

Freshly re-verified before handoff:
- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- Railway PostgreSQL `postgres-recovery` 7d disk:
  - current `4.6521271532307695 GB`
  - average `4.545399481671327 GB`
  - min `4.419897273379311 GB`
  - max `4.657085660862745 GB`
  - 169 samples
- no capacity-driven deletion authorized

Active key Drafts:
- PR #374 availability activation
  - head `05c2cdea22c96fdcaaa45e565ff06450cc33fad5`
  - Draft / mergeable
  - **7/7 exact-head CI SUCCESS**
- PR #375 formal Top5 replay
  - head `248f634b587eae4c419a9194c5ae2e8c989c8fa1`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**
- PR #376 historical 1–5 point walk-forward
  - head `6123a8820f840081b7067f4015ea9f94257334f0`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**
- PR #363 storage ownership migration
  - head `4cccdc5b41241f6ffa139be629172cf5a03d7500`
  - Draft / mergeable
  - all listed exact-head CI SUCCESS
- PR #366 post-result evaluator
  - head `20c835c5dabd847c96180acad6a3daf5ffd8fdf7`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**
- PR #368 Forward economics gate
  - head `2e47342912e545f8341e8678c10e940e94bcd2f3`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**

### Point-count conclusion at handoff

Historical backtest narrows the practical question to **2 vs 3 points**.

PR #376 immutable dual-window evidence:
- workflow run `35806246724`
- artifact ID `10727519397`
- ZIP SHA-256 `426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`

OOS 2026-07-01..2026-08-15, 276 races:
- cumulative ROI: 1pt 71.848%, 2pt 72.500%, 3pt 77.826%, 4pt 78.288%, 5pt 69.217%
- marginal ROI: rank1 71.848%, rank2 73.152%, rank3 **88.478%**, rank4 79.674%, rank5 **32.935%**

Recent timing-safe 2026-09-11..2026-09-22, 60 evaluated races:
- cumulative ROI: 1pt 27.667%, 2pt 45.333%, 3pt 60.056%, 4pt 88.250%, 5pt 76.433%
- marginal ROI: rank1 27.667%, rank2 63.000%, rank3 **89.500%**, rank4 172.833%, rank5 **29.167%**

Robustness:
- rank3 is stable across windows but remains below break-even;
- recent rank4 is not robust: only 2 hits, one 9,560 JPY payout = 92.189% of rank4 gross, remove it => 13.500% marginal ROI, and recent full-feature subset rank4 = 0 hits;
- rank5 is consistently weak.

Current research policy:
- formal **2 points remains control**
- **3 points only shadow/Forward comparison**
- rank4 diagnostic only
- rank5 deprioritized
- do not change Production point count from historical backtest alone
- Forward 30/50/100-case evidence remains the confirmation path

### Secret/safety correction on PR #376

The first immutable report run used an older Railway CLI variable-list pattern. Current PR #376 removes that pattern.

Current boundary:
- no `railway variable list`
- no `RAILWAY_TOKEN`
- no temporary variable-list JSON
- optional future live replay only through dedicated `V4_BACKTEST_DATABASE_URL` GitHub secret
- if absent, CI skips live DB replay and validates frozen evidence/contracts only
- never call Railway plaintext variable-list APIs/tools

### Next critical event

PR #374 must stay unmerged until the **2026-09-24 real timing-clean official availability fixture** is validated.

One active exact automation:
- `V4 Real Fixture Gate 9/24`
- 2026-09-24 08:45 JST

Gate requirements:
- re-fetch main / #374 exact head+CI / Railway
- inspect scheduled primary and any fallback
- choose earliest valid same-date capture via preregistered arbiter
- require matching raw availability + formal freeze from the same run
- verify raw SHA and raw-observed/capture-complete timestamps precede freeze
- replay exact raw bytes through #374 binder/parser/guard with no hand edits
- supported `PASS_ACTIVE_CORE` or correctly parsed supported `BLOCK_PRE_FREEZE_UNAVAILABLE_CORE` validates real HTML
- parser ambiguity/mismatch/SHA/timing/unsupported status blocks merge
- if gate passes and exact-head CI is green, the user has already explicitly approved #374 Production-effect merge

After safe #374 merge:
- re-fetch main
- rebase/recheck #375/#376 before any merge
- #375 is pure/offline research and may proceed if still clean
- #376 remains research evidence; do not use it alone to change Production point count

### Handoff schedule / hard boundaries

Recurring handoff automation:
- 09:00 JST
- 15:00 JST
- 21:00 JST
- **no 03:00 JST run**

May continue without confirmation:
- read-only audits
- research / historical backtest / Forward evaluation
- Draft PR creation/update
- CI
- docs/handoff updates
- safe evidence collection

Explicit approval required:
- Production-effect PR merge unless already explicitly approved
- Railway Production Variables/Cron/service/volume/migration changes
- Production DB INSERT/UPDATE/DELETE/schema/VACUUM
- Production model/coefficient/threshold/candidate/stake changes
- new LINE actual-send behavior changes
- Forward persistence
- automatic purchase
- paid data / external inquiry

Hard safety:
- fail closed
- `purchase_action=false`
- no result-after Forward/candidate reconstruction
- no evidence mixing
- never loosen thresholds for volume/profit/cost
- no capacity-driven deletion
- never expose secret values
- do not touch TOTO staged patch

### Immediate new-chat start sequence

1. Read this latest override in `docs/PROJECT_HANDOFF.md`.
2. Read `docs/CURRENT_STATE.md`.
3. Read Draft PR #374, #375, #376.
4. Re-fetch current main / open PRs / exact-head CI / Railway Production.
5. Do not assume any SHA/state above is still current.
6. If before 2026-09-24 08:45 JST, keep main fixed under #374 validation and do safe research/docs only.
7. At/after the real fixture, execute the #374 gate exactly as above.

### Safety

`PURCHASE_FALSE / MAIN_FIXED_FOR_REAL_FIXTURE_GATE / FORMAL_2_POINTS_UNCHANGED / RANK3_SHADOW_ONLY / NO_SECRET_ENUMERATION / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_CAPACITY_DRIVEN_DELETE`

## LATEST OVERRIDE — 2026-09-23 11:38 JST

This section supersedes the 11:24 JST override below where they differ.

### Conversation handoff status

The current chat reached its token/capacity limit. Continue in a new chat.

At the start of the new chat, read in this order:
1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. Draft PR #374
4. Draft PR #375
5. Draft PR #376

Then re-fetch current GitHub main / open PRs / exact-head CI / Railway Production before acting. Do not assume the SHA/PR/CI/Railway values below are still current.

### Current Source of Truth at handoff

- repository: `kenshoushouri-cloud/boat-ai-v2`
- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway PostgreSQL Production is Production-data Source of Truth
- Railway Production staged changes: none
- `purchase_action=false`
- no Production DB/model/coefficient/threshold/stake/candidate-count mutation in this chat segment

Active Drafts:
- PR #374 `Production: enforce V4 pre-freeze availability guard (rebased)`
  - head `05c2cdea22c96fdcaaa45e565ff06450cc33fad5`
  - Draft / mergeable
  - **7/7 exact-head CI SUCCESS**
- PR #375 `Research: replay formal V4 top-five point-count economics`
  - head `248f634b587eae4c419a9194c5ae2e8c989c8fa1`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**
- PR #376 `Research: backtest V4 1-5 point historical walk-forward`
  - head `6123a8820f840081b7067f4015ea9f94257334f0`
  - Draft / mergeable
  - **5/5 exact-head CI SUCCESS**

### PR #376 — historical point-count result

Immutable original dual-window evidence:
- workflow run `35806246724`
- artifact ID `10727519397`
- ZIP SHA-256 `426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`

Fixed OOS window: 2026-07-01..2026-08-15
- 46/46 days
- 276 exact selected races
- no 5R shrink
- cumulative ROI:
  - 1 point 71.848%
  - 2 points 72.500%
  - 3 points 77.826%
  - 4 points 78.288%
  - 5 points 69.217%
- Nth-point marginal ROI:
  - rank1 71.848%
  - rank2 73.152%
  - rank3 **88.478%**
  - rank4 79.674%
  - rank5 **32.935%**

Recent timing-safe window: 2026-09-11..2026-09-22
- 10/12 days evaluable
- 60 exact selected races
- 2 whole days unevaluable due missing official selected result
- no 5R shrink
- cumulative ROI:
  - 1 point 27.667%
  - 2 points 45.333%
  - 3 points 60.056%
  - 4 points 88.250%
  - 5 points 76.433%
- Nth-point marginal ROI:
  - rank1 27.667%
  - rank2 63.000%
  - rank3 **89.500%**
  - rank4 172.833%
  - rank5 **29.167%**

Sensitivity result:
- rank3 is notably stable across windows but remains below break-even:
  - 88.478% OOS
  - 89.500% recent
- recent rank4 is not robust:
  - only 2 hits
  - one 9,560 JPY payout supplies 92.189% of rank4 gross
  - removing that hit => 13.500% marginal ROI
  - recent full-feature subset (Course full6 + Opponent + Motor, 40 races) => rank4 0 hits / 0%
- rank5 is consistently weak
- deterministic 20,000-resample day-cluster bootstrap exists as uncertainty diagnostic
- simple monotone tier-point policies also failed to become profitable in fixed OOS

Current point-count shortlist:
- keep formal **2 points** as control
- compare **3 points** in shadow/Forward
- rank4 diagnostic only until replicated
- rank5 deprioritized

Do not change Production point count from this backtest alone. Forward 30/50/100-case evidence remains the confirmation path.

### PR #376 secret boundary

The first immutable report run used the repository's older Railway CLI variable-list pattern.

That pattern was removed from current PR #376:
- no `railway variable list`
- no `RAILWAY_TOKEN`
- no temporary variable-list JSON
- future optional live DB replay only via dedicated GitHub secret `V4_BACKTEST_DATABASE_URL`
- if that dedicated secret is absent, CI validates frozen evidence/contracts and skips live DB replay

Exact-head CI enforces this boundary.

### PR #375 — formal Top5 replay

PR #375 is pure/offline research.

It:
- requires explicit immutable artifact SHA
- requires exact six formal races
- requires five pre-result `research_ranked_tickets`
- requires research ranks 1–2 == formal core_order 1/2
- requires predeadline freeze
- requires exact-six final outcomes
- can adapt frozen PR #366 `candidate_discovery_v4_post_result_eval_v1` evidence into the replay without manual result re-entry
- does not reconstruct historical rank3–5 after results
- has no DB/network/LINE/purchase surface

Keep it Draft until #374's Production availability validation is resolved, unless current state after re-fetch clearly justifies otherwise.

### PR #374 — next Production gate

PR #374 remains intentionally unmerged.

Reason:
- 2026-09-23 natural availability shadow failed because repo root was missing from PYTHONPATH
- PR #373 fixed that import-path issue in main
- next clean natural real fixture is expected on 2026-09-24

One active exact automation remains:
- title `V4 Real Fixture Gate 9/24`
- 2026-09-24 08:45 JST
- inspect scheduled primary and any Railway fallback
- select earliest timing-clean capture with preregistered arbiter
- require matching raw + formal artifacts from same run
- verify raw SHA/timestamps and raw-before-freeze ordering
- replay exact raw through #374 binder/parser/guard without hand edits
- supported `PASS_ACTIVE_CORE` or supported `BLOCK_PRE_FREEZE_UNAVAILABLE_CORE` counts as real-HTML contract validation
- parser/ambiguity/SHA/timing/unsupported-status failure blocks merge
- if validation succeeds and exact-head CI is green, user has already explicitly approved #374 Production-effect merge

A duplicate older 08:45 gate automation was disabled during this handoff to prevent double execution.

### Already merged / Production-visible relevant changes

- PR #371 LINE notification display is merged:
  - existing BUY rows only
  - max 2 distinct tickets/race
  - first = `本線`
  - second = `押さえ`
  - no synthetic second point and no threshold relaxation
  - this realtime LINE path is **not yet proven identical** to V4 formal core_order 1/2
- PR #372 Top5 pre-result research observation is merged:
  - formal core remains 2 tickets
  - `research_ranked_tickets` records Top5 for future economics
- PR #373 PYTHONPATH repair is merged

### Handoff automation schedule

Per user request:
- no 03:00 JST handoff update
- recurring handoff updates only at 09:00 / 15:00 / 21:00 JST

### Approval / safety boundaries

May continue without confirmation:
- read-only audits
- research / historical backtest / Forward evaluation
- Draft PR creation/update
- CI
- docs/handoff updates
- safe evidence collection

Explicit approval required:
- Production-effect PR merge unless already explicitly approved
- Railway Production Variables/Cron/service/volume/migration changes
- Production DB INSERT/UPDATE/DELETE/schema/VACUUM
- Production model/coefficient/threshold/candidate/stake changes
- new LINE actual-send behavior changes
- Forward persistence
- automatic purchase
- paid data / external inquiry

Existing explicit approval:
- PR #374 availability guard Production merge is approved **only after** the real timing-clean fixture gate passes.

Hard safety:
- fail closed
- `purchase_action=false`
- never loosen thresholds for volume/profit/cost
- no result-after Forward/candidate reconstruction
- no evidence mixing
- no secret values
- no capacity-driven deletion
- never call Railway plaintext variable-list APIs/tools; config variable names only
- do not change point count from #376 backtest alone

### Best next action in new chat

1. Re-fetch current main/open PR/CI/Railway.
2. If before 2026-09-24 08:45 JST:
   - keep main fixed under #374 validation
   - do not merge #375/#376 merely to reduce Draft count
   - safe research/docs only.
3. At/after the natural 2026-09-24 fixture:
   - execute/inspect the #374 real-fixture gate
   - merge #374 only if exact real raw validates and exact-head CI is green
   - re-fetch main after merge
   - then rebase/recheck #375/#376 as needed.
4. Continue 2-vs-3 point Forward economics:
   - formal 2 points remains control
   - rank3 is shadow/diagnostic comparison only
   - do not activate 3 points based on historical backtest alone.
5. Keep Sep21/Sep22 cancellation-affected formal artifacts out of settled economics unless exact six same-date final outcomes exist.

### Safety

`PURCHASE_FALSE / MAIN_FIXED_FOR_REAL_FIXTURE_GATE / FORMAL_2_POINTS_UNCHANGED / RANK3_SHADOW_ONLY / NO_SECRET_ENUMERATION / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 11:24 JST

This section supersedes the 10:30 JST override below where they differ.

### Current Source of Truth

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- PR #374 availability activation: Draft / mergeable / **7/7 exact-head CI SUCCESS**
- PR #375 top-five formal replay bridge: Draft / mergeable / **5/5 exact-head CI SUCCESS**
- PR #376 historical 1–5 point walk-forward: Draft / mergeable / **5/5 exact-head CI SUCCESS**
- PR #376 current head: `6123a8820f840081b7067f4015ea9f94257334f0`
- no Production DB/model/coefficient/threshold/stake/candidate-count mutation
- `purchase_action=false`

### PR #376 — point-count shortlist hardened

Original immutable dual-window evidence remains:
- workflow run `35806246724`
- artifact ID `10727519397`
- ZIP SHA-256 `426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`

New frozen sensitivity evidence:
`research/evidence/v4_point_count_historical_sensitivity_20260923.json`

#### Marginal rank robustness

Fixed OOS 2026-07-01..2026-08-15, 276 races:
- rank1 marginal ROI 71.848%
- rank2 73.152%
- rank3 **88.478%**, -11.522 JPY/race
- rank4 79.674%
- rank5 **32.935%**

Recent timing-safe 2026-09-11..2026-09-22, 60 evaluated races:
- rank1 marginal ROI 27.667%
- rank2 63.000%
- rank3 **89.500%**, -10.500 JPY/race
- rank4 172.833%
- rank5 **29.167%**

Rank3 is notably stable but still sub-break-even across both windows.

Recent rank4 is not robust:
- only 2 hits;
- one 9,560 JPY payout contributes **92.189%** of rank4 gross;
- removing that single hit reduces rank4 marginal ROI to **13.500%**;
- recent full-feature subset (Course full6 + Opponent + Motor, 40 races) has rank4 **0 hits / 0%**.

Rank5 is consistently weak in both windows.

A deterministic 20,000-resample day-cluster bootstrap is included only as an uncertainty diagnostic; payout tails make the intervals wide.

#### Current research shortlist

Do not increase Production ticket count from this backtest alone.

Keep:
- formal **2 points**
- shadow/Forward comparison **3 points**

Deprioritize:
- rank5

Keep diagnostic only:
- rank4 until its high-payout effect replicates

Historical evidence therefore narrows the practical point-count question to **2 vs 3**, while Forward 30/50/100-case evidence remains the final confirmation path.

### PR #376 CI secret boundary corrected

The first immutable report run inherited a Railway CLI variable-list pattern.

That pattern is no longer present in PR #376:
- no `railway variable list`;
- no `RAILWAY_TOKEN`;
- no temporary variable-list JSON;
- future live replay can use only dedicated GitHub secret `V4_BACKTEST_DATABASE_URL`;
- if that dedicated secret is absent, CI skips live DB replay and validates frozen evidence/contracts only.

Exact-head safety test enforces this boundary.

### Other active gates

PR #374 remains intentionally unmerged until the 2026-09-24 real timing-clean availability fixture is replayed through the exact binder/parser/guard chain.

PR #375 remains Draft until #374 is resolved so main stays fixed underneath the Production availability validation.

### Handoff schedule

03:00 JST update remains disabled.

Recurring handoff updates:
- 09:00 JST
- 15:00 JST
- 21:00 JST

### Safety

`PURCHASE_FALSE / FORMAL_2_POINTS_UNCHANGED / RANK3_SHADOW_ONLY / NO_SECRET_ENUMERATION / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 10:30 JST

This section supersedes the 10:09 JST override below where they differ.

### Current Source of Truth

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- PR #374 availability activation: Draft / mergeable / **7/7 exact-head CI SUCCESS**
- PR #375 top-five formal replay bridge: Draft / mergeable / **5/5 exact-head CI SUCCESS**
- PR #376 historical 1–5 point walk-forward: Draft / mergeable / **5/5 exact-head workflows SUCCESS**
- no Production DB/model/coefficient/threshold/stake/candidate-count mutation
- `purchase_action=false`

### PR #376 — V4 1–5 point historical walk-forward result

Exact head:
`13dfd99f602dd32c26c33451064270bf5ae9ae9e`

Evidence:
- workflow run `35806246724`
- artifact ID `10727519397`
- artifact digest `sha256:426822606000248437d7d7daa8a625937e7e34d4526cd37c500032d0b10e6771`
- read-only Production PostgreSQL
- result/payout queried only after daily six-race + Top5 ranking freeze
- no odds/EV selection
- no 5R shrink / replacement / retune

#### Fixed OOS: 2026-07-01..2026-08-15

Coverage:
- 46/46 days
- 276 selected races
- Course any 66.304%
- Course full6 28.623%
- Opponent timing-safe 0%
- Motor 99.275%

Cumulative fixed-point ROI / profit:
- 1 point: 71.848% / -7,770 JPY
- 2 points: 72.500% / -15,180 JPY
- 3 points: 77.826% / -18,360 JPY
- 4 points: 78.288% / -23,970 JPY
- 5 points: 69.217% / -42,480 JPY

Nth-point marginal ROI:
- rank1 71.848%
- rank2 73.152%
- rank3 **88.478%**
- rank4 79.674%
- rank5 **32.935%**

#### Recent timing-safe window: 2026-09-11..2026-09-22

Coverage:
- 10/12 days evaluable
- 60 selected races
- 2 whole days unevaluable due missing official selected result
- Course any 100%
- Course full6 78.333%
- Opponent timing-safe 90%
- Motor 98.333%

Cumulative fixed-point ROI / profit:
- 1 point: 27.667% / -4,340 JPY
- 2 points: 45.333% / -6,560 JPY
- 3 points: 60.056% / -7,190 JPY
- 4 points: 88.250% / -2,820 JPY
- 5 points: 76.433% / -7,070 JPY

Nth-point marginal ROI:
- rank1 27.667%
- rank2 63.000%
- rank3 **89.500%**
- rank4 172.833% / +4,370 JPY / only 2 hits
- rank5 **29.167%**

Robustness:
- recent rank4 profit disappears on the full-feature subset (Course full6 + Opponent + Motor): rank4 had 0 hits there;
- rank4 profit came from feature-incomplete races and is high-payout / small-hit dependent;
- rank3 marginal ROI is much more stable across windows: 88.478% vs 89.500%;
- rank5 is consistently weak;
- simple monotone tier policies A<=B<=C also failed to reach profitability in fixed OOS; best OOS ROI was about 82.45%.

### Point-count research conclusion

Do **not** change Production ticket count from this backtest.

Research shortlist:
- keep current formal **2 points** as control;
- compare **3 points** in shadow/Forward because rank3 is the most stable additional-ticket signal;
- keep rank4 diagnostic only until its high-payout effect replicates;
- deprioritize rank5.

The backtest indicates that fixed ticket count alone is not the main profitability bottleneck. Race selection / probability ranking quality is the more important research target.

The existing Forward 30/50/100-case milestones still govern any Production point-count decision.

### Other active gates

- PR #374 remains waiting for 2026-09-24 real timing-clean availability fixture validation.
- PR #375 remains pure/offline Draft until #374 is resolved so main stays fixed underneath the Production gate.
- recurring handoff updates remain 09:00 / 15:00 / 21:00 JST only; no 03:00 JST update.

### Safety

`PURCHASE_FALSE / FORMAL_2_POINTS_UNCHANGED / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_5R_SHRINK / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 10:09 JST

This section supersedes the 10:05 JST override below where they differ.

### Current Source of Truth

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- PR #374 availability activation: Draft / mergeable / **7/7 exact-head CI SUCCESS**
- PR #375 top-five formal replay bridge: Draft / mergeable / **5/5 exact-head CI SUCCESS**
- main intentionally unchanged while waiting for the 2026-09-24 real availability fixture gate
- no Production DB/model/coefficient/threshold/stake/candidate-count mutation
- `purchase_action=false`

### PR #375 — post-result evidence adapter added

Current head:
`248f634b587eae4c419a9194c5ae2e8c989c8fa1`

PR #375 remains pure/offline research and Draft.

It now accepts existing frozen post-result evidence from PR #366 instead of requiring outcomes to be manually re-entered.

Adapter checks before conversion:
- contract must be `candidate_discovery_v4_post_result_eval_v1`;
- `formal_core_only=true`;
- legacy excluded from formal metrics;
- fixed stake 100 JPY/ticket;
- exactly six race rows;
- stored formal top-two tickets are valid and distinct;
- each stored `exact_hit` must agree with predicted top two + actual trifecta;
- summary core-races/core-tickets/exact-hits/investment/gross/profit must recompute exactly.

Only then is the evidence converted to the exact-six final-outcome contract consumed by the top-five replay bridge.

This removes duplicate manual outcome entry and reduces evidence-mixing risk.

The replay still requires:
- explicit formal artifact SHA-256;
- exact six formal core races;
- five pre-result `research_ranked_tickets`;
- research ranks 1–2 identical to formal core_order 1/2;
- predeadline freeze;
- exact-six final outcomes.

No historical 3–5 rank reconstruction is permitted.

### PR #374 / next natural gate

No change to the Production gate:
- PR #374 remains Draft, mergeable, 7/7 green;
- 2026-09-23 natural availability shadow failed only because the workflow import path lacked repo-root `PYTHONPATH`;
- #373 fixed that issue in main;
- next timing-clean natural fixture is 2026-09-24;
- a one-time 08:45 JST validation is scheduled to inspect scheduled primary/fallback, verify real raw timing/SHA, replay exact bytes through #374, and merge #374 only if the real-HTML contract passes.

PR #375 is intentionally not merged before that gate so main remains fixed underneath #374 validation.

### Handoff schedule

Per user request, there is no 03:00 JST handoff update.

Recurring handoff updates remain only:
- 09:00 JST
- 15:00 JST
- 21:00 JST

### Safety

`PURCHASE_FALSE / NO_03_JST_HANDOFF / TOP5_PRE_RESULT_ONLY / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_RETUNE / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 10:05 JST

This section supersedes the 09:58 JST override below where they differ.

### Current Source of Truth

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- PR #372 Top5 pre-result observation: merged
- PR #373 availability shadow `PYTHONPATH: .` repair: merged
- PR #374 availability activation: Draft / mergeable / 7/7 exact-head CI SUCCESS
- PR #375 top-five formal replay bridge: Draft / mergeable / 5/5 exact-head CI SUCCESS
- no Production DB/model/coefficient/threshold/stake/candidate-count mutation
- `purchase_action=false`

### PR #375 — future 1–5 point economics replay prepared

PR #375:
`Research: replay formal V4 top-five point-count economics`

Current head:
`6a5d23d58207c01e0ab7267b6e97bfa71355700f`

State:
- Draft / mergeable
- **5/5 exact-head CI SUCCESS**
- pure/offline research only
- intentionally not merged before PR #374 real-fixture validation so main stays fixed

The replay bridge accepts only immutable evidence:
- explicit formal artifact SHA-256;
- prospective-evidence-eligible artifact;
- no result/payout reads in freeze provenance;
- `generated_at_jst == completed_at_jst`;
- exact six formal core races / ranks 1..6;
- exactly five preserved pre-result `research_ranked_tickets` per core race;
- research ranks 1–2 exactly equal formal `core_order 1/2`;
- every frozen ranking precedes its race deadline;
- exact same six finalized outcome rows, with no missing/extra/non-final race.

Only after those checks does it call the frozen 1..5 point marginal-revenue evaluator.

This means future formal artifacts created after #372 can be scored for 1/2/3/4/5-point economics without manual ticket copying or result-after rank reconstruction.

Sep18/Sep19 remain 1–2 only because their immutable artifacts never preserved ranks 3–5.

### PR #374 — next real availability fixture gate

PR #374 remains the current Production activation Draft:
- head `05c2cdea22c96fdcaaa45e565ff06450cc33fad5`
- Draft / mergeable
- **7/7 exact-head CI SUCCESS**

The 2026-09-23 natural shadow capture exposed only:
`ModuleNotFoundError: No module named 'research'`

That workflow import-path issue was fixed and merged in #373. It did not change eligibility.

The next timing-clean real raw validation is scheduled for **2026-09-24 08:45 JST**.

Gate:
- inspect scheduled primary and any 08:25 fallback;
- choose earliest valid capture via the preregistered arbiter;
- require raw availability evidence and formal freeze from the same run;
- verify raw SHA and raw-observed/capture-complete timestamps precede freeze;
- replay exact real bytes through #374 binder/parser/guard with no hand-edited status/scope;
- PASS_ACTIVE_CORE or a correctly parsed supported cancellation BLOCK proves real-HTML contract compatibility;
- parser ambiguity/mismatch/timing/SHA failure blocks merge.

The user has explicitly approved the Production-effect #374 merge once this real-fixture gate passes.

After a safe #374 merge, PR #375 may be rechecked against the new main and merged as pure research if still clean.

### Handoff update schedule

Per user request, the **03:00 JST handoff update has been removed**.

The recurring `AI引き継ぎ日次更新` now runs only at:
- 09:00 JST
- 15:00 JST
- 21:00 JST

Its prompt was also simplified to require fresh current-main/open-PR/CI/Railway retrieval instead of carrying stale fixed SHAs and old blockers.

Do not recreate or enable a 03:00 JST handoff update unless the user explicitly requests it again.

### Safety

`PURCHASE_FALSE / NO_03_JST_HANDOFF / TOP5_PRE_RESULT_ONLY / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_CAPACITY_DRIVEN_DELETE / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 09:58 JST

This section supersedes the 09:54 JST override below where they differ.

### Current main / approved merges

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- PR #372 Top5 pre-result observation: merged
- PR #373 availability shadow import-path repair: merged
- Railway Production staged changes: none
- fallback service auto-deployment after #373: SUCCESS
- no Production DB mutation
- no model/coefficient/threshold/stake/candidate-count change
- `purchase_action=false`

### Availability activation PR replaced cleanly

Old PR #370 has been closed as superseded.

Current activation Draft is PR #374:
`Production: enforce V4 pre-freeze availability guard (rebased)`

- base: current main after #371/#372/#373
- head: `05c2cdea22c96fdcaaa45e565ff06450cc33fad5`
- Draft / mergeable
- **7/7 exact-head CI SUCCESS**

PR #374 preserves:
- merged LINE main/cover display
- merged Top5 pre-result observation
- merged shadow-capture `PYTHONPATH: .` repair

The activation design is unchanged:
- official raw capture before freeze
- exact raw/request/manifest SHA + timing checks
- bind exact frozen six core races to official evidence
- formal prospective artifact is published only on `PASS_ACTIVE_CORE`
- supported pre-freeze cancellation or any ambiguity/failure blocks the normal formal artifact
- blocked run remains diagnostic only
- no replacement / rerank / result read / payout read / DB write / LINE / purchase path

### Remaining merge gate

Do **not** merge PR #374 on synthetic CI alone.

Next natural gate:
- **2026-09-24 08:45 JST**

Requirements:
1. same-run real availability raw + formal prospective artifact
2. exact raw/request/manifest hashes and timestamps
3. all raw source observations completed before formal freeze
4. replay exact preserved bytes through #374 binder/parser/guard with no hand-edited status/scope
5. `PASS_ACTIVE_CORE` or correctly parsed supported `BLOCK_PRE_FREEZE_UNAVAILABLE_CORE`
6. exact-head CI still green

If those pass, the user has already explicitly approved Production-effect activation and #374 may be readied/merged with exact validated head SHA.

If real HTML exposes ambiguity or unsupported shape, remain fail closed and update the Draft instead of weakening the guard.

### Point-count economics

Top5 observation is now active in future pre-result artifacts while formal tickets remain two.

Current historical exact result remains:
- 1 point/race: profit **-10 JPY**, ROI **99.167%**
- 2 points/race: profit **+920 JPY**, ROI **138.333%**
- point-2 marginal profit **+930 JPY**, marginal ROI **177.5%**
- historical points 3–5 remain not evaluable because their ranks were not preserved pre-result

Future settled formal days can now evaluate 1/2/3/4/5 without result-after reconstruction.

### Handoff automation

The user requested no 03:00 JST handoff update.

Current daily handoff cadence:
`09:00 / 15:00 / 21:00 JST`

### Safety

`PURCHASE_FALSE / FORMAL_CORE_TICKETS_2_UNCHANGED / TOP5_OBSERVATION_ONLY / PRE_FREEZE_RAW_REQUIRED / NO_RESULT_AFTER_RECONSTRUCTION / NO_THRESHOLD_RELAXATION / NO_DB_MUTATION / NO_RAILWAY_CONFIG_CHANGE`

## LATEST OVERRIDE — 2026-09-23 09:54 JST

This section supersedes the 01:10 JST override below where they differ.

### Fresh Source of Truth

- current main: `c93422b53c8dc384e87b7d99d444c5902c48253f`
- Railway Production staged changes: none
- no Production DB mutation
- no model/coefficient/threshold/stake/candidate-count change
- `purchase_action=false`

### PR #372 — Top5 pre-result observation approved and merged

The user explicitly approved continuing the V4 point-count marginal-revenue work.

PR #372 `Research: compare V4 1-5 point marginal revenue`:
- validated head: `81adec1d80d9f1d5c2772af33d70a1e02f745229`
- exact-head CI before merge: **7/7 SUCCESS**
- merge/main SHA: `49e09146551c52fc49c2b4e0939b22772435740d`

Production artifact effect now on main:
- formal `CORE_TICKETS=2` remains unchanged
- formal `tickets` remains exactly two
- each future pre-result V4 artifact additionally stores observation-only `research_ranked_tickets` top five from the same frozen V4 probability distribution
- `research_ranked_tickets[:2]` must remain the formal top two
- ranks 3–5 have no candidate eligibility, LINE, threshold, stake, model or purchase effect

Historical exact evidence remains:
- 1 point/race: invest 1,200 / gross 1,190 / profit **-10 JPY** / ROI **99.167%**
- 2 points/race: invest 2,400 / gross 3,320 / profit **+920 JPY** / ROI **138.333%**
- point-2 marginal contribution: **+930 JPY**, marginal ROI **177.5%**
- Sep18/Sep19 ranks 3–5 remain `NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS`; no result-after reconstruction was performed

Future settled formal days can now compare cumulative and marginal economics for 1/2/3/4/5 points using preserved pre-result ranks.

### 2026-09-23 real availability fixture attempt — blocked before raw HTML

Natural fallback run:
- GitHub run `35797576979` (`workflow_dispatch`)
- availability artifact ID `10724442796`
- prospective freeze artifact ID `10724298102`
- freeze JSON SHA-256 `238691641fe8deee44da93cc50baadb92c066d8b893c67e3f8d66818da56a942`
- canonical core SHA-256 `8a50f645239778a3adae8fb24f8c5df18b6c25d698a1136f00006482c8075639`
- freeze completed `2026-09-23T08:28:46.600474+09:00`
- earliest core deadline `08:58 JST`

The availability capture step failed before any official HTML/raw/request manifest was written:

`ModuleNotFoundError: No module named 'research'`

Therefore Sep23 does **not** provide a valid real availability fixture and PR #370 must not be merged from this evidence.

### PR #373 — shadow availability import-path repair merged

To avoid repeating the same failure on the next natural run, the user-approved minimal Production workflow repair was separated from guard activation.

PR #373 `Production: fix V4 availability shadow import path`:
- one workflow file / two-line functional delta
- adds workflow-level `PYTHONPATH: .`
- asserts the invariant in safety CI
- exact-head CI: **5/5 SUCCESS**
- validated head: `aebf4b0720798d28852dc9c7326caa137f1b2ed1`
- merge/main SHA: `c93422b53c8dc384e87b7d99d444c5902c48253f`

Important:
- this repairs already-merged shadow raw capture only
- shadow capture remains `continue-on-error`
- shadow capture still has `eligibility_effect=0`
- it does not enable availability guard enforcement
- no Railway Variables/Cron/service/volume change was made

### PR #370 — availability guard activation remains real-fixture gated

Current PR #370 head:
`a5c13f4e93ee09641e3a4552faeb7e881570d652`

State:
- Draft
- exact-head **7/7 CI SUCCESS**
- currently behind/diverged from newer main after #371/#372/#373
- do not merge stale branch as-is
- if the next real fixture validates, rebase/recreate the equivalent activation changes cleanly on current main while preserving newer LINE and Top5 changes

Next real-fixture gate:
- **2026-09-24 08:45 JST**
- inspect the natural scheduled primary and/or Railway fallback
- require matching real pre-freeze raw + formal artifact from the same timing-clean run
- verify exact raw/request/manifest hashes and timestamps
- replay exact bytes through binder/parser/guard without hand-editing status/scope
- `PASS_ACTIVE_CORE` or a correctly parsed supported pre-freeze BLOCK is acceptable real-HTML validation
- parser ambiguity, missing raw, timing violation, unsupported status or identity mismatch remains a blocker
- user has already explicitly approved Production-effect activation if the real-fixture gate passes and exact-head CI is green

### LINE notification state

The merged LINE main/cover display remains active from main:
- existing BUY decisions only
- maximum two distinct tickets per race
- first = `本線`
- second = `押さえ`
- no synthetic cover / no threshold relaxation

This realtime LINE path is still separate from exact V4 formal `core_order 1/2` identity.

### Handoff automation cadence

The user requested no overnight 03:00 handoff update.

`AI引き継ぎ日次更新` is now scheduled only at:
- 09:00 JST
- 15:00 JST
- 21:00 JST

No 03:00 JST run.

### Safety

`PURCHASE_FALSE / FORMAL_CORE_TICKETS_2_UNCHANGED / TOP5_OBSERVATION_ONLY / PRE_FREEZE_RAW_REQUIRED / NO_RESULT_AFTER_RECONSTRUCTION / NO_THRESHOLD_RELAXATION / NO_DB_MUTATION / NO_RAILWAY_CONFIG_CHANGE`

## LATEST OVERRIDE — 2026-09-23 01:10 JST

This section supersedes the 00:58 JST override below where they differ.

### V4 1–5 point marginal revenue comparison

Draft PR #372:
- title: `Research: compare V4 1-5 point marginal revenue`
- head: `81adec1d80d9f1d5c2772af33d70a1e02f745229`
- Draft / mergeable
- **7/7 exact-head CI SUCCESS**
- research-only; no Production merge performed

Immutable current formal corpus:
- Sep18 artifact ID `10527500527`, JSON SHA `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
- Sep19 artifact ID `10574052434`, JSON SHA `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`
- 2 days / 12 formal races / 100 JPY per ticket

Exact evaluated strategies:
- 1 point/race:
  - investment 1,200 JPY
  - gross return 1,190 JPY
  - profit **-10 JPY**
  - ROI **99.167%**
  - exact hits 2/12 = 16.667%
  - chronological max drawdown 500 JPY
- 2 points/race:
  - investment 2,400 JPY
  - gross return 3,320 JPY
  - profit **+920 JPY**
  - ROI **138.333%**
  - exact hits 4/12 = 33.333%
  - chronological max drawdown 600 JPY

Exact point-2 marginal contribution:
- incremental investment 1,200 JPY
- incremental gross return 2,130 JPY
- incremental profit **+930 JPY**
- marginal ROI **177.500%**
- incremental exact hits 2/12

Current immutable artifacts preserved only ticket ranks 1 and 2.

Therefore:
- 3 points: `NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS`
- 4 points: `NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS`
- 5 points: `NOT_EVALUABLE_MISSING_PRE_RESULT_RANKS`

No result-after regeneration/reconstruction of ranks 3–5 was performed.

PR #372 preregisters an observation-only `research_ranked_tickets` top-five field from the same pre-result V4 distribution so future settled formal days can compare 1/2/3/4/5 points fairly.

Important invariants:
- formal `CORE_TICKETS=2` remains unchanged;
- formal `tickets` remains exactly two;
- `research_ranked_tickets[:2]` must equal the formal top two;
- no race selection/rerank/model/coefficient/threshold/stake/purchase change;
- rank 3–5 observation has no eligibility or LINE effect.

Merge boundary:
the evaluator/evidence is research-only, but merging the prospective top-five observation would change Production artifact schema. **Do not merge PR #372 without explicit user approval.**

Current evidence suggests the second point is economically valuable in the tiny 12-race corpus, but this is not enough to declare two points permanently optimal. Continue review at the existing prospective 30/50/100-case milestones.

### Other current state

Unless superseded above, the 00:58 JST override remains current:
- main `56cb4165c261c26d5fff460f3c0c1fed33983694`
- LINE main/cover display merged and Railway auto-deploy SUCCESS
- PR #370 availability activation remains gated on real timing-clean raw fixture
- Railway Production staged changes none
- no Production DB/model/threshold/stake/purchase mutation

### Safety

`PURCHASE_FALSE / FORMAL_CORE_TICKETS_2_UNCHANGED / NO_RESULT_AFTER_RECONSTRUCTION / NO_SYNTHETIC_RANKS / NO_PRODUCTION_MUTATION`

## LATEST OVERRIDE — 2026-09-23 00:58 JST

This section supersedes the 00:39 JST override below where they differ.

### Production LINE main/cover display — user approved and merged

The user explicitly approved changing actual LINE notification behavior.

Fresh Source of Truth:
- current main: `56cb4165c261c26d5fff460f3c0c1fed33983694`
- PR #371 `Production: show main and cover points in LINE`: merged
- validated PR head: `7b6b87839c134fe9ac647f81b74d068d50270b23`
- merge/main SHA: `56cb4165c261c26d5fff460f3c0c1fed33983694`
- exact-head CI: **5/5 SUCCESS**
- Railway Production staged changes: none
- no manual Railway redeploy/config change
- `cron-final-check` automatic deployment `abff25d7-10cb-47ad-b810-dfea285e42c7`: **SUCCESS**

Production LINE path:
`cron-final-check -> run_final_pg.py -> v25_final_realtime_pipeline_pg.py -> v23_line_notifier_batch_pg.py`

New notification behavior:
- considers only existing `recommendation='buy'` decisions;
- maximum two distinct notified BUY tickets per race;
- first eligible distinct ticket in existing final-score order = `本線`;
- second distinct existing BUY = `押さえ`;
- if there is only one BUY decision, message says `押さえ: BUY条件該当なし`;
- identical tickets from different modes do not consume the second slot;
- an already-notified main counts toward the two-point cap; a later newly eligible second BUY is labeled `押さえ`;
- third and later BUY tickets are not notified;
- only race groups actually visible in the LINE body are marked notified; hidden/deferred groups are not silently marked sent.

Important scope boundary:
- this is a display/notification policy over the existing realtime BUY decision rows;
- no BUY/odds/probability threshold was relaxed;
- no second ticket is synthesized when it does not already satisfy BUY;
- no model/coefficient/stake/candidate-generation change;
- no automatic purchase change;
- this does **not** claim that realtime LINE `本線/押さえ` are identical to V4 formal `core_order 1/2`.
- exact V4-to-LINE binding remains a separate future integration.

Evidence:
- `line_buy_notification_layout.py`
- `tests/test_line_buy_notification_layout.py`
- `docs/LINE_TWO_POINT_NOTIFICATION_20260923.md`
- `.github/workflows/line-two-point-notification.yml`

### PR #370 availability activation remains pending real fixture

PR #370:
- head `2a6f6f819023562b9d94f2fa273ffbee0b27d181`
- Draft / mergeable
- **7/7 exact-head CI SUCCESS**
- merge is still gated on the first real timing-clean pre-freeze official raw fixture from current main shadow capture.

Natural validation remains scheduled for 2026-09-23 08:45 JST:
- re-fetch current main / Railway / PR #370;
- select earliest timing-clean valid V4 capture using the preregistered arbiter;
- replay exact real raw bytes through #370 binder/parser/guard without hand-editing;
- if real fixture validates and exact-head CI is still green, the user has already approved #370 ready+merge;
- if real HTML mismatches, do not merge; keep fail closed and fix Draft safely.

### Safety

`LINE_MAIN_COVER_DISPLAY_ACTIVE / EXISTING_BUY_ONLY / MAX_2_DISTINCT_POINTS_PER_RACE / NO_THRESHOLD_RELAXATION / NO_SYNTHETIC_COVER / NO_AUTO_PURCHASE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-23 00:39 JST

This section supersedes the 2026-09-22 22:56 JST override below where they differ.

### Production availability activation approval / current main

The user explicitly approved proceeding with the V4 pre-freeze availability Production-effect wiring.

Fresh Source of Truth:
- current main: `79ee376282ba2da444b9f6d4aced8ed5b172e6b2`
- Railway Production staged changes: none
- no Railway Variables/Cron/service/volume change
- no Production DB write
- `purchase_action=false`

Already merged:
- PR #367 research availability capture/parser/binder/guard contracts
  - merge commit `9a80b4a5838fc63ea87c4e86cc77f2f5b890d64e`
- PR #369 shadow-only Production capture
  - merge commit `79ee376282ba2da444b9f6d4aced8ed5b172e6b2`
  - scheduled/fallback V4 workflow now captures timing-clean official availability raw before formal freeze
  - raw capture still has no eligibility effect on current main
  - normal formal V4 behavior remains unchanged until activation PR #370 is merged

### PR #370 — Production availability guard activation candidate

PR:
`Production: enforce V4 pre-freeze availability guard`

Current head:
`2a6f6f819023562b9d94f2fa273ffbee0b27d181`

State:
- Draft
- mergeable=true
- **7/7 exact-head CI SUCCESS**
- merge is user-approved **only after the first real timing-clean raw fixture validates the chain**

Important hardening added during activation review:
- real formal artifact timestamp is `generated_at_jst`; guard/binder now use it
- when `freeze_provenance.completed_at_jst` exists, it must equal `generated_at_jst`
- partial venue cancellation such as `11R以降中止` blocks only selected races at/after the boundary during raw binding; earlier selected races still require race-level active evidence
- runtime verifies capture request/manifest identity, raw filenames, raw SHA-256, exact-six snapshot, no replacement, no rerank and no purchase

Proposed Production behavior after #370 merge:
1. capture official availability raw before freeze;
2. generate the existing formal V4 core unchanged;
3. bind exact frozen six races to preserved raw;
4. evaluate availability guard;
5. upload normal `candidate-discovery-v4-prospective-freeze-<run_id>` artifact **only on `PASS_ACTIVE_CORE`**;
6. if capture/parser/guard fails or a selected race is pre-freeze unavailable, preserve a separate diagnostic guard artifact but do not publish the normal formal artifact;
7. fallback runs execute the same guard and cannot bypass a block.

No replacement candidate, no rerank, no denominator shrink, no result/payout read, no model/threshold/stake/candidate-count change.

### Real fixture merge gate

Synthetic CI is intentionally insufficient for merge.

Required:
- first real current-main timing-clean raw capture from #369;
- matching formal artifact from the same run;
- raw observation/capture proven before formal freeze;
- exact raw replay through #370 binder/parser/guard without hand-editing status/scope;
- supported real decision:
  - `PASS_ACTIVE_CORE`, or
  - correctly parsed `BLOCK_PRE_FREEZE_UNAVAILABLE_CORE`;
- all exact-head #370 CI green.

Any real HTML mismatch, ambiguity, missing raw or timestamp violation keeps #370 unmerged and must be fixed fail-closed in Draft.

### Scheduled natural validation

A one-time exact check is scheduled for **2026-09-23 08:45 JST** after:
- GitHub natural primary schedule at 08:16 JST, and
- independent Railway fallback checkpoint at 08:25 JST.

The validation must:
- re-fetch main / #370 / CI / Railway read-only state;
- select the earliest timing-clean valid run under the existing capture arbiter;
- verify raw + formal artifact identities/digests/timestamps;
- replay exact real bytes through #370;
- if and only if the real fixture validates and #370 exact-head CI is green, mark #370 ready and merge using the exact validated head SHA;
- re-fetch main after merge and record evidence.

User approval for this Production-effect merge has already been given in chat on 2026-09-23.

### Safety

`EXPLICIT_USER_APPROVAL / REAL_FIXTURE_BEFORE_MERGE / FAIL_CLOSED / EXACT_SIX / NO_REPLACEMENT / NO_RERANK / NO_RESULT_READ / NO_PAYOUT_READ / NO_DB_WRITE / NO_RAILWAY_CONFIG_CHANGE / PURCHASE_FALSE`

## LATEST OVERRIDE — 2026-09-22 22:56 JST

This section supersedes the 22:50 JST override below where they differ.

### PR #367 — pre-freeze availability chain complete through pure binder

Current head:
`6addf17f400fb6fbc9f7a9417b3efb3b799c8926`

State:
- Draft / mergeable
- **6/6 CI SUCCESS**
- no current-main / Production wiring

The research-only chain is now preregistered end-to-end up to the Production-effect boundary:

`full same-day race universe -> pre-freeze official raw capture -> raw SHA verification -> venue/race row extraction -> normalized exact-six snapshot -> availability guard`

New/strengthened components:
- `candidate_discovery_v4_pre_freeze_availability_capture.py`
  - request can be derived mechanically from full race-universe rows
  - validates race/date/venue/race_no/deadline identity
  - computes deterministic `race_universe_sha256`
  - uses earliest scheduled deadline in the full universe as hard stop
  - captures only official same-day index + per-venue `raceindex`
  - preserves exact raw bytes, timestamps, byte counts and SHA-256
  - result/payout endpoints are not part of the caller-configurable plan
- active parser
  - emits `evidence_binding_sha256` over the exact isolated race-row excerpt
- guard
  - same pre-freeze venue source may support multiple selected active races only at the same venue and only through distinct valid row bindings
  - cross-venue reuse / missing binding / duplicate binding fail closed
- `candidate_discovery_v4_availability_snapshot_binder.py`
  - pure/offline raw->snapshot bridge
  - recomputes raw SHA
  - rejects capture/source observation after artifact freeze
  - extracts isolated venue cancellation or exact race row
  - delegates normalization to the preregistered parsers
  - emits exactly six frozen core race rows
  - no replacement/rerank path

Synthetic-contract tests cover:
- all-active exact-six PASS;
- same-venue multi-core shared source with distinct bindings;
- whole-venue cancellation BLOCK;
- post-freeze raw rejection;
- raw SHA mismatch;
- missing venue source;
- duplicate/ambiguous race row;
- missing explicit `投票`.

### Remaining availability blockers

The main technical design gap is now closed, but **real evidence is still missing**.

Before any Production-effect use:
1. obtain a real timing-clean pre-freeze official raw capture on a future date;
2. run those exact bytes through the raw-capture -> binder -> parser -> guard chain without hand-editing status/scope;
3. review any real-HTML mismatch in Draft;
4. obtain explicit approval before merging/wiring this acquisition/guard path into current main or changing formal candidate eligibility behavior.

Do not capture after the core freeze and relabel it as pre-freeze evidence. Do not reconstruct from post-result pages.

### Other current state

Unless superseded above, the 22:36/22:50 overrides remain current:
- main `8867b77569d836b6c02a075fa6444550b1a46a6c`;
- #363 23/23 listed CI SUCCESS;
- #366 5/5 SUCCESS;
- #368 5/5 SUCCESS;
- Sep22 fallback run `35667553345` remains the formal capture; delayed scheduled run `35676316305` is later diagnostic with identical canonical core SHA;
- Sep21 and Sep22 remain post-result unevaluable because a frozen core race had no same-date final result;
- settled V4 corpus remains `2d / 12R / 24T / +920 JPY / ROI 138.333%`;
- Railway Production staged changes none;
- PostgreSQL volume 20GB; latest read-only disk around 4.645GB;
- no Production/model/threshold/candidate/purchase mutation.

### Safety

`PURCHASE_FALSE / PRE_FREEZE_EVIDENCE_ONLY / EXACT_RAW_SHA / EXACT_SIX / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_CAPACITY_DRIVEN_DELETE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-22 22:50 JST

This section supersedes the 22:36 JST override below where they differ.

### PR #367 — pre-freeze availability acquisition order fixed

Current head:
`d494181207cc8f6f4a0bb0422f6758fd58ad6bfc`

State:
- Draft / mergeable
- **6/6 CI SUCCESS**
- no current-main / Production wiring

Important timing-contract correction:

The guard requires every availability evidence observation to be no later than the V4 artifact freeze timestamp. Therefore:

`freeze six core races -> fetch official availability -> call it pre-freeze evidence`

is invalid, even when the fetch is still before all selected race deadlines.

The preregistered safe order is now:

`08:15 source cutoff -> capture official availability raw for the same-day venue universe -> freeze V4 core -> bind selected core rows to preserved raw`

New research-only files:
- `research/candidate_discovery_v4_pre_freeze_availability_capture.py`
- `tests/test_candidate_discovery_v4_pre_freeze_availability_capture.py`
- `docs/V4_PRE_FREEZE_AVAILABILITY_RAW_CAPTURE_CONTRACT_20260922.md`

Capture contract:
- target date + unique official venue IDs + earliest scheduled-universe deadline hard stop
- one same-day official `race/index?hd=YYYYMMDD`
- one official `race/raceindex?hd=YYYYMMDD&jcd=XX` per scheduled venue
- no caller-configurable result/payout endpoint
- capture starts at/after 08:15 JST
- every source must complete before the preregistered earliest scheduled race deadline
- exact raw bytes, observation time, byte count and SHA-256 are preserved
- redirect, empty payload, oversized payload or timing overrun fail closed
- `purchase_action=false`

Same-venue multi-core handling:
- active parser emits `evidence_binding_sha256` over the exact isolated race-row excerpt
- one preserved pre-freeze venue source may support multiple selected active races at the same venue only with distinct valid row-binding SHAs
- cross-venue reuse, missing row bindings or duplicate row bindings fail closed

This closes the design-order gap only. **Real timing-clean official raw fixtures are still not captured by current main.** Any Production-effect merge/wiring of this capture layer remains explicit-approval gated.

### Current stable state

Unless superseded above, the 22:36 JST override remains current:
- main `8867b77569d836b6c02a075fa6444550b1a46a6c`
- #363 all 23 listed CI SUCCESS
- #366 5/5 SUCCESS
- #368 5/5 SUCCESS
- Sep22 fallback formal capture remains valid; delayed primary is diagnostic only
- Sep21/Sep22 remain excluded from settled formal metrics due cancelled frozen core races
- formally evaluated corpus remains `2d / 12R / 24T / +920 JPY / ROI 138.333%`
- Railway Production staged changes none
- no Production/model/threshold/candidate/purchase mutation

### Next safe boundary

The next timing-clean raw availability fixture cannot be manufactured after freeze. To collect it automatically on a future date, the preregistered pre-freeze capture path must first be reviewed and any main/Production-effect workflow wiring explicitly approved.

Until then:
- do not use post-freeze or post-result pages as missing pre-freeze evidence;
- keep natural fallback monitoring read-only;
- keep Storage/Hobby work research-only;
- no forced plan downgrade or capacity-driven deletion.

### Safety

`PURCHASE_FALSE / PRE_FREEZE_EVIDENCE_ONLY / NO_RESULT_AFTER_RECONSTRUCTION / NO_RETUNE / NO_CAPACITY_DRIVEN_DELETE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-22 22:36 JST

This section supersedes the 2026-09-21 14:58 JST override below where they differ.

### Fresh Source of Truth / CI / Railway

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- PR #363 Storage: `4cccdc5b41241f6ffa139be629172cf5a03d7500`, Draft / mergeable, all 23 listed workflows SUCCESS
- PR #366 post-result evaluator/evidence: `20c835c5dabd847c96180acad6a3daf5ffd8fdf7`, Draft / mergeable, 5/5 CI SUCCESS
- PR #367 availability guard/parsers: `fd86320d848474463d943c7d84b6d419a3838cfa`, Draft / mergeable, 6/6 CI SUCCESS
- PR #368 economics gate: `2e47342912e545f8341e8678c10e940e94bcd2f3`, Draft / mergeable, 5/5 CI SUCCESS
- Railway Production staged changes: none
- fallback deployment remains `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS, Cron `25 23 * * *` UTC = 08:25 JST
- PostgreSQL volume remains 20GB
- fresh read-only 7d disk metric: current ~`4.645 GB`, observed max ~`4.657 GB`
- no Production DB/Railway/model/threshold/candidate/purchase mutation was made

### 2026-09-22 V4 fallback operational proof

The natural Railway fallback checkpoint executed successfully.

Railway log:
- 08:26 JST: `DISPATCH_FALLBACK`
- reason: `no_valid_primary_artifact_observable`
- no second same-date fallback dispatch was observed

Fallback GitHub run:
- run `35667553345`
- event `workflow_dispatch`
- generated `2026-09-22T08:26:36.137106+09:00`
- artifact `10670080150`
- artifact ZIP SHA-256 `60ae93e3758679fc0109fd180bbd66a54978c0b483514a724bb5ace376c5a94c`
- JSON SHA-256 `3e59a58c3704baeb991a102c58a4a92ff56670e1b1e7039cd5df42c6e68dd7d9`
- canonical core SHA-256 `1514b991505565763f412bdc3515eb64613c4de61d49cd51748fb01af61373d9`
- formal core `6R / 12T`
- legacy shadow rows `0`
- earliest core deadline `12:10 JST`
- `prospective_evidence_eligible=true`
- `purchase_action=false`
- `PASS_PRE_RESULT_FREEZE`

The delayed GitHub scheduled primary later appeared:
- run `35676316305`
- event `schedule`
- generated `2026-09-22T10:35:38.887230+09:00`
- artifact `10673271438`
- JSON SHA-256 `b2c54f521a1415fdb7190b8e340c39442b7baaafacbcc2278e4b925c836a4eb1`
- canonical core SHA-256 is the **same** `1514b991505565763f412bdc3515eb64613c4de61d49cd51748fb01af61373d9`
- legacy shadow rows `9`

Under the preregistered capture arbiter:
- the unique earliest valid capture (08:26 fallback) is the formal artifact;
- the 10:35 scheduled capture is a later diagnostic only;
- the formal day is not double-counted;
- full-file differences caused by auxiliary legacy state do not change formal-core identity.

This is strong live evidence that the independent fallback mechanism works for the exact delayed-GitHub-schedule failure mode it was designed to cover.

### 2026-09-22 post-result blocker

Frozen fallback core races:
- `20260922_01_06`
- `20260922_17_04`
- `20260922_09_05`
- `20260922_02_08`
- `20260922_02_11`
- `20260922_03_07`

BOAT RACE official current 2026-09-22 state marks venue 09 / 津 as cancelled. The frozen formal core contains `20260922_09_05` (津 5R).

Therefore Sep22 cannot be scored under the frozen six-outcome contract:

`FORMAL_AVAILABLE / POST_RESULT_UNEVALUABLE_CORE_RACE_CANCELLED / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

Important evidence-strength boundary:
- current cancellation state is authoritative post-result evidence;
- no immutable pre-freeze raw official payload is recorded here proving the exact time the Sep22 津 cancellation became observable;
- do not retroactively label pre-freeze observability without such preserved evidence.

PR #366 now contains:
`research/evidence/v4_formal_eval_blocker_20260922.json`

The formally **evaluated** V4 corpus therefore remains:
`Sep18 + Sep19 = 2d / 12R / 24T / +920 JPY / ROI 138.333%`

Sep21 and Sep22 are formal-artifact-valid but post-result unevaluable because a frozen core race has no same-date final outcome.

### Storage / plan-change state

PR #363 is fully green at this checkpoint, but real Hobby readiness is still false:
- zero-consumer/recovery/retained-set requirements are not all closed;
- no decision-grade fresh retained-set restore has been executed;
- current 20GB volume cannot be used as a direct Hobby-size proof;
- disk growth reinforces the need for measured fresh-restore size + frozen headroom rather than capacity-driven deletion.

October dates remain Go/No-Go checkpoints, not forced downgrade dates. Positive prospective system economics may justify retaining Railway Pro and/or ChatGPT Plus. Cost pressure must never alter thresholds, stake, candidate count, evidence retention or safety.

### Next safe work

1. Keep Sep21 and Sep22 out of formal settled metrics; no denominator shrink or synthetic loss.
2. Preserve the Sep22 fallback-vs-primary equivalence evidence; no duplicate formal counting.
3. On the next timing-clean future date, capture real predeadline official raw availability fixtures before results if available; do not reconstruct them afterward.
4. Continue Storage/Hobby readiness with research-only fresh-restore preparation and natural zero-consumer evidence.
5. Observe the next natural 08:25 JST fallback checkpoint without forcing Production jobs.
6. No Production-effect PR merge, DB mutation, Railway config/plan change, model/threshold/candidate change or purchase action without explicit approval.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_CAPACITY_DRIVEN_DELETE / NO_FORCED_PLAN_DOWNGRADE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-21 14:58 JST

This section supersedes the 14:26 JST override below where they differ.

### Fresh Source of Truth / Production state

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- Railway Production staged changes: none
- V4 fallback latest deployment: `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS
- PostgreSQL `postgres-recovery`: existing 20GB volume unchanged
- fresh read-only 7d disk metric: current ~`4.599 GB` (observed max ~`4.599 GB`)
- no Production DB/Railway/model/threshold/candidate/purchase mutation was made

October plan changes remain **Go/No-Go checkpoints, not forced downgrade dates**. Positive system economics may justify retaining higher-capability Railway/ChatGPT plans; cost pressure must not change thresholds, stake, candidate count, evidence retention or safety.

### PR #363 — fresh restore readiness contract hardened

Current head:
`4cccdc5b41241f6ffa139be629172cf5a03d7500`

State:
- Draft / mergeable
- dedicated `Research fresh restore rehearsal manifest contract`: SUCCESS
- at this checkpoint, all listed exact-head workflows are SUCCESS except one read-only probability-calibration archive-consumer workflow still in progress
- no restore was executed

New fail-closed invariants:
- Hobby capacity ceiling is the conservative decimal `5,000,000,000` bytes; do not substitute 5 GiB
- bounded retention boundary SHA-256 is recomputed from the exact UTF-8 boundary string
- prerequisite manifest gets a canonical SHA-256 fingerprint
- post-rehearsal acceptance requires the exact original preregistered manifest
- volume limit / reserve / measured growth / growth horizon must match that preregistration exactly
- post-hoc headroom-policy changes fail closed
- a PASS still does not authorize Production migration

Current real gate remains:
`REHEARSAL_PREREQUISITES_NOT_READY / HOBBY_READY_NOW_FALSE / OCT03_GO_NO_GO_NOT_FORCED_CUTOVER / NO_CAPACITY_DRIVEN_DELETE`

### PR #367 — negative + positive official availability parser preregistration

Current head:
`fd86320d848474463d943c7d84b6d419a3838cfa`

State:
- Draft / mergeable
- **6/6 CI SUCCESS**
- research-only / no Production wiring

Hardening now includes:
- availability snapshot race rows must equal the exact six formal core race IDs; unexpected non-core rows fail closed
- block parser canonicalizes official URL shape and prevents multi-venue excerpt ambiguity
- negative evidence remains raw-bytes + SHA-256 bound
- separate positive race-level parser is preregistered against official venue `raceindex?hd=YYYYMMDD&jcd=XX`
- positive parser requires selected race row + exact frozen deadline + explicit `投票`, observed strictly before deadline
- `発売終了`, `中止`, or `順延` blocks positive parsing
- page/card/deadline existence alone never becomes `active`

Important limitation:
the positive parser currently has synthetic contract fixtures only. **Real preserved official active and cancelled/postponed raw fixtures with SHA-256 are required before any Production wiring.**

No replacement, no rerank, no result/payout read, `purchase_action=false`.

### PR #368 — V4 Forward economics gate hardened

Current head:
`2e47342912e545f8341e8678c10e940e94bcd2f3`

State:
- Draft / mergeable
- **5/5 CI SUCCESS**
- descriptive-only / pure offline

Economics input now requires:
- each evaluated formal day exactly `6R / 12T / 100 JPY per frozen ticket`
- hit hierarchy `exact <= first+second prefix <= head`
- third-only misses cannot exceed non-exact prefix hits
- period operating cost components must reconcile to the supplied total
- complete cost basis requires named components + allocation notes
- incomplete cost basis returns `observed_net_positive=null` and `net_after_cost_decision_grade=false`

The project 30/50/100 prospective **case** milestones are not redefined as formal race counts.

Current formal result remains descriptive small-sample evidence only:
- Sep18: -100 JPY
- Sep19: +1,020 JPY
- combined: +920 JPY / ROI 138.333%
- no plan-retention/downgrade conclusion from this two-day corpus alone

### PR #366 / Sep21 formal status

PR #366 remains Draft/mergeable at:
`95d7af3efd79ead86bfdf4f708ba3065b283d6f9`
with its prior 5/5 CI SUCCESS.

Sep21 remains:
`CAPTURE_CONTRACT_VALID / POST_RESULT_UNEVALUABLE / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

### Next natural / safe work

1. Let the remaining PR #363 read-only probability-calibration CI finish naturally.
2. 2026-09-21 19:30 JST: final Sep21 official-state confirmation; do not score unless all exact six same-date finalized outcomes+payouts exist.
3. 2026-09-22 08:40 JST: audit the natural 08:25 fallback Cron.
4. For PR #367 positive evidence, capture/review real official raw fixtures only in a future timing-clean pre-deadline observation; do not reconstruct after results.
5. Continue Storage zero-consumer evidence naturally; do not force Production jobs or delete data for capacity.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_CAPACITY_DRIVEN_DELETE / NO_FORCED_PLAN_DOWNGRADE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-21 14:26 JST

This section supersedes the 14:15 JST override below where they differ.

### New safe research work completed

#### PR #363 — fresh restore rehearsal prerequisite gate

Current latest branch head at this checkpoint:
`e9c9ecaf880742802494ee1daa9d7625b3502595`

Added a pure/offline fail-closed manifest contract before any retained-set copy can be considered decision-grade.

Required before a non-Production rehearsal can PASS:
- exact source main SHA;
- Production source read-only and destructive operations false;
- target non-Production + ephemeral;
- frozen per-table retained-set policy;
- protected evidence tables explicitly retained;
- verified primary archive and independent second recovery layer;
- manifest SHA for excluded cold partitions;
- frozen schema/migration-script/index/constraint/extension identity;
- frozen 5 GiB headroom policy with reserve covering measured growth horizon;
- Production migration authorization explicitly false.

Current real state remains:
`REHEARSAL_PREREQUISITES_NOT_READY / HOBBY_READY_NOW_FALSE / OCT03_GO_NO_GO_NOT_FORCED_CUTOVER`

The first focused CI failure was test-only: the isolation test matched the word `Railway` in a docstring. The test was corrected to inspect imports/API surfaces rather than comments. Re-fetch the latest exact-head CI before acting.

#### PR #367 — preserved-raw official availability parser

Current head:
`03dcc9df578730e1feae403b64df5f92df649503`

State:
- Draft / mergeable
- **6/6 CI SUCCESS**
- research-only / no Production wiring

Added a BLOCK-only pure parser:
- exact official raw payload is preserved as base64;
- parser recomputes SHA-256 before parsing;
- human-readable evidence excerpt must occur exactly once in those preserved bytes;
- venue/day evidence supports whole-venue unavailable markers such as `中止順延` / `開催中止`;
- race-page evidence supports `レース中止`;
- URL date/venue/race identity is checked;
- parser never emits `active`;
- page existence, deadline presence, or lack of cancellation text never becomes positive evidence.

Positive race-level active evidence remains unresolved and requires a separate preregistered parser/acquisition contract before Production use.

#### New Draft PR #368 — V4 Forward economics summary

Branch:
`research/v4-forward-economics-gate-20260921`

Current head:
`11f8f63f2b91c7a806b70395b569a11dfcf2c5aa`

Purpose:
- summarize formal wagering profit, ROI, cumulative drawdown and period-matched operating cost;
- never auto-change Railway/ChatGPT plans;
- reject evidence where cost pressure changed threshold, stake, candidate count, result-after policy or purchase safety;
- remain pure/offline with no DB/network/Railway/LINE/purchase path.

Important evidence-separation correction:
the project 30/50/100 milestones are not silently redefined as formal post-result race counts. They belong to separately preregistered case definitions such as Stage2 supported cases and Primary-vs-Challenger prospective cases. PR #368 reports economics only and requires milestone context separately.

Current formal economics remain descriptive:
- Sep18: -100 JPY / ROI 91.667%
- Sep19: +1,020 JPY / ROI 185.000%
- combined: +920 JPY / ROI 138.333%
- two-day cumulative max drawdown: 100 JPY

Classification:
`SMALL_DESCRIPTIVE_FORMAL_CORPUS / PROJECT_MILESTONES_NOT_REDEFINED / HUMAN_REVIEW_REQUIRED / NO_AUTO_PLAN_CHANGE / NO_RETUNE / PURCHASE_FALSE`

### Source of Truth / Production safety

- Boat main remains `8867b77569d836b6c02a075fa6444550b1a46a6c`.
- PR #366 remains Draft/mergeable at `95d7af3efd79ead86bfdf4f708ba3065b283d6f9`.
- Railway Production staged changes remain none.
- fallback latest deployment remains `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS.
- no Production DB/Railway/model/threshold/candidate/purchase mutation was made.

### Next natural / safe work

1. Finish exact-head CI verification for PR #363 and PR #368.
2. 2026-09-21 19:30 JST: final Sep21 official-state confirmation; do not score Sep21 unless all exact six same-date outcomes+payouts exist.
3. 2026-09-22 08:40 JST: natural 08:25 fallback Cron audit.
4. Continue Storage evidence naturally; do not force-run Production jobs.
5. Do not implement positive availability PASS or Production wiring until separately preregistered and explicitly approved where Production behavior changes.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_EVIDENCE_MIXING / NO_CAPACITY_DRIVEN_DELETE / NO_FORCED_PLAN_DOWNGRADE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-21 14:15 JST

This section supersedes the 14:14 JST override below where they differ.

### Railway / ChatGPT plan checkpoints

The plan-change policy from 14:14 JST remains in force: October dates are Go/No-Go checkpoints, not forced downgrade dates. If prospective system economics support keeping higher-capability plans, cost reduction is not prioritized over system quality, safety, evidence preservation or development capability.

Fresh Railway official documentation recheck on 2026-09-21 confirms:
- Hobby volume limit: 5 GB;
- Production's current PostgreSQL volume is still 20 GB;
- volume down-sizing is not supported;
- therefore Pro -> Hobby still requires a fresh compatible retained-set migration/restore rather than shrinking the existing volume in place.

The 10/03 Railway checkpoint remains conditional on fresh-restore size/headroom, dependency/consumer gates, archive/recovery safety and explicit Production approval.

The 10/14 ChatGPT Plus -> Go checkpoint is also conditional. Retain Plus when its additional development/review capability is materially worth the cost; do not downgrade solely to meet an arbitrary monthly-cost target.

### Storage PR #363 correction

A transient GitHub mergeability read briefly returned `mergeable=false`. A fresh recheck now reports:
- head `65219db0b6ae1b4d181fe8d9cdeb1187a69b898b`;
- Draft;
- `mergeable=true`;
- base current main `8867b77569d836b6c02a075fa6444550b1a46a6c`;
- compare status `ahead`, behind=0.

Several read-only archive/storage workflows are still in progress on this head; completed critical syntax/isolation/runtime-contract workflows are passing. Do not interpret the transient mergeability result as a persistent conflict.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_CAPACITY_DRIVEN_DELETE / NO_FORCED_PLAN_DOWNGRADE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`

## LATEST OVERRIDE — 2026-09-21 14:14 JST

This section supersedes the 13:30 JST override below where they differ.

### Cost / plan-change decision policy

The October plan-change dates are **Go/No-Go checkpoints, not forced downgrade dates**.

Current target schedule:
- 2026-10-01 through 2026-10-02: read-only Railway usage / storage / dependency audit.
- 2026-10-03 billing boundary: consider Railway Pro -> Hobby only if data preservation, zero/known-consumer boundaries, fresh retained-set restore, measured growth and safe volume headroom all pass.
- by 2026-10-14: reconsider ChatGPT Plus -> Go.

Decision rule:
- do not downgrade merely to meet a monthly-cost target;
- if prospective system performance supports sustainable positive net return after infrastructure/AI costs, retaining the more capable plan is acceptable;
- evaluate system economics using prospective ROI, payout distribution, drawdown/variance, eligible race volume and recurring operating cost, not hit rate alone;
- small-sample Sep18/Sep19 profit is not sufficient evidence by itself; formal milestones remain the basis for stronger conclusions;
- keep ChatGPT Plus when the additional development/review capability materially improves code quality, safety, research velocity or defect detection enough to justify its cost;
- Railway Pro -> Hobby remains blocked until the fresh <=5GB retained-set restore plus frozen headroom policy is proven; never delete required evidence just to force Hobby fit;
- never loosen prediction thresholds, stakes, candidate counts or safety gates to recover subscription/infrastructure costs.

If a checkpoint is not ready, **continue the current plan temporarily and move the decision date** rather than performing an unsafe migration or capability downgrade.

Any Railway Production plan/service/volume/config migration remains an explicit-approval action. ChatGPT subscription changes remain a user account decision and are not automatic.

### Fresh current-state note

- Boat main remains `8867b77569d836b6c02a075fa6444550b1a46a6c`.
- PR #366 remains Draft/mergeable at `95d7af3efd79ead86bfdf4f708ba3065b283d6f9`.
- PR #367 remains Draft/mergeable at `14f4f4abfb5ffaa3fbb809aa97664cdb5a5cfd86`.
- Storage PR #363 has advanced to `65219db0b6ae1b4d181fe8d9cdeb1187a69b898b` and currently reports `mergeable=false`; re-audit the branch before editing or relying on older Storage-head status.
- Production safety remains `PURCHASE_FALSE / NO_RETUNE / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`.

## LATEST OVERRIDE — 2026-09-21 13:30 JST

This section supersedes the 13:21 JST override below where they differ.

### PR #367 — multi-source availability evidence

Head:
`14f4f4abfb5ffaa3fbb809aa97664cdb5a5cfd86`

- Draft / mergeable
- 5/5 CI SUCCESS
- research-only / offline / no Production wiring

The availability snapshot no longer assumes one official URL/digest can substantiate all six selected races.

Current preregistered evidence contract:
- non-empty `evidence_sources[]`;
- each source has unique `evidence_id`, pre-freeze `observed_at`, BOAT RACE official URL, raw-content SHA-256, optional source-displayed update time;
- each selected core race references an `evidence_id`;
- race-level `active` is required for PASS;
- venue-level `active` cannot PASS;
- venue-level `cancelled_postponed` may BLOCK;
- race-positive evidence cannot be reused for a different selected core race;
- venue-wide unavailable evidence can be shared only within the same venue;
- contradictory venue-wide unavailable + active state fails closed;
- venue ID must be 01..24.

The pure guard does not itself parse BOAT RACE raw bytes. Any future Production acquisition/parser must prove preserved payload -> SHA-256 -> normalized status/scope. Page existence or scheduled deadline alone is not race-level active evidence.

### Unchanged from 13:21

- Boat main: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- PR #366: `95d7af3efd79ead86bfdf4f708ba3065b283d6f9`, Draft/mergeable, 5/5 CI SUCCESS
- strict Sep18/Sep19 replay: 2 days / 12R / 24T / profit +920 / ROI 138.333%
- Sep21: unscored / post-result unevaluable
- Storage: `ZERO_CONSUMER_NOT_REACHED`
- Railway Production staged changes: none
- fallback deployment remains SUCCESS
- no Production mutation

### Next

1. 19:30 JST Sep21 final-state confirmation.
2. 2026-09-22 08:40 JST fallback Cron audit.
3. Natural-only candidate-shadow evidence; no forced Production runs.
4. No Production-effect PR #367 wiring without explicit approval.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 13:21 JST

This section supersedes the 13:05 JST override below where they differ.

### GitHub / Railway current state

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- Railway Production staged changes: none
- fallback service deployment `7c0b590e-a121-42d2-9f88-543848af386f`: SUCCESS
- fallback Cron: `25 23 * * *` UTC = 08:25 JST
- no Production DB/Railway/model/threshold/candidate/purchase mutation made

### PR #367

Head:
`3afde0ef65a0601c684b334800ada0332b7ee57f`

- Draft / mergeable
- 5/5 CI SUCCESS
- research-only pre-freeze availability guard
- exact 6-race identity and evidence-scope checks
- immutable source-content SHA-256 required by the offline guard contract
- no candidate replacement/rerank/result read
- no Production wiring

### PR #366

Head:
`95d7af3efd79ead86bfdf4f708ba3065b283d6f9`

- Draft / mergeable
- 5/5 CI SUCCESS
- pure/offline post-result evaluator

Strict evaluator additions:
- CLI artifact SHA-256 required and verified before JSON parsing;
- exact six-core outcome set required;
- unexpected extra outcome rows rejected;
- missing/duplicate/malformed outcomes rejected;
- explicit non-final statuses rejected;
- cancellation/postponement cannot be converted into a synthetic loss or later-date substitution.

Read-only strict replay from retained immutable artifacts:
- Sep18 artifact `10527500527`, SHA `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
- Sep19 artifact `10574052434`, SHA `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`

Reproduced formal metrics exactly:
`2 days / 12R / 24T / investment 2400 / return 3320 / profit +920 / ROI 138.333%`

Evidence:
`research/evidence/v4_formal_repro_check_20260921.json`

Sep21 remains:
`CAPTURE_CONTRACT_VALID / RACE_UNIVERSE_AVAILABILITY_GAP / POST_RESULT_UNEVALUABLE / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

The earlier official-page observation remains evidence-strength-limited because the exact 08:25 raw payload was not preserved with a digest.

### PR #363 Storage

Fresh current head:
`c3a87df234b06f220ab7128d129dbc32f0354e84`

- Draft / mergeable
- 21 listed workflows SUCCESS
- 1 read-only probability-calibration archive-consumer workflow in progress at this check
- gate remains:
  `ZERO_CONSUMER_NOT_REACHED / ACTIVE_WRITERS / ACTIVE_READERS / SAME_DAY_WRITE_TO_READ_PROVEN / NO_DELETE / NO_MIGRATION / NO_VACUUM`

The head SHA above supersedes the 13:05 override's PR #363 SHA for current-state purposes.

### Next

1. 19:30 JST: re-confirm Sep21 final official status; no formal scoring unless all exact six same-date outcomes+payouts exist.
2. 2026-09-22 08:40 JST: audit natural 08:25 fallback Cron.
3. Continue natural-only Storage evidence; do not manually force Production jobs.
4. No Production-effect use of PR #367 without explicit approval.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 13:05 JST

This section supersedes the 12:59 JST override below where they differ.

### GitHub Source of Truth

- `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- no new main merge
- Production behavior unchanged

### PR #367 — pre-freeze availability guard

Current head:
`3afde0ef65a0601c684b334800ada0332b7ee57f`

State:
- Draft / mergeable
- 5/5 CI SUCCESS
- research-only / pure offline / no Production wiring

Guard now fails closed unless the formal core identity is exact:
- 6 core races
- ranks 1..6
- core orders 1/2 per race
- target date / venue / race-number identity consistent

Official snapshot provenance now requires:
- BOAT RACE official URL
- timezone-aware observation/update timestamps
- lowercase SHA-256 content digest
- row evidence scope: `race` or `venue`

Scope rule:
- venue-level unavailable => may BLOCK selected race
- venue-level active => cannot PASS individual race
- PASS requires race-scoped active evidence for every selected core race

No replacement/rerank/recovery behavior exists.

### PR #366 — Sep21 evaluation / evidence strength

Current head:
`714e96271a50b785fd2b4caeb6f0c27a4f413eed`

State:
- Draft / mergeable
- 5/5 CI SUCCESS
- formal evaluated corpus remains Sep18 + Sep19 only

Sep21 remains:
`CAPTURE_CONTRACT_VALID / POST_RESULT_UNEVALUABLE / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

Additional provenance caveat:
the 08:25 pre-freeze official-page observation was recorded, but no immutable raw 08:25 payload hash exists. Because the official page is mutable, URL-only replay is insufficient. Future Production-effect availability evidence requires preserved raw observation + deterministic SHA-256.

### Storage

PR #363 head:
`562e4ac577a3ca9ba7e5e2c5367fd8e10deb3082`

Gate:
`ZERO_CONSUMER_NOT_REACHED / ACTIVE_WRITERS / ACTIVE_READERS / SAME_DAY_WRITE_TO_READ_PROVEN / NO_DELETE / NO_MIGRATION / NO_VACUUM`

At 13:05 JST one read-only archive-consumer workflow was in progress on the same head; no gate change.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 12:59 JST

This section supersedes the 11:06 JST override below where they differ.

### New Draft PR #367 — pre-freeze availability guard preregistration

Draft PR #367 was created from current main:
- title: `Research: preregister V4 pre-freeze availability guard`
- branch: `research/v4-pre-freeze-availability-guard-20260921`
- Production wiring: none
- DB/network/Railway/LINE/purchase path: none
- guard role: eligibility BLOCK only; no candidate removal-and-replacement, no reranking
- granularity: each of the exact six frozen core races is independently classified, so a single-race cancellation at an otherwise active venue can be represented safely
- missing/duplicate/unknown/late/mismatched availability evidence fails closed
- snapshot observed after artifact freeze is rejected
- Sep21 regression fixture anchors the affected core race `20260921_02_08`

This PR is research-only and must remain separate from any future Production candidate/capture eligibility change. Explicit approval is required before Production wiring/merge that changes behavior.


### Boat / Production Source of Truth

- GitHub `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- Railway Production: project `boat-v2-postgres`
- fallback service remains active on `main`, Cron `25 23 * * *` UTC = 08:25 JST, latest deployment `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS, no staged Production changes
- initial fallback start remained `NOOP_VALID_PRIMARY target_date=2026-09-21 primary_run_id=35549611949`

### 2026-09-21 formal V4 classification refinement

The immutable artifact remains capture-contract-valid:
- run `35549611949`
- generated `2026-09-21T10:03:12.277823+09:00`
- `6R / 12T`
- result/payout read 0
- DB/LINE/BUY/Production change 0
- `purchase_action=false`

Frozen core includes `20260921_02_08` (Toda 8R). BOAT RACE official today's-race page was already updated at 08:25 JST showing Toda cancelled/postponed, before the 10:03 formal freeze.

Current-main V4 generator loads target-date `v2_races`, requires complete six-lane entries and a deadline, but has no pre-result cancelled/postponed race/venue availability filter. `v2_races` has no current compatibility field suitable for this pre-result status check.

Current classification:
`CAPTURE_CONTRACT_VALID / PRE_FREEZE_OFFICIAL_CANCELLATION_OBSERVABLE / RACE_UNIVERSE_AVAILABILITY_GAP / POST_RESULT_UNEVALUABLE / NO_REGENERATION / NO_RETUNE`

Formal evaluated corpus therefore remains only Sep18 + Sep19:
`2 days / 12 races / 24 tickets / investment 2400 JPY / return 3320 JPY / profit +920 JPY / ROI 138.333%`

Do not:
- shrink Sep21 from 6R to 5R;
- create a synthetic zero-yen loss/payout;
- substitute a later postponed-date result;
- regenerate a replacement candidate using knowledge of cancellation/results;
- implement a Production availability filter without explicit approval.

PR #366 contains Draft-only evidence:
- `research/evidence/v4_pre_freeze_race_availability_gap_20260921.json`
- `research/evidence/v4_formal_eval_blocker_20260921.json`
- cancellation/non-final fail-closed tests and contract docs.

### Candidate-shadow / Storage gate

Fresh Production evidence on 2026-09-21:
- morning PRE collector invoked: `candidate_rows=0 / saved_rows=0`;
- day PRE collector invoked: `candidate_rows=7 / saved_rows=7`;
- formal V4 subsequently read `legacy_shadow_rows=7`, adding 5 legacy races / 7 legacy tickets.

Railway Production still contains:
- morning/day/night `run_window_pipeline_pg.py` candidate-shadow writer surfaces;
- nightly `run_nightly_results_pg.py` candidate-shadow evaluator/report reader surface;
- no-Cron `test-beforeinfo-extra` direct collector writer surface.

Current-main GitHub V4 prospective-freeze path is also a candidate-shadow reader.

PR #363 pure runtime-source contract now blocks candidate-shadow zero-consumer on either **writer or reader** capabilities. A zero-row window, a no-Cron service, a Draft-only removal, or the fallback dispatcher's lack of DB dependency is not sufficient for PASS.

Machine evidence:
`research/evidence/candidate_shadow_zero_consumer_gate_20260921.json`

Current gate:
`ZERO_CONSUMER_NOT_REACHED / SAME_DAY_WRITER_TO_READER_PROVEN / ACTIVE_WRITER_SURFACES / ACTIVE_READER_SURFACES / NO_DELETE / NO_MIGRATION / NO_VACUUM`

### PostgreSQL capacity observation

Fresh read-only Railway metrics:
- current disk ~`4.593 GB`;
- 24h observed range ~`4.561 -> 4.593 GB`;
- 7d observed range ~`4.136 -> 4.591 GB`.

These are observations, not a linear growth forecast. They do not authorize deletion. Direct current-footprint Hobby migration is not approved; a proven fresh retained-set restore plus measured growth/headroom remains required.

### Next natural evidence

1. 2026-09-21 19:30 JST: re-confirm Toda final official state; keep Sep21 evaluation blocked unless all six exact same-date final outcomes+payouts exist.
2. 2026-09-22 08:40 JST: audit the natural 08:25 fallback Cron execution.
3. Allow normal night/nightly Production schedules to provide natural candidate-shadow evidence; do not manually trigger them for audit.
4. Keep Production model/coefficient/threshold/candidate logic unchanged without explicit approval.

Safety:
`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 11:06 JST

This section supersedes the 10:40 JST override below where they differ.

### Fresh read-only re-audit

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- PR #364: merged.
- Railway fallback service:
  - `candidate-discovery-v4-fallback-dispatcher`
  - source `kenshoushouri-cloud/boat-ai-v2@main`
  - Cron `25 23 * * *` UTC = 08:25 JST
  - restart `NEVER`
  - latest deployment `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS
  - staged changes none
  - initial real start: `NOOP_VALID_PRIMARY target_date=2026-09-21 primary_run_id=35549611949`
  - no workflow_dispatch run created
- PostgreSQL `postgres-recovery`: 20GB volume; fresh 24h metrics remain healthy enough for read-only operation. No cleanup/VACUUM/migration authorized.
- Storage: 2026-09-21 natural day writer produced `candidate_rows=7 / saved_rows=7` (S03=7), and formal V4 read `legacy_shadow_rows=7`. Therefore `ZERO_CONSUMER_NOT_REACHED` remains true.

### 2026-09-21 formal V4 status refinement

Pre-result artifact validity is unchanged:
`FORMAL_AVAILABLE / NATURAL_SCHEDULE_DELAYED_BUT_PREDEADLINE_VALID / CORE_6R_12T / ARTIFACT_PRESENT / PURCHASE_FALSE`

But post-result evaluation is now blocked by a cancellation edge case.

Frozen core includes:
- `20260921_02_08` = venue 02 / Toda 8R
- frozen deadline 14:16 JST
- frozen tickets `1-2-6`, `1-6-2`

BOAT RACE official same-day pages later marked Toda as cancelled/postponed for 2026-09-21. PR #366 contract requires all six exact finalized same-date outcomes/payouts and already fails closed on a missing outcome.

Therefore:
`FORMAL_AVAILABLE / POST_RESULT_UNEVALUABLE_CORE_RACE_CANCELLED / EVALUATED_CORPUS_STAYS_2_DAYS_12R_24T`

Forbidden:
- shrinking the formal denominator from 6R to 5R;
- treating the cancelled race as a synthetic loss or zero-yen payout;
- using the later postponed-date result as if it were the frozen 2026-09-21 race;
- regenerating a replacement candidate after cancellation;
- retuning model/coefficients/thresholds.

PR #366 now contains:
- `research/evidence/v4_formal_eval_pending_manifest_20260921.json`
- `research/evidence/v4_formal_eval_blocker_20260921.json`
- explicit cancellation/postponement fail-closed policy in the post-result evaluation contract.

### Next

1. Next natural Railway fallback Cron at 08:25 JST is the highest-priority operational check.
2. 2026-09-21 formal metrics stay unchanged unless the exact six same-date outcomes/payouts become authoritatively available.
3. Continue Storage read-only zero-consumer evidence only.
4. No Production/model/threshold/purchase change.


## LATEST OVERRIDE — 2026-09-21 10:40 JST

This section supersedes older state/SHA/fallback descriptions below. On resume, re-fetch GitHub/Railway before acting.

### Critical current state

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- PR #364 V4 capture resilience: **MERGED** into main.
- Production fallback service is now active:
  - service: `candidate-discovery-v4-fallback-dispatcher`
  - service ID: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
  - source: `kenshoushouri-cloud/boat-ai-v2@main`
  - start: `python -u research/candidate_discovery_v4_fallback_dispatcher.py`
  - Cron: `25 23 * * *` UTC = **08:25 JST**
  - restart policy: `NEVER`
  - volume/domain: none
  - required service variables exist: `V4_FALLBACK_GITHUB_REPOSITORY`, `V4_FALLBACK_GITHUB_TOKEN`
  - never record or expose the token value
  - deployment `7c0b590e-a121-42d2-9f88-543848af386f`: SUCCESS
- Railway Production staged changes: **none** after activation.
- Fallback contract: valid primary artifact => NOOP; otherwise at most one same-date `workflow_dispatch`; existing prospective wrapper remains final validity authority; no result-after rescue/backfill.
- First real service start (triggered by initial deployment, not scheduled Cron) safely returned:
  `NOOP_VALID_PRIMARY target_date=2026-09-21 primary_run_id=35549611949`
  and created **no workflow_dispatch run**.

### 2026-09-21 formal V4

Natural scheduled primary eventually appeared:
- run `35549611949`, event=`schedule`
- created/started **10:02:54 JST**
- wrapper start **10:03:09.941 JST**
- completion **10:03:12.278 JST**
- source cutoff 08:15 JST
- scheduled/evaluable **156/156**
- formal core **6 races / 12 tickets**
- full feed **11 races / 19 tickets**
- legacy shadow rows=7; legacy added 5 races / 7 tickets
- earliest core deadline **10:18 JST**
- earliest feed deadline **10:18 JST**
- result/payout reads=0; DB write=0; LINE=0; BUY=0; PROD_CHANGE=0
- `prospective_evidence_eligible=true`
- `purchase_action=false`
- `promotion_allowed=0`
- result: `PASS_PRE_RESULT_FREEZE`
- JSON/full artifact SHA-256:
  `1af00a1a7cc1742c4e93a5f816e4aaf90fb181ac45be9ee4d88ad09c4d5f6175`
- canonical formal-core SHA-256:
  `d07ec4347ccd30eb82c8511da9118784a124cbe90459fe8d2ce5f4c2773debaf`
- artifact ID `10617384166`
- artifact ZIP digest:
  `sha256:b40c34f99c42685ebbee330c90eeab0f45a829cfc18513d2517d9fc9da9da666`

Formal classification:
`FORMAL_AVAILABLE / NATURAL_SCHEDULE_DELAYED_BUT_PREDEADLINE_VALID / CORE_6R_12T / ARTIFACT_PRESENT / PURCHASE_FALSE`

Do not score 2026-09-21 until exact finalized outcomes/payouts are available. Do not reconstruct missing rows after results.

### Formal V4 performance/evaluator

PR #366 remains open Draft/mergeable at head
`902287846d1749a3202029539ede40bbe888b811`.

Already evaluated formal dates:
- 2026-09-18: investment 1,200 / return 1,100 / profit -100 / ROI 91.667%
- 2026-09-19: investment 1,200 / return 2,220 / profit +1,020 / ROI 185.0%
- combined evaluated corpus: **2 days / 12 races / 24 tickets**
- exact hits 4/12 = 33.33%
- head hits 7/12 = 58.33%
- ordered first+second prefix hits 5/12 = 41.67%
- third-only misses 1/12 = 8.33%
- investment 2,400 / return 3,320 / profit **+920**
- ROI **138.333%**
- no retuning; milestones remain 30/50/100.

With 2026-09-21, formal **available** corpus is now 3 days / 18 core races / 36 core tickets, but the **evaluated** corpus remains 2 days / 12 races / 24 tickets until today's results finalize.

### Other open tracks

- PR #363 Storage: open Draft/mergeable, head `362d57d10bd53e9893aef04611f1d1308316b68c`.
  `ZERO_CONSUMER_NOT_REACHED`; active writer/readers remain; no delete/migration/VACUUM.
- PR #362 Trio: open Draft/mergeable, head `b19be407123e8ed8984c49773b7fa1f745f90c5e`; keep separate from trifecta.
- Local horse PR #365: open Draft/mergeable, head `b48e3df1cac7ac3f5959980034a0160f57663b6f`;
  `TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`.
- TOTO PR #163: open Draft/mergeable, head `6b9a7b74df73e984a5888e9ad4ee36b4bb754c7a`.
  2026-09-21 09:00 natural Cron: Round1656 `too-early`, Forward A/B 0/0, purchase=false, normal SKIP.
  Existing TOTO Railway staged patch `0a9f5f5f-e41d-42a9-beae-ead87d7a02f2` must not be accepted/deployed without separate approval.

### Immediate next work

1. Observe the next natural **08:25 JST Railway fallback Cron**. Expected behavior:
   - valid primary artifact already visible => `NOOP_VALID_PRIMARY`;
   - otherwise exactly one workflow dispatch attempt.
2. Verify no duplicate dispatch and that the fallback service exits cleanly.
3. When 2026-09-21 results are finalized, verify exact outcomes/payouts from authoritative sources, then run PR #366 offline evaluator and append evidence; no retune from the small sample.
4. Continue read-only Storage zero-consumer evidence; do not delete shared/historical data.
5. Keep TOTO PR #163 Draft until a natural eligible delivery-window run provides evidence or separate deploy approval is given.

### Safety

- fail closed
- purchase remains false
- no manual same-day V4 rescue after missed timing
- no result-after Forward reconstruction
- do not loosen model/odds thresholds for volume/cost/profit
- no Production DB destructive action without explicit approval
- do not expose GitHub/Railway secret values
- historical / BASELINE / formal V4 / Production evidence remain separate


更新日時: 2026-09-15 23:24 JST

再開時はGitHub main / open PR / Railway Productionを必ず再取得し、この文書のSHA・件数を固定値とみなさないでください。

## Current source of truth

- Boat main: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- Railway project: `boat-v2-postgres`
- PostgreSQL service: `postgres-recovery`
- Volume: 20GB
- Safety: fail-closed / `purchase_action=false`
- Production mutationは明示承認制

## V4

本命アーキテクチャ:
`朝の構造評価/freeze -> 直前の展示・ST・天候・完全オッズ等で全再検証 -> 条件合格時だけ将来自動購入+LINE`

Stage1:
- 6 races / 12 TOP2 exact-order trifecta tickets
- Course 0.50
- Opponent Pressure 1.0 first-place only
- Motor2 beta 0.06, weights 1.0/0.6/0.3
- no Stage1 EV/odds gate
- `purchase_action=false`

Stage2:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- 0..7m complete120 market support
- research-only timing; future LINE/manual purchase timingには流用しない

9/15 formal V4:
- `UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`
- natural run `34917166205`
- 08:16予定 -> 10:25:18 JST開始
- 6 races / 12 ticketsは計算したがearliest deadline 09:36後
- fail-closed、artifactなし、backfill禁止

Draft PR #364:
- V4 capture resilience preregistration
- head `52c081871d38b10b5709eb5a7aa2d2784cb1d7c7`
- fallback scheduler未有効化 / 未merge

## Motor2 cleanup

完了済み:
- fresh Manual backup 2026-09-15 08:27 JST
- 44,203 redundant rows削除
- SHA256 `8d178d854d7b6bfb6a5c6ffdd183e1977f8c6258bd3658c9b0f75fbbf91f203f`
- run `34909832046` SUCCESS_COMMITTED
- protected/ambiguous=0
- evaluator/output diff=0
- post rows=137,030
- `VACUUM FULL`なし
- `MOTOR2_FINAL_SNAPSHOT_MODE=latest_per_race`有効
- one-time cleanup再実行禁止

## Storage / archive

Draft PR #363:
- `Research: preregister V4 storage ownership migration`
- head `7f5198082e0c3362d701906c1eeb9aea382fc0e9`
- latest listed CI/read-only workflows SUCCESS
- Production mutationなし

Latest retention measurement:
- base odds `v2_odds_trifecta`: 7,981,493 rows / relation 1,844,002,816 bytes
- 30d ref: hot 545,940 / cold 7,435,553
- realtime odds relation 536,854,528 bytes
- final_ab 30d: hot 498,208 / cold 557,812
- learning_all 30d: hot 445,565 / cold 22,125

30dはcutoff承認ではなく容量比較のみ。old rows DELETEはBLOCK。

July verified archive 588,156 base-odds rowsでonline/archive exact-output PASS済み:
- probability calibration
- N02 walk-forward / rolling / time-split
- N01/N02 diagnostics
- candidate-filter historical
- Motor2 base-feature
- V24 Motor2 historical
- Feature Lab
- motor/boat A/B
- final_ab analysis

Permanent archiveは未作成。current-day Production consumersはonline保持。`learning_all`はold FINAL previous-odds/drift/steam依存があるためblind stop/delete禁止。

Railway Hobbyは5GB/volume上限。20GB volumeはdownsize不可なので、Hobby移行はfresh <=5GB logical migration + restore-size/headroom proofが必要。

## Old-system retirement

Issue #360が削除gate。legacy/shared dependenciesがゼロになるまで広い削除はしない。

旧daily/monthly LINE reportはDRY_RUN=1済み。

監査用no-Cron serviceやmaintenance serviceは、dependency proof + explicit approvalなしに削除しない。監査目的でservice redeployしない。

## TOTO

- main `74fe4cdf470f553883da88b6e19528ec82e9b079`
- PR #161 merge済み
- `toto-ai-core` deployment `b9475314-be87-4f3c-b496-1ac4cca3ba64` SUCCESS
- natural Cron 9/15 09:04 / 21:04 JSTともRound1654 pairing PASS
- A/B each 5 matches + 5 live votes
- effective deadline 2026-09-19 17:50 JST
- `delivery_window=too-early`
- Forward A/B=0/0
- `purchase_action=false`
- manual rerun/retune禁止
- unrelated `diagnostic-round-1654-reader` removalは自動適用しない

## Local horse

`TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`

権利明確化までbulk ingest / persistent training / commercial use / external inquiry sendなし。

## Immediate next work

1. 9/15 V4 unavailableを固定し、後付け再構築しない。
2. PR #364 fallback設計をreview。Production scheduler変更なら承認を取る。
3. PR #363で残るhistorical/manual consumerのArchive対応またはretirement proofを続ける。
4. Permanent archive先決定前にold rowsを削除しない。
5. fresh logical restoreサイズでHobby 5GB readinessを証明する。
6. Issue #360のzero-consumer gateを継続する。
7. TOTO Round1654は自然Cronだけ監視する。

## Safety boundary

明示承認なしで変更しない:
- Production v24/FINAL
- coefficients / thresholds / BUY/WATCH/SKIP
- LINE actual send
- Railway Production config/Cron/Variables/services/volume
- Production DB writes/deletes/schema/VACUUM
- automatic purchase

必要データを容量節約だけで削除しない。historical / BASELINE / V4 Forward / Production evidenceを混ぜない。
