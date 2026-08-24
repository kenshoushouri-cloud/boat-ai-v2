# boat-ai-v2 Permanent Project Handoff

更新日時: 2026-08-24 21:10 JST

このファイルは、新しいChatGPTチャット・新しい担当者・長時間中断後でも、`boat-ai-v2` の現在地から安全に再開するための常設引き継ぎです。

**再開時は、このファイルに書かれたSHAや件数を現在値だと仮定せず、最初に GitHub main / open PR / Railway read-only health を再確認してください。**

関連資料:
- `docs/PROJECT_HISTORY.md`: これまでの判断・採用/却下理由の時系列
- `docs/DEVELOPMENT_STATUS.md`: Bao等の技術検証の詳細ログ
- GitHub Issue #42: owner-only Railway Bridge control/audit log

---

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
- individual pair groups: 181,490
- individual median n: 9
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
