# boat-ai-v2 Project Handoff

更新: 2026-09-14 19:45 JST

この文書は現在地点の短い引き継ぎです。再開時は必ず GitHub `main`、open PR、Railway Production を再取得し、この文書のSHA・件数を固定値だと仮定しないでください。

## 再開時の指示

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/PROJECT_HANDOFF.md` を最初に読み、現在の `main`、open PR、Railway Production read-only health を再確認してから続行してください。GitHub `main` をコードのSource of Truth、Railway PostgreSQLを本番データのSource of Truthとします。安全なread-only監査、研究、Draft PR、CI、文書整理は確認なしで継続可。Productionへ影響する変更は明示承認まで実施しません。

## Source of Truth / current snapshot

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Current main: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- PR #352 `Research: minimal V4 prospective freeze capture path`: **merged** 2026-09-14 06:29 JST
- PR #355 `Research: schedule daily V4 prospective freeze`: **merged** 2026-09-14 19:32 JST、main commit `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- PR #354: older 08:15 schedule proposal、**closed / not merged / superseded by #355**
- Draft PR #351 `Research: Candidate Discovery main feed (V1-V4)`: open / research-only / mergeable、head `110af472860bd00ae6d98835ea51b4c8d9d11825`
- Draft PR #357 `Research: exact-evaluate immutable 2026-09-13 BASELINE`: open / stacked research-only、head `a31ed3ff8c41d4860783ffac7d467926257a5d8b`
- Railway project: `boat-v2-postgres`
- Production PostgreSQL: `postgres-recovery`
- Railway status再確認時: 主要serviceはSUCCESS、環境STAGED patchなし
- 判断履歴: `docs/PROJECT_HISTORY.md`
- Railway監査ログ: Issue #42

GitHubは原則 `branch → Draft PR → CI → review → merge`。mainへ直接編集しません。

## 承認境界

明示承認が必要:
- Production反映を伴うPR merge
- Railway Production Variables / Cron / service / volume設定変更
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Productionモデル・係数・閾値・候補判定ロジック変更
- LINE実送信に関わる変更
- Production Forward persistenceの新規変更
- 自動購入
- 有料データ契約
- 外部問い合わせ送信

維持事項:
- fail-closed
- `purchase_action=false`
- Production v24/FINALを勝手に変更しない

## 最優先: Candidate Discovery / V4

### Architecture
Stage 1 V4は固定研究契約:
- 6 races/day × TOP2 exact-order trifecta
- Course coefficient `0.50`、missing lane neutral
- Opponent Pressure coefficient `1.0`、first-place only
- Motor2 beta `0.06`、position weights `1.0 / 0.6 / 0.3`
- 4 structural metrics equal-weight daily ranking
- Stage 1にEV gate / absolute odds gateなし
- S01-S05 legacy carryoverを比較用に維持
- `purchase_action=false`

Stage 2 frozen hypothesis:
- `MKT_LATE07_TOP2_SUPPORT_V1`
- deadline 0..7分前のtiming-safe市場TOP2 support
- Stage 1候補を削除・並べ替えしない
- milestone 30 / 50 / 100 supported cases
- post-outcome retuning禁止

### Candidate volume / purchase policy
ユーザー方針として、旧システムのように候補を絞りすぎて日常的に候補ゼロになる状態は避ける。

ただし、候補数を増やすためにBUY閾値を無理に緩めたり、毎日必ず12点を購入する設計にはしない。

研究上の役割分離:
- Stage 1の6 races / 12 ticketsは**候補フィード**であり購入ノルマではない。
- complete-data / eligible dayでは候補を順位付きで広めに維持し、候補生成自体を旧システム並みに極端に絞らない。
- source incomplete / timing guard failure時は従来どおりfail-closedを優先する。
- 実購入は将来の別レイヤーで可変点数にする。条件不十分なら0点も許容する。
- 「候補ゼロを避ける」ために結果を見てから閾値を下げる、追い買いする、日次利益を達成するまで買う、という設計は禁止。

利益目標はselectorの事後最適化条件ではなく運用評価目標として扱う:
- 基本評価目安: 月間 +30,000 JPY
- stretch目標: **月間 +50,000 JPY**
- 日次 +1,000 JPYなどの必達ルールは置かない。
- 利益だけでなく ROI、購入回数、的中率、最大ドローダウン、連敗、月間投資額を同時評価する。
- Forward証拠が十分に蓄積する前に賭け金や閾値を利益目標へ合わせて調整しない。
- 将来のS/A/B等級や100/200/300円の可変stakeは研究候補に留め、Production購入ルール化は別承認とする。

### 2026-09-13 immutable BASELINE freeze / exact evaluation
これは**V4ではなくV1/V2 main-feed baseline**。
- source run `34726186753`
- source artifact `10308110102`
- scheduled/evaluable 180/180
- baseline core 6 races / 12 tickets
- legacy 2 races / 2 tickets
- total 8 races / 14 tickets
- source ZIP SHA256 `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`
- source JSON SHA256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

2026-09-14にDraft PR #357でimmutable artifactを再生成せず、official result rowsのみを使ってexact評価完了:
- CI run `34808905754`: **SUCCESS**
- baseline_core: 6 races / 12 tickets / 2 hits / 投資1,200円 / 払戻1,420円 / **+220円 / ROI 118.333%**
- legacy: 2 races / 2 tickets / 0 hits / 投資200円 / 払戻0円 / **-200円 / ROI 0%**
- total: 8 races / 14 tickets / 2 hits / 投資1,400円 / 払戻1,420円 / **+20円 / ROI 101.429%**
- `v4_core=0`
- `MKT_LATE07_TOP2_SUPPORT_V1 cases=0`
- evaluation artifact `10333917048`
- evaluation artifact name `candidate-discovery-baseline-20260913-exact-eval-34808905754`
- evaluation ZIP SHA256 `c2420e48d633ada46d4bc02466b78deeb0d729ac33dc9d5907b8e6638689ad4b`
- DB write=0 / LINE=0 / `purchase_action=false` / Production change=0

この1日BASELINE結果だけを収益性証明や閾値・モデル調整根拠に使わない。source artifactは今後も再生成・差替え禁止。V4 Forwardや`MKT_LATE07_TOP2_SUPPORT_V1`証拠へ混ぜない。

### 2026-09-14 V4 Forward
PR #352はmainへ入ったため、workflow `.github/workflows/candidate-discovery-v4-prospective-freeze.yml` はdefault branch上で利用可能だったが、2026-09-14の正式なpre-result freezeは取得できていない。

したがって:
- **2026-09-14は正式V4 prospective Forward evidenceとして使用しない**
- 結果後の再構築は禁止
- diagnostic/backfillをprospective扱いしない
- milestoneへ加算しない

### Daily V4 prospective freeze — merged
PR #355は明示承認後にmainへmerge済み。

Default branchの現在契約:
- daily `08:16 JST` schedule (`16 23 * * *` UTC)
- schedule時target dateを`TZ=Asia/Tokyo date +%F`で明示解決
- manual `workflow_dispatch`をfallbackとして維持
- current-date / 08:15 source cutoff / complete universe / 6 races・12 tickets / earliest-feed-deadline guardを維持
- PostgreSQLはread-only
- DB write / LINE / BUY / Production selector変更なし
- `prospective_evidence_eligible=true`を満たさないrunは正式証拠へ数えない
- `purchase_action=false`

次のeligible scheduled runは2026-09-15 08:16 JST。成功時はrun ID / head SHA / artifact ID/name / artifact SHA256 / target date / scheduled/evaluable / core 6 races・12 tickets / legacy count / generated_at_jst / earliest deadline / `prospective_evidence_eligible=true` / `purchase_action=false`を固定する。

## V4 safety / evaluator

PR #351内の重要な安全修正:
- frozen evaluatorは`result_status=official`かつ`race_status=official`のみ採用
- payoutは正の整数のみ
- Forward stability metricsは`candidate_discovery_main_feed_v1`を`baseline_core`、`candidate_discovery_v4_main_feed_v1`を`v4_core`へ分離
- 9/13 baselineがV4 performanceへ混入しない

PR #351は大きなresearch packageなので、workflow availabilityだけを理由にmergeしない。

## Production / data safety

Railway `boat-v2-postgres`再確認時:
- environment staged changes: **なし**
- `postgres-recovery`: SUCCESS / 5GB volume
- `cron-nightly-results`: `30 14 * * *` UTC = 23:30 JST
- `cron-racer-course-stats`: 07:15 JST
- `cron-opponent-pressure-v2-live`: 07:00 JST / SUCCESS
- morning/day/night/FINAL等の主要service: SUCCESS
- legacy `cron-opponent-pressure-v2-runner`には古いFAILED deploymentがあるが、現行live natural Cronではないため触らない

容量原則:
- 予測精度を落として容量節約しない
- 地方競馬等の別競技データを競艇DBへ同居させない
- 大量DELETE/VACUUMは明示承認なしで行わない

## Racer Course / Opponent Pressure

研究上の固定係数:
- Course `0.50`
- Opponent Pressure `1.0`

Opponent Pressureは07:00 JST専用natural Cronでtiming-clean観測中。5/5到達しても自動Production昇格しない。

Course/Opponentの研究結果は有望でも、Production v24/FINALへの昇格は別承認事項。

## TOTO cross-project handoff

Repository: `kenshoushouri-cloud/toto-ai-v1`

重要:
- Production mainは`b6e9df0b758ad0e3f8d89dbed885f0d206e86298`
- Draft PR #161 `Fix: pair mini TOTO Forward by round across distinct deadlines` はopen / mergeable / head `b873c49e7a07735ccc1efb59c1d2380e91609d7a`
- #161はweekly selectorとcurrent-model LINE loaderの両方を、同一round A/B各5試合 + `min(sales_end_at)`のfail-closed共通締切へ修正済み
- モデル係数・confidence threshold・LINE copy・購入動作は変更なし
- Round 1654 safe validationはstacked Draft PR #162で実施
- #162 head `0e718e22bfca116b5146dddb4e1209149afbb5a1`
- validation run `34809289024`: SUCCESS
- full CI run `34809288926`: SUCCESS
- Production自然Cron実ログでRound 1654 mini A/B各5試合・live vote 5を確認
- 公式締切 A=`2026-09-19 17:50 JST`, B=`18:20 JST`
- frozen #161 semanticsではtarget round `1654`, effective deadline `17:50 JST`
- validation classは**`EVIDENCE_REPLAY_NOT_LIVE_DB_EXECUTION`**。Production DBにpublic TCP proxyが無いため、GitHub ActionsからPR branchをlive DBへ直接実行するためのProduction infra変更は行っていない
- DB/Forward write=0、LINE=0、`purchase_action=false`、Production config change=0
- **PR #161 Production mergeは明示承認まで行わない**

Railway `toto-ai-v1`:
- Postgres / `toto-ai-core` / `round1653-baseline-dryrun` healthy
- 誤作成service `diagnostic-round-1654-reader`がまだ存在
- そのserviceだけを削除するSTAGED change 1件が残る
- Applyには2FAが必要。自動Applyしない

TOTOの詳細handoffは同repoの`docs/PROJECT_HANDOFF.md`とDraft PR #160を確認する。

## 地方競馬 / 競輪

地方競馬:
- tracking Issue #353
- research branch `research/local-horse-adoption-gate-20260913`
- current decision: `TECHNICALLY_PROMISING / RIGHTS_BLOCKED / NO_DATA_INGEST_YET`
- NAR公式データは技術的には有望だが、商用利用・長期保存・自動取得・ML学習等の権利条件が十分明確になるまで大量取得・永続DB・学習を開始しない
- 外部問い合わせ文はdraftのみ。送信は明示承認が必要
- 初期研究候補は単勝・馬複、30/50/100/300/500 bet milestones、競艇DBと分離

競輪:
- 現在は研究終了/不採用寄り。地方競馬より優先しない。

## 次の安全な優先順位

1. 9/13 immutable BASELINE exact評価はBASELINE-onlyで固定し、1日結果から閾値調整しない。
2. 9/14 V4 prospective freezeは欠測扱い固定。後付け再構築しない。
3. 2026-09-15 08:16 JSTの初回daily V4 scheduled freezeをread-only確認し、正式artifact provenanceを固定する。
4. PR #351の研究条件を維持したまま、V4 / Stage2 Forward evidenceを30/50/100 milestoneまで蓄積し、post-outcome retuneしない。
5. 候補フィードは広めに維持する一方、12点全購入を前提にしない。月+50,000 JPYはstretch評価目標であり、BUY閾値を強制的に緩める理由にしない。
6. TOTO PR #161はRound 1654 evidence replayまで完了。Production mergeは別承認。
7. TOTO Railwayのaccidental diagnostic serviceはユーザーが2FAでその1件だけApplyした後、元の3service状態をread-only確認する。
8. 地方競馬は権利確認前にbulk ingestしない。

## Restart checklist

1. boat-ai-v2 current main SHAを再取得。
2. PR #351 / #357 / #356状態と、#355 merged / #354 closedを再確認。
3. GitHub ActionsでV4 prospective freezeの最新scheduled runを確認し、prospective provenanceを検証。
4. Railway `boat-v2-postgres` status / staged changes / Postgres healthをread-only確認。
5. `docs/PROJECT_HANDOFF.md`、`docs/CURRENT_STATE.md`、`docs/PROJECT_HISTORY.md`を読む。
6. TOTO repo PR #161 / #162 / #160 / Railway staged removalを確認。
7. Issue #353で地方競馬rights gateを確認。
8. historical / BASELINE Forward / V4 Forward / Production evidenceを混同しない。
9. 候補数目標・利益目標を、結果後の閾値最適化や強制購入の理由にしない。
