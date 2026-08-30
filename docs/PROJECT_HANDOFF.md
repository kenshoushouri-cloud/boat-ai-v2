# boat-ai-v2 Permanent Project Handoff

更新日時: 2026-08-30 JST

このファイルは、新しいChatGPTチャット・新しい担当者・長時間中断後でも、`boat-ai-v2` の現在地から安全に再開するための常設引き継ぎです。

**再開時は、このファイルに書かれたSHAや件数を現在値だと仮定せず、最初に GitHub main / open PR / Railway read-only health を再確認してください。**

関連資料:
- `docs/PROJECT_HISTORY.md`: これまでの判断・採用/却下理由の時系列
- `docs/DEVELOPMENT_STATUS.md`: Bao等の技術検証の詳細ログ
- GitHub Issue #42: owner-only Railway Bridge control/audit log

---


<!-- RACER_COURSE_TOP3_FORWARD_MILESTONE_20260825 -->
## 0A. 2026-08-25 選手×コース3連対率 Forward 追加

- PR #241: `v2_racer_course_stats_snapshots` のForward readinessを結果非参照で監査。42日、4,005R full6はあるが timing-safe 97.54%・日別欠損ありのため、無条件のincremental OOSは `INSUFFICIENT_FOR_INCREMENTAL_OOS`。同日snapshotはupsertで後から更新され得るため、可変sourceを結果評価へ直接使わない。
- PR #242: source integrityを事前固定し、6艇すべてが当日08:15 JSTまで・deadline前のcomplete-caseだけで `course top3 rate` をcurrent v24へ追加するtrain-only expanding OOSを実施。係数grid `0/0.05/0.10/0.20/0.30/0.50`、3つの非重複OOSすべてでtrain選択係数=0.50。全OOS 2,299Rで Brier delta `-0.00608767`、LogLoss delta `-0.21143915`、ticket rank delta `-5.0170`、Top10 `31.62% -> 38.76%`。3/3 splitでBrier/LogLoss/rank改善。0.50はgrid上端のため同じOOSで係数を拡張探索せず、**0.50固定**。
- PR #243: `v2_racer_course_top3_forward_shadow` を追加。BASE=current Production PRE v24（motor2/boat2 defaults 33/34, PROB_TEMP=2.20）、COURSE=`BASE raw strength + 0.50*z(official course top3 rate)`、lane=course early-PRE proxy。exact-date official source、6艇必須、source `created_at <=08:15 JST`・deadline前、write時3分以上lead、1 race 1 row、`ON CONFLICT (race_id) DO NOTHING` first-write-wins。
- 自動収集: GitHub Actions 06:45 JST開始、2分間隔・2時間loop。Railway `cron-racer-course-stats` 07:15 JSTの完了遅延を吸収する。Railway service schedule自体は変更していない。
- 初回confirmed Forward write（2026-08-25 19:00 JST前後）: payload 9R / write 9R / invalid 0 / pending 9。初回healthは evaluated 0、promotion=`BLOCK_MANUAL_REVIEW_ONLY`。
- 決定: `KEEP_FIXED_FORWARD_SHADOW_RESEARCH_ONLY`。Production v24/FINAL/LINE/BUY-WATCH-SKIPへは未昇格。係数0.50、08:15 cutoff、lane=course proxyをForward中に変更しない。

## 1. 新しいチャットで最初に渡す指示

以下だけで再開できる状態を維持する。

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/PROJECT_HANDOFF.md` と `docs/PROJECT_HISTORY.md` を読んでください。次に現在の main、open PR、Issue #42 の Railway read-only health を確認し、引き継ぎの続きから安全に作業してください。GitHubをコードのSource of Truth、Railway PostgreSQLを本番データのSource of Truthとして扱ってください。

---

## 2. Source of Truth / 基本構成

### GitHub
- Repository: `kenshoushouri-cloud/boat-ai-v2`
- コードの Source of Truth: **GitHub main**
- mainを直接編集しない。
- 原則: branch → Draft PR → CI → review → ready → merge。

### Railway
- Production project: `boat-v2-postgres`
- PostgreSQL service: `postgres`
- 本番データの Source of Truth: **Railway PostgreSQL**
- Supabase: 削除済み。使用しない。
- 各serviceのDB参照は原則 `DATABASE_URL=${{postgres.DATABASE_URL}}`。
- Railway token / secret値は文書・Issue・回答へ出さない。

### 最新の機能コード基準点
この引き継ぎ文書を作り始める直前の main:
- `4e18cfb0eb52a01869dcb72be79089ca8f7bb5c0`
- PR #189 `Audit: report opponent-pressure forward health` マージ後。

これは「最後に確認した機能コード基準点」であり、再開時の current main ではない。必ず再取得する。

### Open PR
2026-08-24 20:23 JST 時点:
- **PR #169** `Draft: temporary 10-minute base-odds refresh`
  - Open / Draft
  - **安易にマージしない。**
  - base oddsの完全性を改善するが、PRE候補/通知を改善する証拠がまだない。
  - 詳細は後述。

---

## 3. 最重要: 予想システムは2系統を分けて扱う

この区別を崩さない。

### A. 現行Production予想系（本来の予想システム）
主軸。最優先で改善する。

目的:
- 的中精度
- 予想の安定性
- 展示・モーター・選手能力・相手構成・場/気象・直前情報の統合
- BUY / WATCH / SKIP の安全な運用

現在の大きな流れ:
- v24 PRE
- FINAL realtime
- LINE notification

### B. 馬王型（理論価格・期待値型）研究系
通常予想の代替ではない。

2026-08-24の方針:
- **通常予想プラスアルファ程度**として扱う。
- 補助評価、穴候補、見送り判断、価格差の研究材料。
- Productionの主エンジンにはしない。

研究概念:
- model probability
- market implied probability
- theoretical odds
- value ratio / edge / EV
- calibration
- walk-forward / OOS

重要な最新結論:
- 現在のv24生確率を、そのまま `確率 × オッズ` の馬王型EVに使わない。
- AI評価が高いほど実績が良くなる関係が確認できず、一部では逆に悪化した。
- 馬王型の研究は継続するが、通常予想側の改善を優先する。

---

## 4. Railway主要services

確認済みの主要運用:

- `cron-data-prepare`
  - Start: `python -u run_daily_data_prepare_pg.py`
- `cron-window-morning`
  - Start: `python -u run_window_pipeline_pg.py`
  - cron例: `15 23 * * *` (UTC)
- `cron-window-day`
  - Start: `python -u run_window_pipeline_pg.py`
  - cron例: `35 0 * * *`
- `cron-window-night`
  - Start: `python -u run_window_pipeline_pg.py`
  - cron例: `35 5 * * *`
- `cron-final-check`
  - Start: `python -u run_final_pg.py`
  - cron例: `*/15 23,0-14 * * *`
- `cron-nightly-results`
  - Start: `python -u run_nightly_results_pg.py`
  - cron例: `30 14 * * *` = 23:30 JST
- その他:
  - `cron-learning-all`
  - `cron-racer-course-stats`
  - `cron-monthly-report`
  - `cron-daily-report`
  - `backtest-analysis`
  - `historical-backfill`
  - `test-beforeinfo-extra`
  - `postgres`

再開時は `/railway inventory` / `/railway config` 等で現状を確認してから変更する。

---

## 5. Production DB主要テーブル

正しい出走表テーブル名は **`v2_race_entries`**。
`v2_entries` は誤り。

主要テーブル:
- `v2_races`
- `v2_race_entries`
- `v2_results`
- `v2_result_entries`
- `v2_odds_trifecta`
- `v2_exhibition`
- `v2_race_weather`
- `v2_feature_snapshots`
- `v2_realtime_odds_snapshots`
- `v2_candidate_filter_shadow`
- `v2_opponent_pressure_shadow_v2`

Bao / Shadow系はProduction判定系から隔離されていることを保つ。

---

## 6. FINAL chain

現在追跡済みのFINALチェーン:

`run_final_pg.py`
→ `v25_final_realtime_pipeline_pg.py`
→ `v21_realtime_collector_pg.py`
→ `run_v22_targeted_pg.py`
→ `v22_exhibition_shadow_pg.py`
→ `v23_line_notifier_batch_pg.py`

`v21_realtime_collector_pg.py`:
- version確認済み: `2026-07-30 ticket-validation-v1`
- 三連単ticketの不正値除外を修正済み。

---

## 7. 時間帯ウィンドウ設計

基本は「オッズ取得 → PRE判定 → 通知」。

- morning: おおむね 08:30–10:15
- day: おおむね 09:45–15:00
- night: おおむね 14:45以降

重複ウィンドウを持たせ、締切の早いレースを取りこぼさない設計。

---

## 8. 2026-08-24 当日データ収集の最新確認

2026-08-24 20:23 JST の read-only `today-health`:

- races: **144 / deadline_ready 144**
- entries: **864 rows / 144 races / full6 144**
- odds rows: **17,148**
- odds races: **144**
- exact dynamic complete: **116**
- elapsed: 140
- elapsed odds complete: 112
- upcoming: **4**
- upcoming odds complete: **4 / 4**

つまり、その時点で**これから走る4Rにはオッズ不足なし**。

未完全なdynamic exact状態は既に終了したレース側に残っている。これは学習/補修候補であり、20:23時点の今後のProductionレースの直接ブロッカーではない。

---

## 9. PRE / v24 low-core の現状

現在観測されているPRE候補0の主因は、下流フィルタではなく low-core 自体が存在しないケースが多い。

v24 low-coreの確認済み条件:
- `11 <= prob_rank <= 20`
- `market_rank == 1`
- `3.0 <= odds < 5.0`

7日診断では:
- ready: 1049
- low_core: 4
- 約0.381%

同じticketで
- prob rank 11–20
- market rank 1
- odds 3–5

が重なる構造自体が非常に希少。

重要:
- R10–12除外が主原因ではなかった。
- base odds不足をメモリ上で補完しても候補0のケースを確認した。
- 現段階でProduction閾値を緩めない。

---

## 10. PR #169 base-odds refresh の扱い

PR #169:
- Open Draft
- temporary 10-minute base odds refresh
- 10–60分前の対象
- dynamic exact120/60/24が完全ならskip
- PRE / LINE / FINALは呼ばない
- Railway Variables/settingsは変更しない

保持理由:
- base odds完全性の改善効果はある。
- しかし read-only sensitivity では、公式exact120を補完してもPRE candidate 0だった。
- low_core_total=0 のケースも確認。

**結論: データ完全性だけを理由にマージしない。**
予測・学習・通知に明確な価値が確認されるまでDraft維持。

---

## 11. N02 / candidate Shadow研究

### N02固定条件
- prob rank 11–20
- market rank 2–5
- odds 3–6
- R07–R10
- any venue/event
- select mode EV

N01は範囲を広げた案:
- prob rank 11–25
- market rank 2–5
- odds 3–6
- R07–R12

### 現在の結論
- N02 Forward実データは非常に少ない。
- live scarcityの主ボトルネックは **odds 3–6**。
- N01へ広げてもlive exact候補不足は解消しなかった。

### Phase9 OOS
Extension(N01側) overall:
- n=15
- hits=2
- ROI=65.3%
- OOS1 ROI=0%
- OOS2 ROI=122.5%

不安定なので採用しない。

### Phase10 fixed filters
Motor/頭ST等の事前固定フィルタを試したが:
- 全フィルタ OOS1 ROI 0%
- OOS2のみ良好

これも再現性不足。

**決定:**
- N01 inactive維持
- N02 CORE固定
- odds帯を同じOOSデータから後付け調整しない
- Forward蓄積を優先

---

## 12. 馬王型の最新検証

2026-08-24に以下を読取専用で検証。

### OOS確率/価格検証
- v24の生のmodel probabilityは絶対確率として十分calibratedではない。
- value ratioが高いほどROIが良くなる関係は確認できなかった。
- 一部では高valueほど悪化。

PRE時点のfrozen Shadowでも同傾向。

したがって:
- v24の生確率をそのまま理論オッズへ変換しない。
- 「AIが市場より強く評価するほど買う」方式を採用しない。
- 馬王型は独立calibrationができるまで補助研究。

N02は条件抽出として一定の可能性があるが、絶対確率の正しさとは分けて考える。

---

## 13. モーター / ボート実測値の最新知見

v24確率式を調査したところ、比較テストのbaselineでは:
- motor 2-place rate = 33.0固定
- boat 2-place rate = 34.0固定

一方 `v2_race_entries` には実測値を保存可能。

### 2026-07-01..2026-08-15 / 7,184R
- BASE logloss: 4.40602095
- MOTOR actual: 4.40303973
- BOAT actual: 4.40531781
- BOTH actual: 4.40232791

改善量:
- MOTOR logloss delta: **-0.00298123**
- BOAT: **-0.00070314**
- BOTH: **-0.00369304**

的中艇平均順位:
- BASE 29.6272
- MOTOR 29.4589
- BOAT 29.6253
- BOTH 29.4407

主因はモーター。

### 2026-04-01..2026-06-30 / 13,525R
再現検証:
- BASE logloss: 4.41818166
- MOTOR: 4.41508752
- BOAT: 4.41811265
- BOTH: 4.41501772

Delta:
- MOTOR: **-0.00309414**
- BOAT: -0.00006902
- BOTH: -0.00316395

的中艇順位:
- BASE 29.9449
- MOTOR 29.7396
- BOAT 29.9488
- BOTH 29.7353

4–6月でも改善主因はモーターで再現。

### ただしProductionへ直投入しない
ユーザーからの重要な要件:
- **モーター交換時期・使用開始時期に注意する。**
- 交換直後の率を成熟モーターと同じ信頼度で扱わない。

既存方針:
- DB first-seen dateを公式のモーター使用開始日だとみなさない。
- BOAT RACE公式の使用開始日をprimary sourceにする。
- 艇国データバンクはsecondary cross-check / 補助情報源。

次の正しい検証:
- official motor generation/use-start date
- days since start
- number of appearances
- maturity / shrinkage
- actual motor 2-place rate

を組み合わせたOOS。

モーター実測値が改善したからといって、成熟度を確認せずProduction式を変更しない。

---

## 14. 艇国データバンクの扱い

ユーザー要望:
- 公式以外に艇国データバンクを活用したい。

過去検証済み:
- GitHub Actionsから艇国DBへはtimeoutするケースがあり、自動取得primary sourceとしての安定性に課題。
- 公式ページとのcheckpoint照合は実施済み。

Source policy:
1. **BOAT RACE公式 = automated primary**
2. **艇国DB = secondary / externally verified cross-check / 公式不足情報の参考**

モーター交換/使用開始、選手・コース別成績等で役立つ情報があれば、利用規約・取得安定性・再現性を確認しながら補助利用する。

---

## 15. 選手 × 相手コース/ランク相性 = Opponent Pressure

これは「今後検討するだけ」のテーマではない。過去にかなり進んでいる。

### 過去に検証した粒度
- racer × own lane × opponent lane × opponent class
- exact 5-opponent class pattern
- aggregate opponent-class counts
- own-class × own-lane × opponent-class × opponent-lane global baseline

全履歴 readiness audit:
- participant rows: 384,660
- racers: 1,649
- individual pair median n: 9
- individual ge30: 4,177
- exact pattern median n: 1
- global class/lane groups: 480
- global class/lane median n: **3,387**

結論:
- 個人×相手条件は母数が薄い場合が多い。
- global own-class × own-lane × opponent-lane × opponent-class は十分な母数。
- 個人相性は十分なnがある時だけ使い、少ない時はglobalへshrinkする方向が安全。

### OOS opponent pressure
chronological splits:
- 2026-03-31
- 2026-04-30
- 2026-05-31

3splitすべてでbaselineよりBrier改善を確認。
例:
- win Brier improvement 約0.00134–0.00136
- top3 Brier improvement 約0.00377–0.00390
- score quartileの実勝率/3着内率も明確な順序性を確認。

### Shadow v2
`v2_opponent_pressure_shadow_v2`

日次収集実装済み。
2026-08-24のhealth:
- 2026-08-22: 156 / 156R
- 2026-08-23: 168 / 168R
- 2026-08-24: 144 / 144R
- total rows: 468
- model/train_end/arrays/matched opponents 全件正常

つまり、**この研究ラインは生きている。重複実装しない。**

次の検証は、通常予想Aに組み込む前に、このForward Shadowが実結果に対してどの程度incrementalに効くかを評価する。

---

## 16. Bao / Motor2 / Exhibition Forward

BaoはShadow / researchであり、Productionへ自動昇格しない。

係数:
- Motor2 beta = 0.06
- Exhibition beta = 0.06

証拠ルール:
- market earlyは6艇・120ticket完全なexact frozen evidenceのみ
- partial / 119 / 0は拒否
- exhibitionは6艇times + rank permutation 1..6
- frozen時刻順序を守る
- mutable realtime snapshot timestampを正式forward evidenceに使わない

Promotion gates:
1. market Forward pairs >=30
2. exhibition Forward pairs >=30
3. Motor2 realized results >=30
4. exhibition realized results >=30

最後に確認できているformal state (2026-08-24 18:24 JST付近):
- market paired: 52
- exhibition proxy-ready: 43
- Motor2 realized: 13
- Exhibition realized: 7

したがって realized gates未達。

**Promotion = BLOCK**

30件を超えても自動Production反映しない。
`READY_FOR_MANUAL_REVIEW`止まり。

---

## 17. Railway Bridge / Issue #42

Issue #42はowner-only Railway control/audit hub。

代表read-only command:
- `/railway status`
- `/railway inventory`
- `/railway config`
- `/railway today-health`
- `/railway bao-paired-forward-audit`
- `/railway bao-formal-forward-eval`
- `/railway window-refresh-plan`
- `/railway window-refresh-live-probe`
- `/railway pre-repeat-plan`
- `/railway pre-odds-sensitivity`
- `/railway n02-forward-robustness`
- `/railway v24-low-candidate-diagnostic`
- `/railway candidate-shadow-active-report`
- `/railway n02-live-opportunity-plan`
- `/railway phase4-live-compare`
- `/railway phase9-oos-extension-report`
- `/railway phase10-oos-fixed-filters-report`
- `/railway opponent-composition-readiness`
- `/railway opponent-pressure-forward-health`
- `/railway motor-ablation-history-stability`
- `/railway logs <service>`

Write command例:
- `/railway window-refresh-run CONFIRM`

Writeは目的・影響を確認してからのみ。
`window-refresh-run CONFIRM` はbase odds writeだけであり、PRE/LINE/FINALを自動実行しない。

---

## 18. Productionで変更してはいけない/慎重に扱うもの

十分なOOS/Forward証拠なしに以下を変更しない:
- BUY / WATCH / SKIP logic
- LINE notification logic
- Railway Variables / schedules / settings
- v24 probability thresholds
- v24 low-core thresholds
- N02 rule / odds band
- N01 activation
- Bao beta coefficients
- Bao promotion
- base odds scheduler PR #169
- current Production scoring weights

同じデータで「候補が少ないから条件を広げる」→「良く見えるまで調整」はしない。
OOSを後からtrainingとして再利用しない。

---

## 19. 現在の優先順位

### Priority 1: 現行Production予想Aの精度向上
特に:
1. モーター実測値の改善効果を、公式使用開始/交換時期・成熟度込みで検証
2. Opponent Pressure Forward Shadowのrealized incremental value評価
3. 展示・選手能力・場/気象等を一機能ずつOOS/Forward検証
4. 現行候補不足の原因を、閾値緩和ではなく特徴・確率品質から改善

### Priority 2: データ品質
- elapsed dynamic odds gapsは学習用補修候補
- upcoming completenessをProductionでは優先
- historical frozen evidenceか、単なる最終/後取得データかを区別

### Priority 3: Bao Forward
- realized Motor2 30
- realized Exhibition 30
まで蓄積
- 係数固定

### Priority 4: 馬王型B
- 通常予想の補助
- calibration改善後に理論価格を再検討
- v24 raw probabilityをそのままEVに使わない

---

## 20. 次の安全な作業候補

新しいチャットでcurrent state確認後、最優先候補:

1. **motor maturity OOS**
   - 公式モーター使用開始日/交換世代
   - 実測2連率
   - 経過日数/appearance count
   - shrinkage
   - fixed split OOS

2. **opponent-pressure Forward realized report**
   - 8/22以降Shadow rowsとresultをjoin
   - baseline vs pressure-adjusted
   - Brier/logloss/ranking
   - Productionへはまだ反映しない

3. **Bao read-only audit**
   - gates確認だけ

4. **PR #169はhold**
   - 明確なprediction/learning valueが出るまでmergeしない

---

## 21. 引き継ぎ更新ルール

今後、大きな判断のたびにこのファイルを更新する。

更新トリガー:
- Productionに関係するPRがmerge
- 研究featureがOOS gateを通過/失敗
- Railway service / schedule / DB schema変更
- ShadowがForward gate到達
- 採用/却下の重要判断
- Source of Truth変更

更新方法:
1. `PROJECT_HANDOFF.md` = **現在地を上書き**
2. `PROJECT_HISTORY.md` = **判断経緯を追記**
3. 詳細な実験ログは `DEVELOPMENT_STATUS.md` またはPR/Issue #42に残す

この3層に分け、チャット全文を保存しない。

---

## 22. ユーザーの開発方針

- 作業は可能な限り自動で進める。
- ユーザーへ大量の途中ログを要求しない。
- GitHub/Railway Bridgeで安全に確認できるものは自分で確認する。
- ユーザー向け報告は基本:
  - **実施内容**
  - **結果**
- 調査・CI・review等の内部確認は必要だが、説明は簡潔にする。
- Production影響が大きい変更は慎重にする。

---

## 23. 最後の再開チェックリスト

新しいチャットは以下の順で開始する。

1. `PROJECT_HANDOFF.md` を読む
2. `PROJECT_HISTORY.md` を読む
3. current main SHA確認
4. open PR確認
5. PR #169がまだDraftか確認
6. `/railway today-health`
7. 必要に応じ `/railway status` / `inventory`
8. Bao / N02 / opponent Shadow等、今回の作業対象だけread-only audit
9. 過去の却下理由を確認してから新しい変更案を作る
10. branch → Draft PR → CI → review → merge

以上。


---

<!-- HANDOFF_MILESTONE_20260824_OPP_MOTOR -->
## 追記: 2026-08-24 21:10 JST — Opponent Pressure実結果 / モーター交換・成熟度

この節は PR #191〜#194 完了後の重要マイルストーン。Productionロジックは変更していない。

### main基準点
この追記作成直前の main:
- `a34e48d3fbc809ab173925e18eb774cae0e639e6`
- PR #194 マージ後。

再開時は必ず current main を再取得する。

### Opponent Pressure — 実結果Forward
PR #191で既存 `v2_opponent_pressure_shadow_v2` と確定着順を比較するread-only Forward evaluatorを追加。
初回は旧 `v2_result_entries` を読んだため0評価となった。現在のnightlyは `v2_results` の `first_lane..sixth_lane` が正なので、PR #192で評価側のみ修正した。

2026-08-22〜08-24のfrozen Shadow:
- Shadow rows: 468
- `v2_results` official rows: 324
- evaluated: **292**
- pending: 176
- malformed: 0
- integrity skip: 0

Overall 292R:
- win Brier: `0.10984498 -> 0.10869775` / delta **-0.00114723**
- top3 Brier: `0.21241847 -> 0.21071051` / delta **-0.00170796**
- winner logloss: `1.34694537 -> 1.33417941` / delta **-0.01276596**
- winner rank: `2.0582 -> 2.0514` / delta **-0.0068**

日別でも8/22・8/23ともBrier/loglossは改善。

**判断:**
- historical OOSと実結果Forwardの方向が一致し、通常予想系の補助特徴量として有望。
- ただし実結果はまだ292R・2日分中心なので **Productionへ入れない**。
- daily Shadowを継続し、日数・場・レース条件をまたいだ再現性を確認してから次段階へ。

### モーター交換時期 — Source policy
モーター世代開始日はDB first-seenから推定しない。

優先順位:
1. **BOAT RACE / 各場公式** = 一次情報
2. **艇国DB** = 補助・クロスチェック
3. Railway DB first-seen = 診断用途のみ。公式開始日として使わない。

2026-08-24に公式ページで固定確認したcurrent-generation subset:
- venue 03 江戸川: **2026-05-11**
- venue 05 多摩川: **2026-04-18**
- venue 12 住之江: **2026-03-23**
- venue 14 鳴門: **2026-04-11**
- venue 23 唐津: **2025-09-05**

### PR #193 — 世代開始からの日数別モーター実測値
5場、official start以降、motor data complete **5,095R**。
BASE=fixed motor2 33.0、MOTOR=出走表の実測motor2。v24式/係数/PROB_TEMPは固定、boat2=34.0固定。

Overall:
- logloss delta **-0.00324000**
- Brier delta **-0.00007750**
- winner rank delta **-0.2075**

世代開始後の日数別 logloss delta:
- 0–14日: n582 / **-0.00579696**
- 15–30日: n522 / **-0.00440829**
- 31–60日: n723 / **-0.00234561**
- 61–120日: n1510 / **-0.00303145**
- 121日+: n1758 / **-0.00259356**

若い0–30日もaggregateでは悪化しなかった。一方、venue×ageには一部悪化区間あり。

**判断:** 「交換直後だから実測motor2を一律に弱める」という単純補正は採用しない。

### PR #194 — 個別モーターの事前出走回数別
公式世代開始日から、各motor_noの**現在レースより前の出走表登場回数だけ**を時系列カウント。同一レースをカウントしてから評価しないため、same-race leakageなし。
レースは6艇中もっとも事前登場回数が少ないmotorで分類。

Coverage:
- result races: 5,114
- evaluated / motor complete: **5,095**
- prior <10 sample: 815
- prior 20+ sample: 3,707

最小prior count別 logloss delta:
- 0–4: n438 / **-0.00240089** / rank delta `+0.0776`
- 5–9: n377 / **-0.00719944** / rank delta `-0.6286`
- 10–19: n573 / **-0.00454600** / rank delta `-0.3700`
- 20–39: n1081 / **-0.00439443** / rank delta `-0.4218`
- 40+: n2626 / **-0.00205133** / rank delta `-0.0708`

全固定binでloglossは改善したが、0–4ではwinner rankが僅かに悪化し、場別の低母数binには悪化例もある。

**判断:**
- motor実測値そのものの有用性は強まった。
- しかし「prior N未満なら除外/○%減」のような閾値を、この同じ結果から後付けで作らない。
- 交換時期・公式世代開始・個体母数をメタデータとして保持し、Forwardで場別安定性を確認する。
- Production v24の固定33.0は、まだ変更しない。

### 次の優先順位（この追記時点）
1. Opponent Pressure daily Shadowを継続し、実結果Forwardを日数・場をまたいで再評価。
2. motor実測値は公式世代開始日/個体prior countを伴う独立Shadowまたは固定read-only比較でForward確認する。後付け閾値調整はしない。
3. 公式motor generation startの場カバレッジを増やす。艇国DBは補助照合に使う。
4. Baoは既存gateを維持。馬王型は通常予想のプラスアルファ。
5. PR #169はDraft維持。Production/LINE/threshold/Railway設定は未変更。

---

<!-- HANDOFF_MILESTONE_20260825_GUARD05_FORWARD -->
## 追記: 2026-08-25 — GUARD05交換直後保護 / 独立Forward Shadow

この節は PR #225〜#229 完了後の重要マイルストーン。通常予想Aのモーター研究だが、**Production v24にはまだ反映していない**。

### この追記直前のmain基準点
- `7bdbf059bfaa9c665c5b94afa3386977214163b4`
- PR #229 `Shadow: schedule daily GUARD05 Forward collection` マージ後。

再開時は必ずcurrent mainを再取得する。

### GUARD05の固定ルール
公式current-generation startが確認済みの5場（03/05/12/14/23）のみ対象。

Forwardで採用した成熟度定義:
- **COUNT_MODE = PRIOR_DAY**
- current generation内で、対象モーターが**TARGET_DATEより前の日付**の完全な出走表へ登場した回数を数える。
- 同日の前半R、当日の結果、当日後から確定する情報は成熟度カウントに使わない。

レーン単位の固定処理:
- prior-day appearances `<= 5` → motor2を **33.0** として確率計算
- `>= 6` → 出走表の実測 `motor_place2_rate` を使用
- threshold 5をForward開始後に動かさない。

### PR #225 — 一律shrinkageは採用しない
BASE=33%固定、FULL=実測、K03/K06/K12/K24の縮約を3期間×5場で比較。

2,963R全体では:
- FULL LL `4.41551617`
- K03 LL `4.41560430`
- K06 LL `4.41570894`
- K12 LL `4.41590176`
- K24 LL `4.41620132`

K系はBASEより改善するが、FULLには3期間すべてLogLoss/Brierで負けた。

一方 P00–05 の103RではFULLがBASEより悪化:
- BASE LL `4.57884059`
- FULL LL `4.58098931`

**判断:** 全モーターへ一律shrinkageは採用しない。交換直後だけを保護する候補へ進む。

### PR #226 — GUARD05候補生成
2,963Rでlane-local GUARD05を固定比較。

Overall GUARD05 vs FULL:
- LogLoss delta **-0.00017390**
- Brier delta **-0.00000432**
- 的中券rank delta **-0.0145**

P00–05 / 103R:
- GUARD05 vs BASE LL **-0.00285388**
- GUARD05 vs FULL LL **-0.00500259**
- Brier vs FULL **-0.00012438**
- rank vs FULL **-0.4175**

P06+ではGUARD05はFULLと同じ。

**判断:** 歴史データ上は有望。ただし同じ歴史データから導いた候補なのでProduction採用不可。新規Forward必須。

### PR #227 — 時系列安全性
結果を成熟度カウントへ一切使わない2方式で再検証:
- `CARD_ORDER`
- `PRIOR_DAY`

2,963R Overall、FULL比:
- CARD_ORDER: LL **-0.00014907** / Brier **-0.00000398** / rank **-0.0152**
- PRIOR_DAY: LL **-0.00009457** / Brier **-0.00000291** / rank **-0.0084**

両方式とも3期間すべてでFULLよりLogLoss/Brier/rank改善。

より保守的でPRE時点に確実に既知な情報だけを使う **PRIOR_DAYをForward定義として固定**。

### PR #228 — 独立compact Forward Shadow
既存 `v2_v24_motor2_forward_shadow` の疎保存/候補ROI研究へ混ぜず、専用テーブルを新設:
- **`v2_motor_guard05_forward_shadow`**

1 race = 1 row。
保存:
- model_version
- count_mode=`PRIOR_DAY`
- guard_max_prior=5
- official generation_start
- deadline_at / snapshot_at
- motor_nos[6]
- prior_day_counts[6]
- actual_motor2[6]
- guard_flags[6]
- BASE/FULL/GUARD05の三連単120確率配列

安全条件:
- collector default disabled + DRY_RUN
- collectorは結果/オッズを読まない
- write時はdeadline 3分以上前のみ
- DB constraint `snapshot_at < deadline_at`
- `ON CONFLICT (race_id) DO NOTHING`
- **first snapshot wins**。後から結果を見て確率を上書きしない。
- Production/LINE/BUY/WATCH/SKIP consumerなし。

Issue #42:
- write: `/railway motor-guard05-forward-collect CONFIRM`
- read-only: `/railway motor-guard05-forward-health`

### 2026-08-25 最初のForward書込み
PR #228 merge後、Issue #42からconfirmed writeを1回実行。

結果:
- payloads: **12R**
- write rows: **12**
- invalid: **0**
- pending results: **12**
- affected races: **0**
- guard lanes: **0**

当日の残り対象では交換直後条件が無かったためGUARD05=FULL。これは失敗ではなく、affected sampleがまだ0という意味。

### PR #229 — 毎朝自動収集
独立GitHub Actions scheduleを追加:
- cron `20 22 * * *`
- **07:20 JST daily**

これはGitHub Actions側のShadow収集であり、Railway service schedule/Variables/settingsは変更していない。

毎日:
1. TARGET_DATE当日の対象5場を確認
2. deadline前の確率をfirst snapshotとして保存
3. BASE/FULL/GUARD05の120確率を凍結
4. post-write healthはread-only

### 現在の決定
- **GUARD05 = KEEP_SHADOW / Production BLOCK**
- 8/25のunaffected 12RはGUARD05効果判定の母数に数えない。
- **affected Forward rows**が十分に蓄積し、実結果でFULLより再現性ある改善を示すまでProductionへ入れない。
- threshold 5、PRIOR_DAY定義、v24係数をForward途中で調整しない。
- 既存Production v24のmotor2固定33.0は現時点で変更しない。

### 次の確認ポイント
1. daily Shadowのcollection/integrityが継続しているか。
2. affected Forward rowsが何件になったか。
3. affectedでBASE/FULL/GUARD05のLogLoss/Brier/actual-ticket rankを比較。
4. 日別・場別の符号が安定するか。
5. 十分な新規Forward証拠が集まった時点だけmanual reviewする。

---

<!-- HANDOFF_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->
## 追記: 2026-08-25 12:45 JST — Opponent Pressure v24統合Forward / Motor V12直近反転診断

この節は PR #231〜#233 完了後の重要マイルストーン。**Production v24 / LINE / BUY-WATCH-SKIP / Railway設定は変更していない。**

### main基準点
この追記直前の main:
- `07e52455ac210128f0f2dd62355694b75fe76410`
- PR #233 `Audit: decompose recent motor holdout by venue and date` マージ後。

再開時は必ずcurrent mainを再取得する。

### Opponent Pressure — 現在のForward状態
既存 `v2_opponent_pressure_shadow_v2` は2026-08-22から日次収集継続。
8/25昼時点:
- Shadow: **624R**
- top3が確定した三連単評価可能: **468R**
- 6艇全着順integrityを要求する基本realized evaluator: **428R**

基本realized 428R Overall:
- win Brier delta **-0.00092528**
- top3 Brier delta **-0.00195974**
- winner LogLoss delta **-0.01096028**
- winner rank delta **-0.0023**

全体では引き続き有望。ただしvenue別では:
- win Brier改善 11/17場
- top3 Brier改善 15/17場
- LogLoss改善 10/17場
- rank改善 6/17場

R帯別ではR01-04 / R09-12は概ね良好、R05-08はwinner rankが僅かに悪化。

### v24三連単へ統合する固定head-only方式
既存研究を再確認し、単純な全lane weight再配分ではなく、PR #202/#203の **head-only mapping** が現在の本命研究方式。

固定定義:
- Opponent Pressureは**1着確率だけ**へ反映
- coefficient = **1.0固定**
- 2着/3着のconditionalはcurrent v24のまま
- threshold/date/venue選択なし

PR #203 historical OOSでは3固定splitすべてOverallでBrier / LogLoss / actual-ticket rank改善。
代表:
- split 2026-03-31: LL **-0.01036749** / rank **-0.352**
- split 2026-04-30: LL **-0.00969562** / rank **-0.265**
- split 2026-05-31: LL **-0.01007095** / rank **-0.259**

一方、realized Forward 468R:
- 120-class Brier delta **-0.00006135**
- actual-ticket LogLoss delta **-0.00183905**
- actual-ticket rank delta **+0.284**（悪化）

R05-08 / 156R:
- Brier **+0.00020560**
- LogLoss **+0.00859710**
- rank **+0.679**

日別では8/24が弱く、特に8/24 R05-08が悪化。

**判断:**
- historical OOSは強いが、3日中心のForwardはmixed。
- **KEEP_FORWARD_RESEARCH / Production BLOCK**。
- 8/24やR05-08を見た後に除外filterを作らない。
- 同じhead-only coefficient=1.0を固定したままForwardを増やす。

Issue #42 read-only commands:
- `/railway opponent-pressure-forward-stratified`
- `/railway opponent-pressure-v24-head-forward`
- `/railway opponent-pressure-v24-head-daily`

### fixed log-odds transportは不支持
PR #207の固定log-odds transportを再確認。
468R Overall、v24比:
- trifecta Brier **+0.00006538**
- LogLoss **+0.00093481**
- rank **+0.577**

R09-12だけは改善したがOverallは3指標悪化。

**判断:** `NO_FIXED_LOG_ODDS_FORWARD_SUPPORT_YET`。log-odds方式を追わず、head-only固定案のForwardを継続する。

### Motor actual rate — V12直近反転の診断
PR #220 independent holdout 2026-08-16..08-24 / 240RではALL_ACTUAL motor2がOverall改善:
- LL **-0.00354788**
- Brier **-0.00009918**
- rank **-0.2583**

ただし住之江 V12 / 36Rだけ悪化:
- LL **+0.00453061**
- Brier **+0.00006796**
- rank **+0.3333**

PR #219のpre-holdout V12 mature P21+は3期間すべてLogLoss改善:
- 2026-05-11..06-15: **-0.010378**
- 06-16..07-15: **-0.000588**
- 07-16..08-15: **-0.000926**

PR #233で全5場をvenue×date分解。V12の36Rは1節3日だけ:
- 8/16 n12: LL **-0.00109457**
- 8/17 n12: LL **+0.00504850**
- 8/18 n12: LL **+0.00963791**

全20 venue×date cell:
- LL改善 14/20
- Brier改善 13/20
- rank改善 12/20

**判断:**
- V12は長期的に不支持ではなく、直近1節後半2日の小標本反転。
- **V12を後付け除外しない。**
- actual motor2は有望のまま。ただしProduction一律置換はまだしない。
- GUARD05（PRIOR_DAY / <=5保護）の独立Forwardを固定継続する。

### 現在の通常予想Aの優先状態
1. Opponent Pressure head-only: historical OOS strong / realized Forward mixed → 固定Forward継続。
2. actual motor2: independent holdout Overall positive / venue・meet変動あり → GUARD05 Forward継続。
3. どちらもProductionへまだ入れない。
4. PR #169はDraft hold継続。

---

<!-- HANDOFF_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->
## 追記: 2026-08-25 17:54 JST — Exhibition ST fixed OOS / Forward Shadow自動収集

この節は PR #235〜#237 完了後の重要マイルストーン。**Production v24 / FINAL / LINE / BUY-WATCH-SKIP / Railway Variables・service scheduleは変更していない。**

### main基準点
この追記直前の main:
- `656f7d25d21b2a16b4cd33074913513d8760f971`
- PR #237 `Ops: schedule exhibition ST Forward collection` マージ後。

再開時は必ずcurrent mainを再取得する。

### PR #235 — Exhibition STをcurrent v24へ固定追加したfuture OOS
BASEはcurrent Production PRE v24相当:
- motor2 = 33.0固定
- boat2 = 34.0固定
- PROB_TEMP = 2.20

Exhibition ST側はPR #122の最初のtrain cutoffで固定済み定義を再利用:
- `z(-start_timing_rank)`
- ticket position weight = 1.0 / 0.6 / 0.3
- **beta = -0.02固定**
- coefficient searchなし

future OOS 2026-01-01..2026-08-22 / **34,697R**:
- trifecta Brier delta **-0.00001292**
- actual-ticket LogLoss delta **-0.00041811**
- actual-ticket rank delta **-0.0142**
- LogLoss改善: fixed window **4/4**、month **8/8**

**判断:** historical future OOSでは小さいが一貫したincremental value。race-band差を見て後付けfilterは作らず、同じ固定定義でForwardへ進む。

### PR #236 — 独立Exhibition ST Forward Shadow
新規専用テーブル:
- `v2_exhibition_st_forward_shadow`

固定Forward定義:
- beta **-0.02**
- deadline **8〜15分前**のofficial beforeinfoだけを使用
- lexicographic 120-ticket order固定
- BASE/ST 120確率を凍結
- collectorは**結果・オッズを読まない**
- `snapshot_at < deadline_at`
- `ON CONFLICT (race_id) DO NOTHING` = **first snapshot wins**
- Production consumer / LINEなし

最初のconfirmed collectionはofficial Forward **3R**、invalid/timing/source error 0、結果はpendingで開始。

Issue #42:
- write: `/railway exhibition-st-forward-collect CONFIRM`
- read-only: `/railway exhibition-st-forward-health`

### PR #237 — 5分間隔の自動Forward収集
GitHub Actions schedule:
- `*/5 0-12,23 * * *` UTC
- **08:00〜21:59 JST、5分間隔**

collector自身の8〜15分前windowは変更しない。GitHub Actions側の収集頻度だけを上げ、7分幅windowのdeterministic missを避ける。

初回CIではworkflow自己検査の `send_line` 禁止文字列がassert文自身へ一致するself-matchで専用CIだけ失敗。機能側ではなくCI検査の不具合だったため、禁止語を文字列連結へ変更。修正後:
- Critical Python syntax: PASS
- Critical mojibake guard: PASS
- Production shadow isolation: PASS
- Exhibition ST Forward scheduled collector: PASS
- V21 parser sanity: PASS

その後PR #237をready → squash merge。

### 2026-08-25 17:44 JST runtime再確認
Issue #42 read-only:
- races **156 / deadline_ready 156**
- entries **936 / full6 156R**
- odds races **156**
- upcoming **19R / odds complete 19R**
- night window **65R / odds complete 65R**
- read-only health PASS

PostgreSQL read-only size:
- **3225 MB**（Hobby 5GB reference）

Railway inventory:
- **14 services**
- connection healthy
- Railway Variables/settings/deploy configurationは今回変更していない。

### Opponent Pressure / GUARD05の現在地
Opponent Pressure head-onlyは固定のまま:
- shadow 624R / evaluated 468R / pending 156R
- Brier delta **-0.00006135**
- LogLoss delta **-0.00183905**
- rank delta **+0.284**
- **KEEP_FORWARD_RESEARCH / Production BLOCK**
- R05-08・8/24を見た後の除外filterは作らない。

GUARD05:
- frozen rows **12**
- evaluated 0 / pending 12 / affected evaluated 0
- **BLOCK_MANUAL_REVIEW_ONLY**
- PRIOR_DAY / <=5保護を固定したままaffected Forwardを待つ。

### 現在の通常予想Aの研究優先
1. Opponent Pressure head-only fixed Forwardを継続。
2. GUARD05 actual motor2 fixed Forwardを継続。
3. Exhibition ST beta=-0.02 fixed Forwardを自動蓄積。
4. 3系統とも十分な新規Forward証拠なしにProductionへ入れない。
5. PR #169は唯一のopen PRとしてDraft hold継続。

---

<!-- HANDOFF_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->
## 追記: 2026-08-25 18:28 JST — Exhibition ST Forward scheduler遅延対策

### main基準点
この追記直前の main:
- `71166721f6dc7f5037eea37a1648c676274f6407`
- PR #239 `Ops: make exhibition ST Forward schedule delay-resilient` マージ後。

再開時は必ずcurrent mainを再取得する。

### 観測した問題
PR #237 merge後の最初のscheduled runは **18:21 JST** に開始。
workflow自体は成功したが:
- target races: 156
- 8〜15分window内 payloads: **0**
- outside_window: **156**
- write rows: **0**

manual confirmed collectorも同時刻帯ではpayload 0だった。
collector/parserの失敗ではなく、GitHub scheduled eventが約20分遅れて起動したため、7分幅のfrozen capture windowを5分cronだけでは保証できないことを確認した。

### PR #239 — delay-resilient loop
既存Bao auto captureの実績ある設計をExhibition STへ限定適用。

変更:
- trigger開始を **07:00 JST**へ前倒し
- cron: `*/5 22,23,0-12 * * *`
- scheduled job内で **2分間隔 / 90分** collection loop
- timeout 100分
-既存concurrency groupを維持、`cancel-in-progress: false`

固定のまま変更していないもの:
- beta = **-0.02**
- capture window = **8〜15分前**
- official beforeinfo only
- BASE/ST 120 probability definition
- `ON CONFLICT (race_id) DO NOTHING`
- first snapshot wins
- results/odds非参照
- Production/LINE consumerなし

PR #239 CI:
- Exhibition ST Forward scheduled collector: PASS
- Production shadow isolation: PASS
- Critical Python syntax: PASS
- Critical mojibake guard: PASS
- V21 parser sanity: PASS

### 現在の判断
- **ADOPT_DELAY_RESILIENT_FORWARD_COLLECTION**
- Production promotionは引き続きBLOCK。
- scheduler遅延を特徴量やwindow変更で埋めない。
- frozen 8〜15分window / beta=-0.02を維持したまま、新規Forward evidenceの欠損だけを減らす。
- Railway Variables / service schedules / Production v24 / LINE / BUY-WATCH-SKIPは変更していない。
- PR #169はDraft hold継続。



---

<!-- HANDOFF_MILESTONE_20260830_POSTGRES_SERVICE_LOST -->
## 緊急引き継ぎ: 2026-08-30 21:05 JST — Railway Postgres service消失 / detached volume復旧待ち

### Source of Truth
- GitHub repository: `kenshoushouri-cloud/boat-ai-v2`
- code Source of Truth: `main`
- この追記直前のmain: `3cd0108b3b8eb8d3d0d899554a377313e196aac5`
- Railway project: `boat-v2-postgres`
- production environment
- 本番DBのデータ本体はRailway Volume `postgres-volume` に残存していると画面上確認。
- Supabaseは削除済み。使用しない。
- 正しい出走表テーブルは `v2_race_entries`。

### 現在の最重要障害
2026-08-28頃からRailway画面/APIでDB参照障害が発生。
当初はRailway全体障害を疑ったが、2026-08-30のRailway Project CanvasとBridge監査で次を確定した。

1. 以前は `postgres` serviceを含む **14 services** が存在し、`postgres` latest deploymentはSUCCESSだった。
2. 現在のinventoryは **13 services** で、**`postgres` serviceが一覧から消失**している。
3. 一方、Railway Volume **`postgres-volume` は残存**。
4. iPhone Railway UIのVolume設定には **Volume is unmounted / Mount to service** と表示。
5. Volume metrics:
   - size limit: **5.00 GB**
   - usage: **約3.76 GB**
   - usage warning: **75%**
   - region: **US West (California, USA)**
6. Backups画面では既存 **Pre-Security-Patch Backup** が見えた。
   - 表示時点: 約7日前
   - size: **3.5 GB**
   - Hobby環境では新規backup作成不可とUI表示。
7. **Wipe Volume / Delete Volumeは絶対に実行しない。**
   どちらも本番データ/backupを失う破壊操作。

### DATABASE_URLの状態
各cron serviceにはVariable名 `DATABASE_URL` 自体は残っている。
しかし read-only DB reference diagnostic で以下を確認:
- cron-learning-all: `DATABASE_URL` = empty / length 0
- cron-final-check: empty / length 0
- cron-data-prepare: empty / length 0
- cron-window-night: empty / length 0
- config layer resolved URL: **NO**

過去の `postgres` serviceには少なくとも以下の標準Variable keysが存在していた記録あり:
- `DATABASE_PUBLIC_URL`
- `DATABASE_URL`
- `PGDATA`
- `PGDATABASE`
- `PGHOST`
- `PGPASSWORD`
- `PGPORT`
- `PGUSER`
- `POSTGRES_DB`
- `POSTGRES_PASSWORD`
- `POSTGRES_USER`
- volume/TCP関連Railway variables

従って現在のcron側 `${{postgres.DATABASE_URL}}` 参照は、参照先service `postgres` が存在しないため空になっている可能性が最も高い。

### 最新service health
2026-08-30 Bridge inventoryでは:
- CRASHED: `cron-daily-report`
- CRASHED: `cron-data-prepare`
- CRASHED: `cron-final-check`
- CRASHED: `cron-nightly-results`
- CRASHED: `cron-racer-course-stats`
- CRASHED: `cron-window-morning`
- CRASHED: `cron-window-day`
- CRASHED: `cron-window-night`
- `cron-learning-all` は最新inventory上SUCCESS/画面上Running表示の時点あり。ただしread-only診断ではDATABASE_URL emptyなので、これをDB復旧証拠と扱わない。
- SUCCESS表示の古い/非DB依存serviceもあるが、現在のProduction正常性を意味しない。

`cron-final-check` の実ログ:
- `RuntimeError: DATABASE_URL が必要です。`

### 読み取り診断
PR #246で `.github/workflows/railway-postgres-volume-readonly.yml` をmainへ追加。
目的はdetached volumeの `PG_VERSION` を**読み取りだけ**で確認すること。
Issue #42:
- `/railway postgres-volume-readonly`

結果:
- root listing: FAILED
- `/pgdata` listing: FAILED
- `PG_VERSION` は取得できず

これはVolumeデータ消失を意味しない。
Railway UIではVolume 3.76GB使用が確認できている。
detached volumeに対するCLI file APIが利用できない/失敗している可能性があるため、PG major versionはまだ未確定。

その後、DB referenceのread-only diagnosticもmainへ入り、Issue #42で:
- `/railway db-reference-readonly`
を実行。上記DATABASE_URL emptyを確認。

### 絶対にしない操作
復旧確認なしに以下を行わない:
- `postgres-volume` の Wipe
- `postgres-volume` の Delete
- 既存backupの破壊/上書き
- Volumeをcron application serviceへ直接mount
- 空のPostgresへVolumeを適当にmount
- PostgreSQL major versionを推測して既存data directoryを起動
- Production BUY/WATCH/SKIP、LINE、v24係数/threshold等の変更
- PR #169 merge

### 復旧の次手
次チャットはまず最新状態を再取得してから進める。

推奨順:
1. GitHub main / open PR / Issue #42を再取得。
2. Railway inventoryで `postgres` がまだ欠落しているか確認。
3. Railway UIで `postgres-volume` がunmounted、usageが維持されているか確認。
4. 元Postgres major version / image / PGDATA / auth情報を安全に特定できる手段を優先。
5. 可能ならRailway Supportにも「service消失・volume孤立」の調査を依頼。
6. 元Volumeを保持したまま、新しい正規Postgres serviceへの再接続手順を設計。
7. **データ保全を最優先し、最初の起動はversion/PGDATA互換性を確認してから。**
8. 復旧後:
   - `/railway vars postgres` 成功
   - `/railway db-reference-readonly` でnon-empty
   - `/railway today-health` 正常
   - data prepare/window/final/nightlyのDB系service正常
   - DB行数/主要テーブルをread-only監査
   を確認するまでProduction復旧完了としない。

### Open PR
- **PR #169** Draft: temporary 10-minute base-odds refresh
- 書き込み系Production base oddsのため、今回のDB復旧とは無関係。
- 明示承認なしにmergeしない。

### TOTO AI
別repo `kenshoushouri-cloud/toto-ai-v1` は初期bootstrap済み。
Railway新規Project/PostgreSQL作成は今回のRailway/boat DB問題のため一旦停止中。
**boat-ai-v2の本番DB復旧・健全性確認を優先し、その後TOTO Railwayを再開する。**



---

<!-- POSTGRES_RECOVERY_PREFLIGHT_STAGE1_20260830 -->
## 2026-08-30 — Railway Postgres recovery: exact config resolved / preflight PASS / Stage 1 Draft hold

### 現在の最優先
Production model改善ではなく、消失した Railway `postgres` service の安全な復旧を最優先とする。

**現時点でも Production DB は復旧していない。**
- current named service `postgres`: **absent**
- services discovered: **13**
- DB依存cronの多く: **CRASHED**
- `postgres-volume`: preserved / READY / detached
- Production consumerの `${{postgres.DATABASE_URL}}` は未解決のまま

### preserved volume / backup の確定事実
Issue #42 read-only diagnostics:
- volume: `postgres-volume`
- state: `READY`
- pending deletion: false
- attached service: none
- region: `us-west2`
- mount path: `/var/lib/postgresql/data`
- configured size: 5000 MB
- current size: 約 3761.75 MB
- createdAt: 2026-07-05T08:10:05.694Z

既存backup:
- `Pre-Security-Patch Backup`
- createdAt: 2026-08-23T04:57:09.850Z
- referenced: 3582 MB
- used: 270 MB
- expiresAt: 2026-09-22T04:57:09.552Z

**Volume / backup を wipe/delete/restore していない。**

### service消失 evidence
Railway events:
- 2026-08-28T11:55:48.293Z: `Deployment` removed
- 2026-08-28T11:55:49.648Z: `ServiceInstance` removed

### 元Postgresのexact runtime/config
deleted deployment + deployment snapshotからread-onlyで回収:
- image: `ghcr.io/railwayapp-templates/postgres-ssl:18`
- PostgreSQL major: **18**
- image digest: `sha256:e617e80d34d40def28ab197662197acc5cd6c1dc120db9cf38d835a2386c226c`
- builder: RAILPACK
- replicas: 1
- region config: `us-west2` / 1 replica
- restart policy: `ON_FAILURE`
- restart max retries: 10
- required mount: `/var/lib/postgresql/data`
- PGDATA: `/var/lib/postgresql/data/pgdata`
- deployment snapshot variable count: 13
- credential continuity inputs: internally available
- secret valuesはIssue/文書/回答へ公開しない

### DB variable topology
old literal hostをコピーする必要はない。
- `DATABASE_URL`: Railway referencesを使ったinterpolated value
  - `PGUSER`
  - `POSTGRES_PASSWORD`
  - `RAILWAY_PRIVATE_DOMAIN`
  - `PGDATABASE`
  - port 5432
- `PGHOST`: `RAILWAY_PRIVATE_DOMAIN` reference
- `DATABASE_PUBLIC_URL`: `RAILWAY_TCP_PROXY_DOMAIN` / `RAILWAY_TCP_PROXY_PORT` references
- literal stale-host risk: **NO**

### Recovery preflight
PR #270 merge後、Issue #42 `/railway postgres-recovery-preflight`:
- **Overall recovery preflight: PASS**
- 25/25 guards PASS
- volume state/size/region/mount
- backup presence/expiry/reference size
- deletion event evidence
- exact image + digest
- original runtime config
- snapshot variables
- PGDATA
- credential continuity

Decision:
- `READY_FOR_MANUAL_REVIEW`
- これは**自動復旧承認ではない**

### recovery API readiness
read-only GraphQL schema introspectionで確認済み:
- `serviceCreate`
- `serviceInstanceUpdate`
- `volumeInstanceUpdate`
- `volumeInstanceBackupCreate`
- `tcpProxyCreate(applicationPort, environmentId, serviceId)`
- `tcpProxyDelete(id)`

したがって staged recovery は技術的に構成可能:
1. isolated `postgres-recovery` を作る
2. preserved volumeをattach
3. exact PostgreSQL 18 configで起動
4. temporary TCP proxyでread-only DB integrity audit
5. proxy削除
6. integrity PASS後のみStage 2で `postgres` promotionを別承認

### PR #277 — Stage 1 Draft
Open Draft:
- PR #277 `Draft: gated isolated Postgres recovery Stage 1`
- **DO NOT MERGE / DO NOT EXECUTE YET**
- PR eventではrecover jobはSKIP
- dedicated Stage 1 validation +既存4 CI = PASS

exact execution gate（将来、明示承認後のみ）:
- Issue #42 owner-only exact command:
  `/railway postgres-recovery-stage1 CONFIRM`

Stage 1では禁止:
- `postgres` へのrename/promotion
- Production consumer Variables変更
- service/volume delete
- backup restore / PITR
- Production model / LINE / N02 / Bao変更
- PR #169 activation

### PR #277 の現在のblocking review
Stage 1 codeはDraftのまま、以下をhardeningしてからactivation reviewする:
1. volume mutation直前に既存 `Pre-Security-Patch Backup` の存在・期限・reference-sizeをStage 1内でも再確認。
2. staging起動前に `DATABASE_PUBLIC_URL` を設定しない。TCP proxy未作成時の `RAILWAY_TCP_PROXY_*` 参照を避ける。
3. `serviceInstanceUpdate` 直後のunconditional `serviceInstanceRedeploy` を避け、不要な二重restartを防ぐ。

このhardeningはまだPR #277へ反映していない。
**PR #277はBLOCK / Draft hold。hardening完了後に再reviewする。**

### Open PR
- #169: temporary base-odds refresh — **Draft hold**
- #277: Postgres recovery Stage 1 — **Draft hold / manual recovery review**

### Production safety
以下は変更なし:
- Production v24 / FINAL
- LINE / BUY-WATCH-SKIP
- N01 / N02 / Bao
- coefficients / thresholds
- PR #169
