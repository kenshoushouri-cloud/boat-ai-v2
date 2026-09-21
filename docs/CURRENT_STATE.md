# boat-ai-v2 Current State

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
