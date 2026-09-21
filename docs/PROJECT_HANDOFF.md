# boat-ai-v2 Project Handoff

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
