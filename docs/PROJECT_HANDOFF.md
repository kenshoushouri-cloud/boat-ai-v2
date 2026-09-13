# boat-ai-v2 Project Handoff

更新: 2026-09-13 JST

この文書は次チャットが安全に再開するための**現在地だけ**を残します。数値・SHA・PR状態はcheckpointであり、再開時に必ずcurrent値を再取得してください。

## 再開時の最初の指示

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/CHATGPT_BOOTSTRAP.md` と `docs/PROJECT_HANDOFF.md` を読み、current `main`、open PR、PR #351 の最新head/Actions、Railway Productionのread-only healthを確認してから続行してください。GitHub `main`をProduction codeのSource of Truth、Railway PostgreSQLをProduction dataのSource of Truthとしてください。安全なread-only監査・研究・Draft PR・CI・文書整理は連続して進めてよいですが、Production変更は明示承認まで実施しないでください。

## Source of Truth / checkpoint

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Production code: GitHub `main`
- 2026-09-13 handoff時 main checkpoint: `8abbb0186852969129175848ee106118031f97e4`
- Production DB: Railway project `boat-v2-postgres` / service `postgres-recovery`
- Candidate Discovery primary research: Draft PR #351
- PR #351 branch: `research/candidate-discovery-v1-20260913`
- 2026-09-13 handoff直前 branch checkpoint: `97fa31281ffc091102abe576274b1a3a24f8b1d3`

mainやPR headは必ず再取得し、このcheckpointを固定値として扱わないでください。

## Production変更の承認境界

以下は明示承認が必要です。

- Production反映を伴うPR merge
- Railway Production Variables / Cron / service / volume等の変更
- Production DBのINSERT / UPDATE / DELETE / schema変更 / VACUUM
- モデル係数・閾値・Production候補/判定ロジック変更
- 実LINE送信に関わる変更
- Production Forward persistenceの新規変更
- 自動購入
- 有料データ契約・外部問い合わせ送信

安全なread-only監査、研究コード、Draft PR、CI、文書整理は確認なしで継続可です。`purchase_action=false` と fail-closed を維持してください。

## 現在の戦略

競艇が最優先です。新しい Candidate Discovery 系を将来の主候補システムとして育て、現行v24は当面benchmark/referenceとして残します。

重要方針:

- **候補表示と購入判定を分離する。**
- 候補を極端に減らすEV閾値・絶対オッズ帯を主ゲートにしない。
- 現行S01-S05候補は当面legacy/reference carryoverとして比較可能にする。
- 新システムが十分に実証されるまで、Production v24を消さない。
- 旧データ削除は新システム確立後に依存関係を分類してから検討する。実DELETE/VACUUMは別承認。

## Candidate Discovery PR #351

PR #351 `Research: Candidate Discovery main feed (V1-V4)` は研究専用です。Productionへは未反映です。

### Stage 1 — V4 structural main feed

現行研究契約:

- 1日 TOP6レース × TOP2 3連単候補を基本feedにする。
- Course coefficient `0.50`、欠損laneはneutral `z=0`。
- Opponent Pressure coefficient `1.0` は**1着確率だけ**へ適用。
- Motor2 beta `0.06`、着順weight `1.0 / 0.6 / 0.3`。
- V2由来の4 structural metricsを等重み順位化して日次TOP6を選ぶ。
- EV gateなし。
- 絶対オッズmin/max gateなし。
- `purchase_action=false`。

詳細:
- `docs/CANDIDATE_DISCOVERY_V4_CONTRACT_20260913.md`
- `docs/CANDIDATE_DISCOVERY_TWO_STAGE_ARCHITECTURE_20260913.md`

### Stage 2 — late Bao corroboration

- Stage-1候補を削除しない。
- timing-safeな完全120点市場snapshotと展示/Motor2を用いて支持タグを付ける。
- Bao不一致でもV4候補は残す。
- 既存Bao windowは early `20-30分前`、exhibition `8-15分前`、late `0-7分前`。

## 2026-09-13 公式Forward freeze

結果確定前に固定済みです。後から候補を再生成して評価しないでください。

- Actions run: `34726186753`
- Freeze time: 約08:44 JST
- scheduled / evaluable: 180 / 180
- V4 core: 6レース / 12 tickets
- legacy carryover: 2レース / 2 tickets
- total feed: **8レース / 14 tickets**
- Artifact ID: `10308110102`
- Artifact ZIP SHA-256: `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`
- frozen JSON SHA-256: `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`
- 詳細: `docs/CANDIDATE_DISCOVERY_FORWARD_20260913.md`

結果評価はこのexact Artifactを使います。

## バックテストで確定したこと

過去データによるbacktest / walk-forward / time-splitを実施しています。

- V1 broad single-ticket: 候補数は増えるがROI約66-71%。購入ロジックには不採用。
- V2 small formations: 2-3点で的中率は概ね16-24%へ上がるが、ROIは100%未満。
- V3 broad market-rank archetypes: 約8候補/日、ROI約63.7%。不採用。
- 3連単 / 2連単 / 3連複について、TOP1/2/3/5と20/35/50% coverageを100円/点で比較済み。
- 2連単・3連複は的中率/連敗耐性を改善するが、券種変更だけでは長期ROIを100%超へ押し上げない。
- 30日Smokeで約102%だった `A+B × 3連複 TOP1` は長期1,733レースでROI約83.01%、-29,440円まで低下。**採用しない。**
- 長期のpredeclared Tier×券種gridでは100%超セルなし。後付けでTier/点数を切り直さない。

公式K payout archiveから3連単・2連単・3連複の払戻を研究用にread-only取得できる経路は確立済みです。

## 市場/Bao corroborationの現在地

30日proxyでは、一般的な市場一致だけでは明確な利益改善を確認できませんでした。

既存Bao late window `0-7分前` に限定したproxyでは小標本ながら:

- 3連単 market TOP2 support: 34 races / ROI約107.94% / +270円
- 3連複 market TOP2 support: 47 races / ROI約109.15% / +430円

ただしサンプル・利益とも小さく、**Production昇格根拠ではありません**。

このため、結果を見て条件を動かさないProspective仮説を固定しています。

### `MKT_LATE07_TOP2_SUPPORT_V1`

- Prospective start: **2026-09-14 JST**
- window: 締切0-7分前を固定
- rule: structural候補を市場TOP2も支持しているか
- 候補feed自体は削除しない。購入判断用の独立タグ研究。
- 2026-09-13の既存結果をProspective実績へ後付け算入しない。
- 30 / 50 / 100 evaluated opportunitiesで再判定。
- 結果を見てTOP1/TOP3、時間窓、券種等を途中変更しない。

関連:
- `docs/CANDIDATE_DISCOVERY_MARKET_CORROBORATION_FORWARD_20260914.md`
- `docs/CANDIDATE_DISCOVERY_MARKET_FORWARD_EVAL_CONTRACT_20260913.md`
- `research/candidate_discovery_market_annotation_contract.py`
- `research/candidate_discovery_market_forward_metrics.py`

## 次にやること

1. **最初にPR #351の最新Actionsを再取得する。** 過去のDryrun failureだけを見て修正しない。
2. 最新branchには pure annotation contract / wiring / Forward metrics CI が追加されているため、その最新結果を確認する。
3. 9/14以降、`MKT_LATE07_TOP2_SUPPORT_V1` を固定条件のままProspective蓄積する。
4. 9/13 official freezeはexact Artifactでのみ結果評価する。
5. V4/Bao/marketのForward結果を30/50/100件で評価し、retuneせず継続/棄却を判断する。
6. 十分なForward証拠が得られてからProduction promotionを検討する。実promotionは別途明示承認が必要。

## CIについての注意

以前 `.github/scripts/candidate_discovery_v4_market_annotation_dryrun_pg.py` の初回CIが、docstring内の `payout` という説明語を静的guardが誤検知して本体実行前にfailureになったことがあります。これはDB mutationや結果リークではありません。

その後branchにはpure annotation contract / wiring / prospective Forward metricsが追加されています。**再開時は必ず最新headのActionsを見て、古いfailureを現在の未解決障害と決めつけないでください。**

## Railway / DB容量

容量余裕は大きくありませんが、予測価値を犠牲にした削除はしません。

- `v2_odds_trifecta` は大規模だが実データ/研究・backtest価値があり、単純削除対象ではない。
- Motor2 older retention候補の実削除は、効果が小さいため現在保留。
- DELETEしてもRailway物理diskが即縮むとは限らない。
- VACUUM / VACUUM FULLは未承認。
- 新システムが十分に確立した後、旧システムデータを `still-needed / archive-only / safe-delete` に分類して整理する。

## 安全上の要点

- Production Candidate Discoveryはまだ未導入。
- current v24 / FINAL / LINEを勝手に変更しない。
- `purchase_action=false`。
- fail-closed維持。
- no-future-leakageを厳守。
- 結果を見た後に同じ実験の条件を変えない。
- PRやCIが存在することだけを理由にmerge/deployしない。

## 文書更新ルール

このファイルにはCURRENT / HOLD / NEXTだけを残し、古い記述は置換してください。長い日次ログや完了経緯はPR本文・研究docs・`PROJECT_HISTORY.md`へ残します。
