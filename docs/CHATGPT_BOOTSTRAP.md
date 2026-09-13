# boat-ai-v2 — ChatGPT Lightweight Bootstrap

更新日時: 2026-09-13 JST

このファイルは、新しいChatGPTチャットが最初に読む軽量入口です。詳細は必要な範囲だけ `docs/PROJECT_HANDOFF.md` とPR #351を参照してください。

## 0. 最重要ルール

- 最初にcurrent GitHub `main`、open PR、PR #351 head/Actionsを再取得する。
- SHA・件数・CI状態はcheckpointであり固定値ではない。
- GitHub `main` = Production code Source of Truth。
- Railway PostgreSQL = Production data Source of Truth。
- mainへ直接編集しない。原則 `branch → Draft PR → CI → review → merge`。
- 安全なread-only監査、研究コード、Draft PR、CI、文書整理は連続して進めてよい。
- Production merge、Railway Production変更、Production DB write/delete/schema/VACUUM、model/係数/閾値/候補判定変更、実LINE、Forward persistence、自動購入、有料契約・外部問い合わせは明示承認が必要。
- `purchase_action=false`、fail-closed、no-future-leakageを維持する。
- 結果を見た後に同じ実験の条件をretuneしない。

## 1. Current checkpoint

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- handoff時 main: `8abbb0186852969129175848ee106118031f97e4`
- Railway project: `boat-v2-postgres`
- Production DB service: `postgres-recovery`
- Primary research: Draft PR #351 `Research: Candidate Discovery main feed (V1-V4)`
- Branch: `research/candidate-discovery-v1-20260913`
- PROJECT_HANDOFF更新commit: `e273a767b0ed4afa1c5034fa9b9eb27ab2ca6d2c`

再開時は上記を必ずcurrent値と照合する。

## 2. Current strategy

競艇を最優先とする。

- 新しい Candidate Discovery を将来の主候補システムとして育てる。
- 現行v24は当面benchmark/referenceとして残す。
- **候補feedと購入判断を分離する。**
- EVや絶対オッズ帯で候補を極端に減らさない。
- 現行S01-S05はlegacy/reference carryoverとして比較する。
- Production Candidate Discoveryはまだ未導入。

## 3. Candidate Discovery V4

Stage 1 main feed:

- TOP6 races/day × TOP2 trifecta tickets/race
- Course `0.50`, missing lane neutral
- Opponent Pressure `1.0`, first-place-only
- Motor2 beta `0.06`, position weights `1.0 / 0.6 / 0.3`
- four equal-weight structural race metrics
- no EV gate
- no absolute odds eligibility gate

Stage 2:

- late Bao / market corroborationはタグのみ。
- Stage-1候補を削除しない。
- Bao disagreementでも候補feedを維持する。

詳細:
- `docs/CANDIDATE_DISCOVERY_V4_CONTRACT_20260913.md`
- `docs/CANDIDATE_DISCOVERY_TWO_STAGE_ARCHITECTURE_20260913.md`

## 4. Official Forward freeze — 2026-09-13

結果確定前のofficial freeze:

- Actions run `34726186753`
- 約08:44 JST
- V4 core 6 races / 12 tickets
- legacy 2 races / 2 tickets
- total 8 races / 14 tickets
- Artifact ID `10308110102`
- ZIP SHA-256 `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`
- JSON SHA-256 `50be76554372fb0a54a979b04d2b991cdcb15cc699e48bcf7623e1ca0032129c`

評価時はexact frozen Artifactを使用し、再生成しない。

詳細: `docs/CANDIDATE_DISCOVERY_FORWARD_20260913.md`

## 5. Backtest conclusions

過去データbacktest / walk-forward / time-splitを実施済み。

- V1 ROI ~66-71%: candidate discoveryには使えるが購入ロジック不可。
- V2: small formationでhit rateは上がるがROI <100%。
- V3: 約8 candidates/day、ROI ~63.7%。
- 3連単 / 2連単 / 3連複 × TOP1/2/3/5 + coverage 20/35/50 を100円/点で比較済み。
- 2連単・3連複はhit rate/連敗耐性を改善するが、券種変更だけでは長期収支は黒字化しない。
- 30日で約102%だったA+B×3連複TOP1は長期1,733 racesでROI約83.01%、-29,440円。採用しない。
- 長期predeclared gridにROI 100%超セルなし。

券種・点数・Tierを結果後に後付けで切り直さない。

## 6. Prospective market hypothesis

固定研究仮説:

`MKT_LATE07_TOP2_SUPPORT_V1`

- start: **2026-09-14 JST**
- inherited Bao late window: 0-7 minutes predeadline
- rule: structural candidateをmarket TOP2も支持するか
- candidate feedを削らない。独立タグ研究。
- 2026-09-13をprospective実績へ後付け算入しない。
- review at 30 / 50 / 100 evaluated opportunities
- window / TOP2定義 / thresholdを途中変更しない。

30日proxyでは小標本ながら:

- trifecta TOP2 support: 34 races / ROI ~107.94%
- trio TOP2 support: 47 races / ROI ~109.15%

これはPromotion根拠ではない。Forward再現性が必要。

関連:
- `docs/CANDIDATE_DISCOVERY_MARKET_CORROBORATION_FORWARD_20260914.md`
- `docs/CANDIDATE_DISCOVERY_MARKET_FORWARD_EVAL_CONTRACT_20260913.md`
- `research/candidate_discovery_market_annotation_contract.py`
- `research/candidate_discovery_market_forward_metrics.py`

## 7. Next actions

1. PR #351の**最新headと全Actionsを再取得**する。
2. 最新branchのmarket annotation contract / wiring / Forward metrics CIを確認する。
3. 古い `V4 Market Annotation Dryrun` failureを現在のfailureと決めつけない。初回failureはdocstring内語句への静的guard誤検知だった。
4. 2026-09-14以降、Prospective market tag evidenceを固定条件のまま蓄積する。
5. 2026-09-13 official freezeはexact Artifactで結果評価する。
6. V4/Bao/marketのForward evidenceを30/50/100件で判定する。
7. 十分な証拠が出た後にのみProduction promotion案を作る。実promotionには明示承認が必要。

## 8. Railway / storage HOLD

- 容量圧迫はあるが、予測・backtest価値のあるデータを容量目的だけで削除しない。
- `v2_odds_trifecta` は単純削除対象ではない。
- Motor2 older-retention実削除は効果が小さいため保留。
- DELETEしても物理diskが即縮むとは限らない。
- VACUUM / VACUUM FULLは未承認。
- 新システム確立後、旧データを `still-needed / archive-only / safe-delete` に分類してから整理する。

## 9. Startup sequence

新しいチャットでは:

1. この `CHATGPT_BOOTSTRAP.md` を読む。
2. `docs/PROJECT_HANDOFF.md` を読む。
3. current `main` / PR #351 / open PR / latest Actionsを確認。
4. 必要なresearch docsだけ読む。過去Issue/履歴を一括取得しない。
5. safe read-only/research workは確認を挟まず続行する。
6. Production境界へ到達した時だけ対象操作を明示して承認を取る。

## 10. Parallel projects

TOTO / 地方競馬等は別系統。boat-ai-v2のCandidate Discovery研究を最優先し、別repo・別DB・別Variablesを混同しない。
