# boat-ai-v2 Project Handoff

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

### PR #367 multi-source provenance hardening

Current head:
`14f4f4abfb5ffaa3fbb809aa97664cdb5a5cfd86`

State:
- Draft / mergeable
- 5/5 CI SUCCESS
- research-only / offline / no Production wiring

Fresh official-surface review showed the earlier single-source snapshot shape was insufficient for a legitimate multi-venue PASS:
- BOAT RACE same-day index is a venue/day overview;
- race-specific surfaces are separate `hd/jcd/rno` resources;
- one top-level URL/digest must not be reused as provenance for six race-scoped positive assertions across multiple venues.

The preregistered snapshot is now multi-source:
- non-empty `evidence_sources[]`;
- each preserved official source has unique `evidence_id`, pre-freeze `observed_at`, official URL, raw-content SHA-256 and optional displayed `source_updated_at`;
- each selected core race references one `evidence_id`;
- PASS requires race-scoped `active` evidence for every selected core race;
- race-scoped positive evidence cannot be reused for another selected core race;
- venue-wide unavailable evidence may be shared only for selected races at the same venue;
- venue-wide unavailable + active contradiction at the same venue fails closed;
- venue ID is restricted to 01..24.

Important limitation remains explicit:
the pure guard validates supplied provenance structure but does not prove that normalized status/scope follows from raw bytes. A future acquisition/parser layer must bind preserved payload -> digest -> parsed status/scope. Mere page existence or a scheduled deadline is not sufficient race-level active evidence.

No candidate replacement, no reranking, no result/payout read, `purchase_action=false`.

### Other current state

Unless superseded above, the 13:21 override remains current:
- Boat main `8867b77569d836b6c02a075fa6444550b1a46a6c`;
- PR #366 strict replay/evaluator head `95d7af3efd79ead86bfdf4f708ba3065b283d6f9`, 5/5 CI SUCCESS;
- Sep18/Sep19 strict replay reproduced +920 JPY / ROI 138.333%;
- Sep21 remains post-result unevaluable and unscored;
- Storage zero-consumer gate remains not reached;
- Railway Production behavior/config unchanged;
- no Production DB/model/threshold/candidate/purchase mutation.

### Next natural checks

1. 2026-09-21 19:30 JST: final Sep21 official-state confirmation; no formal scoring unless all exact six same-date outcomes+payouts exist.
2. 2026-09-22 08:40 JST: natural 08:25 fallback Cron audit.
3. Continue natural-only Storage evidence; do not force-run Production jobs.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 13:21 JST

This section supersedes the 13:05 JST override below where they differ. Re-fetch GitHub/Railway before acting.

### Fresh Source of Truth re-fetch

- Boat `main`: `8867b77569d836b6c02a075fa6444550b1a46a6c`
- Railway Production environment: staged changes `none`
- V4 fallback service: `candidate-discovery-v4-fallback-dispatcher`
  - Cron `25 23 * * *` UTC = 08:25 JST
  - latest deployment `7c0b590e-a121-42d2-9f88-543848af386f`: SUCCESS
  - no volume
- No Production behavior/config/model/DB/purchase mutation was made in this work.

### PR #367 — pre-freeze availability guard preregistration

Current head:
`3afde0ef65a0601c684b334800ada0332b7ee57f`

State:
- Draft / mergeable
- 5/5 CI SUCCESS
- research-only / offline / no Production wiring

The 13:05 invariants remain authoritative: exact 6 core races, exact identity/rank/order checks, source-content SHA-256 provenance, race/venue evidence scope, venue-unavailable may BLOCK, venue-active cannot by itself PASS a race, no replacement/rerank/result read, `purchase_action=false`.

### PR #366 — strict post-result reproducibility hardening

Current head:
`95d7af3efd79ead86bfdf4f708ba3065b283d6f9`

State:
- Draft / mergeable
- 5/5 CI SUCCESS
- base branch current main
- no Production I/O

New strict evaluator guarantees:
- CLI requires expected immutable artifact JSON SHA-256 and verifies raw bytes before parsing;
- malformed/mismatched artifact SHA fails closed;
- outcomes must match the exact six frozen formal-core race IDs;
- extra outcome rows are rejected instead of ignored;
- missing/duplicate/malformed outcomes fail closed;
- explicit non-final status such as cancelled/postponed fails closed;
- legacy rows remain excluded from formal metrics.

Retained formal Actions artifacts were re-downloaded read-only and verified before replay:
- 2026-09-18 artifact `10527500527`, JSON SHA `b195b214d8761f4efdf0c37345434ac1e96bff93815c9ecd1b00f9c87aec1a3a`
- 2026-09-19 artifact `10574052434`, JSON SHA `f2a558d0631ac830f3ffb96440b801a17fa91c98639cae8ca186585c30e46bc2`

Strict replay reproduced the committed formal metrics exactly:
- Sep18: investment 1,200 / return 1,100 / profit -100 / ROI 91.667%
- Sep19: investment 1,200 / return 2,220 / profit +1,020 / ROI 185.000%
- combined: 2 days / 12 races / 24 tickets / investment 2,400 / return 3,320 / profit +920 / ROI 138.333%

Evidence:
`research/evidence/v4_formal_repro_check_20260921.json`

This strengthens evidence identity only. Sep21 remains unscored:
`CAPTURE_CONTRACT_VALID / RACE_UNIVERSE_AVAILABILITY_GAP / POST_RESULT_UNEVALUABLE / NO_5R_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

The 13:05 provenance caveat also remains: the historical 08:25 official-page observation was not preserved as immutable raw bytes, so URL-only replay is not cryptographic proof of that exact historical page state.

### PR #363 — Storage

Fresh GitHub refetch currently reports head:
`c3a87df234b06f220ab7128d129dbc32f0354e84`

This supersedes the SHA written in the 13:05 override for current-state purposes.

State:
- Draft / mergeable
- 21 listed workflows SUCCESS
- 1 read-only probability-calibration archive-consumer workflow in progress at this audit
- zero-consumer gate remains NOT reached
- same-day writer -> V4 reader proof remains active
- no DELETE / migration / VACUUM

Do not interpret an in-progress read-only CI job as a Storage gate change.

### Next natural checks

1. 2026-09-21 19:30 JST: re-confirm final Sep21 official status; do not score Sep21 unless all exact six same-date finalized outcomes+payouts exist.
2. 2026-09-22 08:40 JST: verify the natural 08:25 fallback Cron.
3. Let normal night/nightly Production schedules provide natural candidate-shadow evidence; do not force-run Production jobs for audit.
4. Keep PR #367 research-only until any Production-effect availability/candidate-universe change receives explicit approval.

### Safety

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 13:05 JST

This section supersedes the 12:59 JST override below where they differ. Re-fetch GitHub/Railway before acting.

### PR #367 hardening completed

Draft PR #367 `Research: preregister V4 pre-freeze availability guard` remains research-only / no Production wiring.

Current head:
`3afde0ef65a0601c684b334800ada0332b7ee57f`

Current state:
- Draft / mergeable
- 5/5 CI SUCCESS
- branch is based directly on current main `8867b77569d836b6c02a075fa6444550b1a46a6c`

New fail-closed invariants:
- exactly six formal core races;
- daily ranks exactly 1..6;
- exact core orders 1 and 2 on every core race;
- race ID target date / venue / race-number identity must match;
- official snapshot carries lowercase 64-hex `source_content_sha256`;
- each availability row carries evidence scope `race` or `venue`;
- venue-level `cancelled_postponed` may block a selected race;
- venue-level `active` is insufficient to PASS an individual race;
- unknown/missing/late/mismatched status or scope fails closed;
- no candidate replacement, no reranking, no result/payout read, `purchase_action=false`.

### Mutable official-source provenance limitation

The BOAT RACE same-day race-list URL is mutable during the day. The historical 08:25 displayed update time for Sep21 Toda cancellation was observed and recorded before the 10:03 formal freeze, but the exact 08:25 raw response bytes were not preserved with a content digest.

Therefore:
- current post-result fact remains: Toda was cancelled/postponed;
- the pre-freeze 08:25 observation remains useful historical evidence;
- that exact historical page state is not cryptographically reproducible from URL alone.

PR #366 now records this evidence-strength limitation. Any future Production-effect availability guard must preserve the exact observed official payload (or equivalent immutable raw representation) plus deterministic SHA-256 before parsed status can qualify as evidence.

PR #366 current head:
`714e96271a50b785fd2b4caeb6f0c27a4f413eed`
- Draft / mergeable
- 5/5 CI SUCCESS
- Sep21 remains unscored and post-result unevaluable under the six-race contract.

### Storage

PR #363 current head:
`562e4ac577a3ca9ba7e5e2c5367fd8e10deb3082`
- Draft / mergeable
- zero-consumer gate remains NOT reached
- same-day writer -> V4 reader evidence remains active
- no DELETE / migration / VACUUM
- at 13:05 JST one archive-consumer read-only workflow was rerunning; do not treat temporary in-progress status as a gate change.

### Source of Truth / safety

- Boat main remains `8867b77569d836b6c02a075fa6444550b1a46a6c`.
- Railway Production behavior unchanged.
- fallback service unchanged.
- no Production DB/Railway/model/threshold/candidate/purchase mutation was made.
- `PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING`

### Next natural checks

1. 2026-09-21 19:30 JST: re-confirm final official Sep21 status; do not score Sep21 unless all exact six same-date outcomes+payouts exist.
2. 2026-09-22 08:40 JST: verify natural 08:25 fallback Cron behavior.
3. Continue candidate-shadow zero-consumer evidence from natural windows only; do not force-run Production jobs.


## LATEST OVERRIDE — 2026-09-21 12:59 JST

This section supersedes the 11:06 JST override below where they differ. Re-fetch GitHub/Railway before acting.

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


### New V4 race-universe finding

The 2026-09-21 formal artifact remains immutable and capture-contract-valid:
- run `35549611949`
- generated `2026-09-21T10:03:12.277823+09:00`
- core `6R / 12T`
- `purchase_action=false`

However, frozen core race `20260921_02_08` (Toda 8R) was already on a venue officially marked cancelled/postponed **before** the formal freeze. BOAT RACE official today's-race page showed Toda `中止順延` at its 08:25 JST update.

Current main generator `.github/scripts/candidate_discovery_v4_main_feed_pg.py`:
- loads target-date rows from `v2_races`;
- requires complete six-lane entries and a deadline;
- has no pre-result cancelled/postponed race/venue availability filter;
- does not have a compatible pre-result status field in `v2_races`.

Therefore Sep21 classification is refined to:
`CAPTURE_CONTRACT_VALID / PRE_FREEZE_OFFICIAL_CANCELLATION_OBSERVABLE / RACE_UNIVERSE_AVAILABILITY_GAP / POST_RESULT_UNEVALUABLE / NO_REGENERATION / NO_RETUNE`

Evidence is Draft-only in PR #366:
- `research/evidence/v4_pre_freeze_race_availability_gap_20260921.json`
- `research/evidence/v4_formal_eval_blocker_20260921.json`
- updated post-result evaluation contract

Do not implement a Production availability/candidate-universe exclusion without explicit approval. Future work may preregister a timing-safe official same-day race/venue availability source, but Production candidate logic remains unchanged now.

### Storage gate hardening

PR #363 fresh 2026-09-21 evidence:
- morning natural Production window invoked candidate-shadow collector: `candidate_rows=0 / saved_rows=0`;
- day natural Production window invoked collector: `candidate_rows=7 / saved_rows=7`;
- formal V4 run then read `legacy_shadow_rows=7` and added 5 legacy races / 7 tickets;
- morning/day/night Railway configs still use `run_window_pipeline_pg.py` with candidate-shadow surfaces;
- nightly still uses `run_nightly_results_pg.py` with candidate-shadow evaluator/report surfaces;
- no-Cron `test-beforeinfo-extra` still directly runs the collector.

The pure runtime inventory contract now blocks zero-consumer on **reader or writer** capabilities, including the Railway nightly reader and GitHub V4 reader. Machine-readable evidence:
`research/evidence/candidate_shadow_zero_consumer_gate_20260921.json`

Current gate:
`ZERO_CONSUMER_NOT_REACHED / SAME_DAY_WRITER_TO_READER_PROVEN / ACTIVE_WRITER_SURFACES / ACTIVE_READER_SURFACES / NO_DELETE / NO_MIGRATION / NO_VACUUM`

Fresh PostgreSQL disk observation:
- current ~`4.593 GB`
- last 24h observed range ~`4.561 -> 4.593 GB`
- last 7d observed range ~`4.136 -> 4.591 GB`

This reinforces that current-footprint direct Hobby migration is not approved. Fresh retained-set restore + measured growth/headroom remain required; do not use these observations to justify capacity-driven deletion.

### Next natural checks

1. 2026-09-21 19:30 JST: re-confirm Toda final official status and keep Sep21 evaluation blocked unless all six exact same-date outcomes+payouts exist.
2. 2026-09-22 08:40 JST: verify natural 08:25 fallback Cron behavior.
3. Continue candidate-shadow zero-consumer evidence. The night and nightly windows are future natural evidence, not a reason for manual execution.
4. Keep Production/model/threshold/candidate logic unchanged without explicit approval.

### Safety unchanged

`PURCHASE_FALSE / NO_RETUNE / NO_RESULT_AFTER_RECONSTRUCTION / NO_EVIDENCE_MIXING / NO_PRODUCTION_MUTATION / NO_SECRET_OUTPUT`


## LATEST OVERRIDE — 2026-09-21 11:06 JST

This section supersedes the 10:40 JST override below where they differ. Re-fetch GitHub/Railway before acting.

### Re-audit confirmed

- Boat `main` remains `8867b77569d836b6c02a075fa6444550b1a46a6c`.
- PR #364 remains merged.
- Railway Production fallback `candidate-discovery-v4-fallback-dispatcher` remains active on `main`, Cron `25 23 * * *` UTC (=08:25 JST), restart `NEVER`, latest deployment `7c0b590e-a121-42d2-9f88-543848af386f` SUCCESS, staged changes none.
- Initial deployment log remains `NOOP_VALID_PRIMARY target_date=2026-09-21 primary_run_id=35549611949`; no workflow_dispatch run was created.
- PR #363 Storage remains Draft/mergeable. Fresh 2026-09-21 read-only evidence: natural `cron-window-day` wrote 7 candidate-shadow rows (S03=7), and formal V4 later read `legacy_shadow_rows=7`; `ZERO_CONSUMER_NOT_REACHED` remains in force.
- PR #366 remains Draft/mergeable and now contains a frozen 2026-09-21 post-result evaluation manifest plus explicit cancellation fail-closed evidence/policy.

### 2026-09-21 post-result evaluation blocker

The immutable formal V4 artifact remains valid pre-result:
- run `35549611949`
- formal core 6 races / 12 tickets
- full SHA `1af00a1a7cc1742c4e93a5f816e4aaf90fb181ac45be9ee4d88ad09c4d5f6175`
- canonical core SHA `d07ec4347ccd30eb82c8511da9118784a124cbe90459fe8d2ce5f4c2773debaf`

However, one frozen core race is `20260921_02_08` (Toda 8R, frozen deadline 14:16 JST). BOAT RACE official same-day pages later marked Toda as cancelled/postponed on 2026-09-21.

Current evaluation classification:
`FORMAL_AVAILABLE / POST_RESULT_UNEVALUABLE_CORE_RACE_CANCELLED / NO_DENOMINATOR_SHRINK / NO_SYNTHETIC_ZERO / NO_LATER_DATE_SUBSTITUTION / NO_REGENERATION / NO_RETUNE`

Do not score only the remaining five races. Do not invent a zero-yen payout/loss. Do not substitute the postponed race's later-date result back onto 2026-09-21. Under the frozen PR #366 contract, a missing exact same-date finalized outcome/payout blocks the full-day formal evaluation.

### Immediate next work

1. Keep the 2026-09-21 artifact immutable and unscored unless all six exact same-date final outcomes/payouts exist from authoritative sources.
2. Observe the next natural 08:25 JST Railway fallback Cron; valid primary => NOOP, otherwise exactly one workflow_dispatch attempt; duplicate dispatch prohibited.
3. Continue Storage zero-consumer evidence only; no delete/migration/VACUUM.
4. Keep model/coefficients/thresholds unchanged; no retuning from the small formal corpus.

### Safety unchanged

- fail closed
- `purchase_action=false`
- no result-after candidate reconstruction
- no Production DB destructive action without explicit approval
- do not expose secret values
- historical / BASELINE / formal V4 / Production evidence remain separate


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


更新: 2026-09-15 23:24 JST

この文書はトーク上限・担当交代時のSource of Truthです。再開時は、ここに書かれたSHA・件数・Railway状態を固定値とみなさず、必ずGitHub `main` / open PR / Railway Productionを再取得してから作業してください。

## 再開時の最初の指示

> `kenshoushouri-cloud/boat-ai-v2` の `docs/PROJECT_HANDOFF.md` と `docs/CURRENT_STATE.md` を最初に読み、GitHub main / open Draft PR / CI / Railway Production health をread-onlyで再確認してから続行する。GitHub mainをコードのSource of Truth、Railway PostgreSQLをProduction dataのSource of Truthとする。安全なread-only監査、research、Draft PR、CI、docs更新は継続可。Productionへ影響する変更は明示承認まで実施しない。

## Source of Truth / approvals

- Boat repository: `kenshoushouri-cloud/boat-ai-v2`
- Current main at this update: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- TOTO repository: `kenshoushouri-cloud/toto-ai-v1`
- TOTO current main: `74fe4cdf470f553883da88b6e19528ec82e9b079`
- Boat Railway project: `boat-v2-postgres`
- Production PostgreSQL service: `postgres-recovery`
- Production volume: `postgres-volume`, 20GB, mount `/var/lib/postgresql/data`
- Safety default: fail-closed / `purchase_action=false`

明示承認が必要:
- Production-effect PR merge
- Railway Production Variables / Cron / service / volume / migration変更
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Production model / coefficient / threshold / candidate logic変更
- LINE actual-send behavior変更
- Production Forward persistence新規変更
- automatic purchase
- paid data contract
- external inquiry send

ユーザーは安全なread-only監査、研究、Draft PR、CI、docs/handoff更新を継続してよいと承認済み。必要データは容量節約だけを理由に捨てない。

## 新システム本命アーキテクチャ

本命は以下:

`朝の構造評価 / candidate freeze -> 直前の展示・ST・天候・完全オッズ等で全再検証 -> 条件合格時だけ将来自動購入 + LINE`

重要:
- 朝はPurchase確定ではなくCandidate Discovery。
- 旧morning/day/nightの3回PREは、そのまま新システムへ継承しない。
- 直前判定で朝候補を全て却下して0件でもよい。
- Challengerとして `直前のみ全対象を評価 -> BUY/SKIP` をShadow比較する。
- Primary vs Challengerはprospective 30/50/100 casesで比較し、結果後に都合のよい方式を選ばない。
- automatic purchaseは別途明示承認とfail-closed safety validation完了まで有効化しない。

旧Production FINALはT-30..0分を15分刻みで回し、通常は約15〜30分前にdecision/LINEへ入る。したがって現在のStage2 `0..7m` はlate-market research専用で、将来の人間向けLINE/購入時刻へそのまま流用しない。

## Candidate Discovery V4

固定Stage1 research contract:
- 6 races/day
- TOP2 exact-order trifecta = 12 core tickets
- Course coefficient `0.50`
- Opponent Pressure `1.0`, first-place only
- Motor2 beta `0.06`, weights `1.0 / 0.6 / 0.3`
- 4 structural metrics equal-weight rank
- Stage1 EV/odds gateなし
- legacy S01-S05 carryoverは現在比較用に残る
- `purchase_action=false`

Stage2 frozen hypothesis:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- complete 120-ticket market snapshot, deadline 0..7m
- core_order1のみ市場TOP2 support注記
- Stage1を削除・rerankしない
- milestone 30/50/100 supported cases
- post-outcome retuning禁止

Trio副研究はDraft PR #362で別track。trifectaとpoolしない。

### 9/13 BASELINE

これはV4ではない。immutable baseline artifactをexact評価済み:
- core 6 races / 12 tickets / 2 hits / +220 JPY / ROI 118.333%
- legacy 2 races / 2 tickets / -200 JPY
- total +20 JPY / ROI 101.429%
- source JSON SHA256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

1日だけのBASELINE結果をV4性能やthreshold調整へ混ぜない。

### 9/15 formal V4 incident

2026-09-15 formal V4 evidenceは:

`UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`

確定事実:
- planned primary: 08:16 JST
- natural scheduled run `34917166205`
- started 10:25:18 JST, 約2h09m遅延
- read-only feedは6 core races / 12 ticketsを計算
- earliest frozen-feed deadlineは09:36 JST
- deadline後だったためwrapperが正しくfail-closed
- artifact uploadなし
- backfill / manual reconstruction / result-after relabelingなし

これはmodel品質失敗ではなくcapture orchestration/timing failure。

Draft PR #364 `Research: preregister V4 capture resilience after 9/15 schedule delay`:
- open / Draft / mergeable
- head `52c081871d38b10b5709eb5a7aa2d2784cb1d7c7`
- primary 08:16 GitHub schedule維持
- future-only independent fallbackを08:25頃に検討
- duplicate valid capture時は最初のvalid post-08:15 artifactだけformal
- Railway Cron/serviceをfallbackとして有効化する場合は別途明示承認が必要
- 自動merge禁止

## Motor2 cleanup — 完了

ユーザー明示承認済みの限定cleanupは完了済み。

Fresh manual backup:
- 2026-09-15 08:27 JST
- Railway UI表示は約4.28GB referenced
- restore可能なfresh safety pointとして確認済み

Cleanup:
- exact candidate 44,203 rows
- 2,456 races
- 908 snapshot keys
- range 2026-08-20..2026-09-12
- SHA256 `8d178d854d7b6bfb6a5c6ffdd183e1977f8c6258bd3658c9b0f75fbbf91f203f`
- run `34909832046`: `SUCCESS_COMMITTED`
- protected intersection=0 / ambiguous latest=0
- Performance/PRE/FINAL/latest-PRE-health outputs diff=0
- post rows=137,030
- conservative final/final removable=0 after cleanup
- `VACUUM FULL`未実施

Production `MOTOR2_FINAL_SNAPSHOT_MODE=latest_per_race` は既に自然Cronで有効。再設定不要。Motor2 one-time cleanupを再実行しない。

## Storage / Archive / October cost plan

Draft PR #363 `Research: preregister V4 storage ownership migration`:
- open / Draft / mergeable
- branch `research/v4-storage-ownership-migration-20260915`
- current head at this update `7f5198082e0c3362d701906c1eeb9aea382fc0e9`
- latest listed CI / read-only workflows are all SUCCESS
- Production mutationなし

Latest read-only retention audit (2026-09-15):
- `v2_odds_trifecta`: 7,981,493 rows / logical payload 830,075,423 bytes / relation 1,844,002,816 bytes
- 30d reference: hot 545,940 rows / 56,777,757 bytes; cold 7,435,553 / 773,297,666
- `v2_realtime_odds_snapshots` relation: 536,854,528 bytes
- `final_ab`: 1,056,020 rows; 30d hot 498,208 / 94,924,296 bytes; cold 557,812 / 106,331,968
- `learning_all`: 467,690 rows; 30d hot 445,565 / 84,861,496; cold 22,125 / 4,248,000
- 30dは承認済みretention cutoffではない。容量比較用referenceのみ。
- DELETE直後のphysical volume reclaim値ではない。

Archive pilot / exact-output equivalence:
- July `v2_odds_trifecta` verified archive: 588,156 rows
- online/archive exact-output PASS:
  - Historical readiness
  - Feature Lab
  - `compare_motor_boat_ab_pg.py`
  - `analyze_final_ab_features_pg.py`
  - probability calibration: ready 4,889 / ticket rows 586,680
  - N02 walk-forward: 13 bets
  - N02 rolling: 13 bets
  - N02 time-split: 13 bets
  - N01/N02 diagnostics: N01 25 bets / N02 13 bets
  - candidate-filter historical: ready 4,889 / rule selections 586
  - Motor2 base-feature: processed 4,853 / candidate rows 75
  - V24 Motor2 historical: processed 4,853
- all are Production read-only, ephemeral archive, permanent uploadなし
- current PR also has realtime archive export/entry footprint/read-through validation; latest corresponding CIはSUCCESS

重要なblocker:
- Permanent archive/Bucketはまだ作成していない。
- old rowsのDELETEはまだBLOCK。
- `run_odds_window_pg.py` / daily prepare等のcurrent-day Production pathはKEEP ONLINE。
- manual OOS / historical consumersはarchive read-through対応またはretirement proofが必要。
- `learning_all`はold FINALのprevious-odds/drift/steamへ間接依存するため、blind stop/delete禁止。
- `v2_odds_trifecta`は「無駄」ではなくresearch/backtest asset。archive-first。

Railway Hobbyはper-volume 5GB上限。現在の20GB volumeはin-place downsize不可なので、Pro→Hobbyは**fresh <=5GB compatible volume/serviceへのlogical migration**が前提。必要データを削って5GBへ押し込まない。fresh restore後の実サイズ/headroomで判断する。

Cost target:
- October: ChatGPT Go + Railway Hobby/low usageでcombined <= USD20/monthを目標
- Oct 1–2: read-only usage/storage/dependency audit
- Oct 3 billing boundary: independence/data-preservation/migration safetyが通ればRailway Pro→Hobbyを検討
- Oct 14までにChatGPT Plus→Goを検討
- コスト回収のためにprediction threshold/stake/candidate countを変えない

## Old-system retirement

Issue #360 `Migration: retire old selector data after V4 independence` がgate。

旧システム専用データを広く削除する条件:
1. V4 feedがlegacy shadowを読まない
2. Stage2 market ownershipが新システム側で保全
3. prospective evidence蓄積
4. old selector/report停止が新システムへ無影響
5. fresh dependency scanでzero consumers
6. exact inventory rows/date/size + digest
7. recovery proof
8. shared tables除外
9. explicit approval後にbounded delete/drop + verify

旧daily/monthly report LINE actual-sendは既にDRY_RUN=1へ変更済み。

Railway no-Cron audit/maintenance servicesはcleanup候補だが、依存確認と明示承認なしに削除しない。特に監査のためにaudit serviceを再deployする方法は使わない。過去にread-only監査のつもりでstaged Function作成やaudit service redeployが発生したため、今後はProduction service mutationを伴わない経路だけ使う。

## TOTO handoff

Repository `kenshoushouri-cloud/toto-ai-v1`。

PR #161はユーザー明示承認でmerge済み:
- current main `74fe4cdf470f553883da88b6e19528ec82e9b079`
- Railway `toto-ai-core` deployment `b9475314-be87-4f3c-b496-1ac4cca3ba64`: SUCCESS
- Cron `0 */12 * * *`
- same-round A/B pairing / effective deadline=`min(A,B)` fail-closed

Round 1654 Production natural validation:
- 2026-09-15 09:04 JST: PASS
- 2026-09-15 21:04 JST: PASS
- A=5 matches / 5 live votes
- B=5 matches / 5 live votes
- target_round=1654
- effective deadline = 2026-09-19 17:50 JST
- delivery_window=`too-early`
- Forward A/B=0/0
- `TOTO_WEEKLY_PIPELINE=SKIP reason=delivery-window-too-early`
- `purchase_action=false`
- manual rerun / retuneなし

Round1653 frozen baseline:
- A 4/5
- B 1/5
- combined 5/10
- mini-toto ticket 0/2
- post-result retune禁止

Unrelated `diagnostic-round-1654-reader` staged removalは別Production action。自動適用しない。

## Local horse

Issue #353。

Current decision:
`TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`

権利が明確になるまで:
- NAR bulk ingestしない
- long-term storageしない
- persistent ML trainingしない
- commercialize/distributeしない
- external inquiryを勝手に送らない

ここは容量ではなく利用権がblocker。

## Immediate next work

1. 9/15 V4を正式unavailableのまま固定し、後付け再構築しない。
2. PR #364 fallback設計をreviewし、Production scheduler変更が必要ならユーザー承認を取る。
3. PR #363で残るhistorical/manual consumersをverified archive read-throughへ移すかobsolete retirementを証明する。
4. Permanent archive先を決める前にold rowsを削除しない。
5. archive + online hot-set + fresh logical restoreの実サイズでHobby 5GB readinessを証明する。
6. Issue #360の旧システムzero-consumer gateを継続する。
7. TOTO Round1654は自然Cronだけを監視し、締切前にmanual rerunしない。
8. V4 / TOTO / Storage evidenceを混ぜず、historical / BASELINE / V4 prospective / Productionを明確に分離する。

## 最後の安全ルール

- fail-closed
- `purchase_action=false`
- thresholdを候補数・料金回収・月利益目標のために緩めない
- 結果後にForwardを作り直さない
- historical / BASELINE / V4 Forward / Production evidenceを混ぜない
- 必要なraw/timing/reproducibility dataを容量節約だけで捨てない
- Production mutationは必ず明示承認範囲を確認する
