# boat-ai-v2 Current State

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
