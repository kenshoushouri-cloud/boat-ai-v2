# boat-ai-v2 Project History / Decision Log

更新日時: 2026-08-25 19:01 JST

このファイルは「何をやったか」だけでなく、**なぜ採用/却下したか**を残す常設decision logです。

現在地は `docs/PROJECT_HANDOFF.md` を優先してください。
このファイルは過去の判断を同じデータで再検討し直したり、却下済み案を理由なく復活させたりしないために使います。

---


<!-- RACER_COURSE_TOP3_FORWARD_MILESTONE_20260825 -->
## 0A. 2026-08-25 — Racer course top3: fixed OOS support → isolated Forward

- #241 decision: `NOT_READY_FOR_UNFILTERED_OOS`; mutable exact-date snapshot timestamps and uneven daily coverage prevent treating all stored rows as frozen morning evidence.
- #242 pre-registered complete-case OOS decision: `SUPPORTS_FIXED_FORWARD_SHADOW_RESEARCH_ONLY`. Three non-overlapping Aug windows all improved Brier/LogLoss/rank; aggregate n=2,299, Brier `-0.00608767`, LogLoss `-0.21143915`, rank `-5.0170`. Train-only selected coefficient was 0.50 in all three splits.
- Because 0.50 was the pre-registered grid ceiling, **do not** search larger coefficients on the same OOS. Freeze 0.50 for Forward.
- #243 decision: `KEEP_ISOLATED_FORWARD_SHADOW`. Dedicated first-write-wins table freezes BASE/COURSE 120-probability vectors plus all six source timestamps before outcomes. Automatic GitHub collection starts 06:45 JST and polls every 2 minutes for 2 hours; no Railway schedule/settings change.
- First live Forward capture: 9R written, invalid 0, pending 9. Promotion remains manual-review-only / Production BLOCK.
- No Production v24/FINAL/LINE/BUY-WATCH-SKIP, N02/N01, Bao, scoring-weight, Railway Variable/service schedule, or PR #169 change.

## 0. 長期方針

プロジェクトは当初から最終的に以下を目指している。

- 全場のデータ収集
- 事前予想
- 直前情報による再判定
- オッズを考慮した買い/見送り
- 結果照合
- 学習/バックテスト
- LINE通知
- 過学習を避けたForward/OOS検証

2026年春以降、予想は大きく2トラックで研究してきた。

1. 通常/安定予想系
2. 馬王型（理論価格・期待値型）

2026-08-24時点では、通常予想を主軸、馬王型をプラスアルファとする。

---

## 1. 2026-04-29: 馬王Z的な考え方を競艇へ応用

ユーザー要望:
- 条件別成績
- 指数化
- 期待値買い
- 見送り

を競艇AIへ入れる方向を検討。

この段階から「当たりそうな艇を選ぶ」だけでなく、**市場価格に対して割安か**を見る研究が始まった。

---

## 2. 2026-05-04: 安定モード / 馬王モードの2系統

過去設計:

### 安定モード
- 通常予想
- 比較的高い的中性/安定性を優先

### 馬王モード
- 穴狙い
- probabilityとoddsから期待値を見て選ぶ

当時の歴史的な例:
- stable EV >= 1.10
- ana/馬王 EV >= 1.35
- stable odds 3.5–25
- ana odds 12–80

これらは**当時の研究値**であり、現在のProduction閾値ではない。

関連古いコード:
- `runner_no_odds.py`
- `backtest_multi_patterns_v3.py`
- `daily_selector_v19.py`
- `UPGRADE_PLAN.md`

重要な設計思想:
- 着順/組合せ確率
- オッズ/EV
- 資金配分

を分離する。

---

## 3. 2026-05〜06: 全場データ/補修の拡大

全場全Rの履歴を増やし、旧5場1R等の欠損補修を実施。

旧ログ例:
- 2025-05旧5場1R補修
- races 120
- odds 14,400
- success 82

その後、月次全場補修へ拡大。

重要な学び:
- 非開催/データなしとparser失敗を区別する。
- race_id / venue code / race_noの正規化が重要。

---

## 4. 2026-06〜07: Supabase → Railway PostgreSQL 移行

Supabase Free容量問題を受け、本番DBをRailway PostgreSQLへ移行。

決定:
- Supabaseは削除。
- Railway PostgreSQLを唯一の本番DB Source of Truthとする。

Production:
- Railway project `boat-v2-postgres`
- PostgreSQL service `postgres`

正しいentries table:
- `v2_race_entries`

`v2_entries` は存在しない/誤りとして何度か修正した。

---

## 5. 2026-07: 締切時刻/場コード/取得基盤の修正

### deadline parser bug
`parse_deadline_time(html)` が対象race_noではなく最初の締切時刻を拾う問題を修正。

結果:
- 同一場の1R〜12Rが同じ締切で上書きされる問題を解消。

`v2_races`へ:
- `deadline_time`
- `deadline_at`

を追加。

### venue code
公式場コードの辞書誤りを修正。

例:
- 06 浜名湖
- 08 常滑
- 09 津
- 23 芦屋

---

## 6. 2026-07: morning/day/night window pipeline

締切の早いレースへ対応するため、1日1回の取得から時間帯分割へ。

設計:
- morning
- day
- night

各枠:
1. odds取得
2. PRE
3. notification

DRY_RUNで3枠すべて正常完走を確認。

代表テスト:
- morning success 12
- day success 68
- night success 69

---

## 7. 2026-07-30: FINAL chain / invalid trifecta修正

FINAL chainを追跡:

`run_final_pg.py`
→ `v25_final_realtime_pipeline_pg.py`
→ `v21_realtime_collector_pg.py`
→ `run_v22_targeted_pg.py`
→ `v22_exhibition_shadow_pg.py`
→ `v23_line_notifier_batch_pg.py`

`v21_realtime_collector_pg.py`:
- invalid trifecta ticket filteringを追加
- version `2026-07-30 ticket-validation-v1`

目的:
- 不正ticketが後工程へ入らないようにする。

---

## 8. 2026-08: historical quality / feature researchへ移行

単にデータを集める段階から、
- どの特徴が実際にOOSで効くか
- Productionへ入れる価値があるか

を厳密に分けて検証する方針へ。

原則:
- 1 feature at a time
- train-only learning
- chronological OOS
- Forward Shadow
- Production isolation

---

## 9. PR #80: モーター成熟度のsource readiness

テーマ:
- モーター2連率等を使う際、交換/使用開始からの成熟度をどう扱うか。

重要決定:

**DB first-seen dateを公式のmotor use-start dateとして扱わない。**

理由:
- project historical boundaryのleft censoringがある。
- DBに最初に現れた日 != 本当の使用開始日。

次gate:
- official use-start dateを取得してからmaturity weightingを考える。

このルールは2026-08-24のモーター実測値改善後も有効。

---

## 10. PR #83 / #84: 艇国DBと公式のモーター開始日照合

### PR #83
BOAT RACE公式と艇国DBのautomated cross-checkを試行。

結果:
- 公式: HTTP 200
- 艇国DB: GitHub Actions環境からtimeout

データ不一致ではなくexecution pathの問題。
PRはmergeせずclose。

### PR #84
外部確認済み艇国DBcheckpointを使い、公式event/motor pageで再確認する方式へ。

Source policy確立:
- BOAT RACE official = automated primary
- 艇国DB = secondary externally verified cross-check

この方針を今後も維持。

---

## 11. PR #85: 相手構成feature readiness

ユーザーが以前から検討していた:

**選手がそのコースに入った時、他コースの選手ランク構成との相性**

をデータ化。

評価粒度:
- racer × own lane × opponent lane × opponent class
- exact five-opponent pattern
- aggregate opponent class pattern
- global own-class × own-lane × opponent-class × opponent-lane

readiness結果:
- participant rows 384,660
- racers 1,649
- individual pair median n=9
- global class/lane median n=3,387

判断:
- exact/individualは母数不足になりやすい。
- global class/lane interactionは十分強い母数。

---

## 12. PR #86 / #87 / #93: Opponent Pressure OOS

racer-specificおよびglobal opponent effectsをchronological OOSで検証。

### global Opponent Pressure
train-onlyで:
- own_class
- own_lane
- opponent_lane
- opponent_class

のeffectを学習し、5人の相手から平均pressure scoreを作る。

Splits:
- 2026-03-31
- 2026-04-30
- 2026-05-31

3splitすべてで:
- win Brier改善
- top3 Brier改善
- quartile ordering良好

例:
- win improve 約0.00135
- top3 improve 約0.0038
- low-score vs high-score actual win spread 約0.137
- top3 spread 約0.21

判断:
- racer-specificよりglobal baseline + shrinkageが安全。
- Shadow候補へ進める価値あり。

---

## 13. PR #88〜#94: Opponent Pressure Shadow

### PR #88
Shadow-only collector。

### PR #90〜#92
JSONBよりcompact typed arraysの方がstorage効率が高いことを実測。

### PR #91
`v2_opponent_pressure_shadow_v2` を作成。

### PR #94
日次Forward収集を追加。

Schedule:
- 07:15 JST
- morning data preparation後
- earliest 08:30 race前

安全設計:
- complete six-lane cards必須
- dry-run preflight
- post-write verification
- Production consumerなし
- LINEなし

2026-08-24 PR #189で再health確認:
- 8/22 156/156
- 8/23 168/168
- 8/24 144/144
- total 468 rows

つまりこの研究は今も継続中。

---

## 14. Bao research: モーター/展示をForwardで検証

Baoではmodel probabilityを市場のearly/late priceと比較するShadow researchを構築。

重要な設計:
- exact complete snapshotsのみ
- early market
- Motor2 adjustment
- exhibition adjustment
- late market proxy
- realized result

係数:
- Motor2 beta 0.06
- Exhibition beta 0.06

重要:
- tiny sampleでProductionへ入れない。
- mutable realtime timestampをformal frozen evidenceにしない。

Gate:
- Motor2 market pair 30
- exhibition pair 30
- Motor2 realized 30
- exhibition realized 30

2026-08-24夕方:
- market 52
- exhibition proxy 43
- Motor2 realized 13
- exhibition realized 7

Promotion BLOCK。

---

## 15. 2026-08-23〜24: Bao auto capture

手動smokeだけではcapture windowを逃すため、一時的なauto captureを追加。

特徴:
- every 5 minutes schedule
- internal loop
- exact date gate
- concurrency control
- frozen completeness gates

目的:
- Forward sample確保

Production predictionとは隔離。

---

## 16. PR #159 / #163 / #165: PRE repeat safety

PREを再実行する際のLINE重複防止研究。

- notification dedupe scaffold
- race-ticket dedupe
- PostgreSQL integration test

Productionでの再実行を軽率に有効化せず、安全性を先に作る方針。

---

## 17. PR #162 / #164 / #166〜#174: base odds completeness

課題:
- PRE前にbase oddsが未完全なraceがある。

作成:
- window refresh runner
- read-only planner
- Bao/base odds gap comparison
- manual confirmed refresh
- live parser probe
- PRE repeat read-only plan
- missing odds sensitivity
- low-core observability

重要結果:
- official pageからmemory上でexact120を取れるケースは多い。
- つまりparser固定バグよりtemporary/timing fetch gapの可能性。

しかし:
- incomplete raceをmemory exact120で補ってもPRE candidate 0。
- ready racesでも low_core_total=0。

結論:
- base odds完全性 = 改善価値あり
- prediction/notification value = まだ証拠なし

PR #169 temporary 10-min refreshはDraft保持。

---

## 18. PR #175〜#180: N02 scarcity診断

N02 Forwardがほぼ増えない原因を追跡。

N02:
- pr11–20
- mr2–5
- odds3–6
- R07–10

### #175/#176
Forward evaluator backlogではなく、実際にrowが少ないと判明。

### #177 v24 low candidate diagnostic
7日:
- total 1056
- ready 1049
- low_core 4

triple intersectionが非常に希少。

### #180 live opportunity
rank条件を満たすticketはあるが、odds3–6がほぼない。

ボトルネック = **odds band**。

---

## 19. PR #181: N01へ広げても解決しない

N01:
- pr11–25
- mr2–5
- odds3–6
- R07–12

live compare:
- rank-compatibleは増える
- exact odds3–6は0

判断:
- race/rank range拡張だけではscarcity解消しない。
- N01 inactive維持。

---

## 20. PR #182 Phase9 OOS extension

N02 COREがない場合だけN01 range extensionを使うfixed test。

Overall:
- CORE n13 hits4 ROI173.8%
- EXT n15 hits2 ROI65.3%
- UNION n28 hits6 ROI115.7%

OOS1:
- EXT ROI 0%

OOS2:
- EXT ROI 122.5%

期間で正反対。

判断:
- 頻度を増やすためだけにN01 extensionを採用しない。

---

## 21. PR #183 Phase10 fixed filters

Phase9 extensionを:
- motor edge
- head motor3
- head avg ST

等の事前固定フィルタで救えるか検証。

結果:
- 全filters OOS1 0 hit / ROI0
- OOS2は高ROI

一部overallでは良く見えるがperiod robustnessなし。

判断:
- 採用しない。
- N02 COREを変えない。
- 同じOOSでthreshold searchをしない。

---

## 22. PR #184: 馬王型 probability/value calibration OOS

v24 probabilityとmarket priceを使った理論価格の妥当性を確認。

重要結果:
- 高value ratioほどROIが上がる関係がない。
- value ratio 1.5+など高value域でむしろ悪化。
- model probabilityはabsolute calibrationが不足。

N02は条件抽出としてpositiveな可能性があるが、model absolute probabilityとは別問題。

判断:
- v24 raw probabilityを馬王型理論確率として直接使わない。

---

## 23. PR #185: frozen PRE Shadow value calibration

実際のPRE時点frozen Shadowで再検証。

傾向:
- value ratioが高くなるほど成績改善しない。
- AI順位がmarket順位より大きく上のticketsも成績が悪い。

ユーザー認識:
- 「馬王型はAI評価が高いほど悪くなったと思う」

検証結果と整合。

2026-08-24方針:
- 馬王型は通常予想のプラスアルファ。

---

## 24. PR #186: actual motor/boat rate OOS

v24比較式内のfixed:
- motor=33
- boat=34

を、entry actual ratesへ置き換えた固定formula comparison。

2026-07-01..2026-08-15:
- n=7,184
- BASE LL 4.40602095
- MOTOR 4.40303973
- BOAT 4.40531781
- BOTH 4.40232791

モーターが主要改善要因。

ただしProduction変更はしない。

---

## 25. PR #187: motor vs boat ablation

motorだけ / boatだけ / bothを分離。

7,184R:
- motor delta LL -0.00298123
- boat delta -0.00070314
- both -0.00369304

winner rankもmotorで明確に改善。

判断:
- motor actual rateはpromising。
- boatの寄与は小さい。

---

## 26. PR #188: prior-month stability

2026-04-01..2026-06-30の別期間で固定ablation。

n=13,525:
- BASE LL 4.41818166
- MOTOR 4.41508752
- BOAT 4.41811265
- BOTH 4.41501772

Delta:
- motor -0.00309414
- boat -0.00006902
- both -0.00316395

winner rank:
- BASE 29.9449
- MOTOR 29.7396
- BOAT 29.9488
- BOTH 29.7353

結論:
- motor改善は7–8月だけの偶然ではなく、4–6月でも再現。
- boat単独はほぼ価値なし。

ただし、ここでユーザーから重要な指摘:
- **モーター交換時期に注意**

よって次はmaturity-adjusted OOS。

---

## 27. PR #189: Opponent Pressureの流れを再発見/再接続

別チャットの内容を見直した結果、
「選手×他コース選手ランク相性」は既にShadow化・日次収集済みと再確認。

新しいread-only health command:
- `/railway opponent-pressure-forward-health`

結果:
- 8/22 156/156
- 8/23 168/168
- 8/24 144/144
- integrity all pass

判断:
- 既存研究を重複開発せず、realized Forward evaluationへ進める。

---

## 28. 2026-08-24: 常設引き継ぎを作る決定

チャットが長くなり、別チャット間で:
- モーター交換時期
- 艇国DB
- Opponent Pressure
- 馬王型の位置付け

等の重要な過去判断を拾い直す必要が発生。

ユーザー要望:
- いつでも引き継ぎできる形にしたい。

決定:
- `docs/PROJECT_HANDOFF.md` = current state
- `docs/PROJECT_HISTORY.md` = decision history
- `docs/DEVELOPMENT_STATUS.md` = detailed experiment status
- Issue #42 = Railway runtime/audit log

この4層で管理する。

---

# 採用済み判断まとめ

## 採用/維持
- GitHub main = code Source of Truth
- Railway PostgreSQL = production data Source of Truth
- `v2_race_entries`が正しいentries table
- morning/day/night window architecture
- invalid trifecta validation
- opponent pressure Shadow daily forward
- Bao frozen Forward evidence collection
- strict chronological OOS / Forward
- BOAT RACE公式をmotor use-start primary source
- 艇国DBをsecondary cross-check
- motor actual rateを次の重要研究候補とする
- 馬王型は通常予想のプラスアルファ

---

# 現在却下/保留している判断

## N01 activation
却下/保留理由:
- Phase9 extension overall weak
- OOS期間不安定

## Phase10 extension filters
却下理由:
- OOS1全滅、OOS2のみ強い
- robustnessなし

## N02 odds/rank threshold loosening
保留理由:
- scarcityだけを理由に同じデータで調整するとoverfit

## 馬王型 raw v24 probability EV
却下理由:
- calibration/value monotonicityがない
- AI高評価側の実績悪化

## motor actual rate Production直投入
保留理由:
- 強いOOS改善は確認
- しかし交換/使用開始/maturityをまだ組み込んでいない

## boat actual rate feature
優先度低:
- motorに比べ寄与極小
- prior periodではwinner rankもわずかに悪化

## PR #169 auto base refresh
Draft hold:
- completeness改善
- PRE candidate recovery evidenceなし

## Bao Production promotion
BLOCK:
- realized result gates未達

---

# 失敗からの重要ルール

1. **DB first-seenを公式開始日と決めつけない。**
2. historical final oddsをPRE-time frozen oddsとして扱わない。
3. mutable realtime snapshotをfrozen Forward evidenceとして扱わない。
4. partial 120 ticket dataをcompleteとして使わない。
5. 候補が少ないだけでthresholdを緩めない。
6. OOSを見た後に同じOOSへ合わせてtuneしない。
7. proxy improvementだけでProduction promotionしない。
8. LINE/BUY/WATCH/SKIPをShadow研究から直接変更しない。
9. Railway Variables/settingsを研究PRで変更しない。
10. 過去に同じ研究が存在しないか、repo/PROJECT_HISTORYを確認してから新規実装する。

---

# 今後のhistory追記形式

Material decisionごとに以下を追記する。

```markdown
## YYYY-MM-DD: テーマ

### 仮説
...

### 検証
- train:
- OOS:
- Forward:

### 結果
...

### 決定
- ADOPT / KEEP_SHADOW / REJECT / HOLD

### Production影響
- none / manual review required / changed via PR #...
```

数値が更新されるだけで判断が変わらない場合は `DEVELOPMENT_STATUS.md` を更新し、判断が変わる時だけこのdecision logへ追記する。

以上。


---

<!-- HANDOFF_MILESTONE_20260824_OPP_MOTOR -->
## 2026-08-24 20:49〜21:10 JST — 相手構成Forwardとモーター交換成熟度を再検証

### Opponent Pressure: historical OOSから実結果Forwardへ
過去チャットで検討していた「自選手のコース × 相手コース × 相手級別」の相性を、既存Opponent Pressure Shadowで実結果評価。

- PR #191: realized Forward evaluator追加。
- 初回0評価から、現行nightly結果の正本が `v2_results(first_lane..sixth_lane)` であることを再確認。
- PR #192: evaluatorの結果結合先だけを現行構造へ修正。
- 292Rでwin Brier / top3 Brier / winner logloss / winner rankのOverall 4指標がすべて改善。

**Decision:** `PROMISING_FORWARD_RESEARCH_ONLY`。通常予想系の有力補助候補だが、2日中心の292RではProduction採用しない。Forward継続。

### モーター交換時期の扱いを明示
ユーザー指摘「モーターは交換時期に注意」を受け、DB first-seenではなく公式使用開始日を使う方針を再確認。

2026-08-24公式確認subset:
- 江戸川 2026-05-11
- 多摩川 2026-04-18
- 住之江 2026-03-23
- 鳴門 2026-04-11
- 唐津 2025-09-05

Source policyは **公式一次 / 艇国DB二次照合 / DB first-seen診断のみ**。

### PR #193: 世代開始後の日数別
5,095Rでactual motor2の効果を固定比較。
0–14日から121日+まで全age binのOverall loglossが改善。

**Decision:** 「交換直後を一律に弱める」補正を却下。venue×ageには悪化区間があるため、より直接的な個体母数へ進む。

### PR #194: 個体の事前出走回数別
6艇のうち最もprior appearanceが少ないmotorを基準に固定bin化。current raceを加算する前に評価し、same-race leakageなし。

- P00–04 n438: logloss -0.00240089、rank +0.0776
- P05–09 n377: -0.00719944
- P10–19 n573: -0.00454600
- P20–39 n1081: -0.00439443
- P40+ n2626: -0.00205133

**Decision:** 全binでlogloss改善のため、低母数を理由にactual motor2を一律除外しない。一方、場別には低母数で悪化例があるため、このデータから後付けcutoff/shrinkage係数を作らない。Forwardで場別再現性を確認する。

### Production safety
PR #191〜#194はすべてread-only audit/評価。Production予想、LINE、Railway Variables/settings、v24/N02 threshold、Bao係数/promotion、PR #169は変更していない。

---

<!-- HISTORY_MILESTONE_20260825_GUARD05_FORWARD -->
## 2026-08-25 — 交換直後Motor2を保護するGUARD05をForward研究へ固定

### 仮説
actual motor2は長期間・別期間でv24 probabilityを改善したが、交換直後の個体では母数不足による不安定性があり得る。

ユーザー要件「モーターは交換時期に注意」に沿い、成熟したモーターの実測値の利点を残したまま、非常に若い個体だけを保護できるか検証する。

### PR #225: 一律shrinkage family
事前固定:
- BASE=33.0
- FULL=actual motor2
- K03/K06/K12/K24=`33 + n/(n+K)*(actual-33)`

3期間×公式generation確認済み5場、2,963R。

結果:
- K03〜K24はBASEより改善。
- しかしLogLoss/Brierでは**FULLに3/3期間負け**。
- 一律shrinkageは支持されない。

一方、固定maturity slice P00–05 / 103Rでは:
- BASE LL `4.57884059`
- FULL LL `4.58098931`

つまり交換直後sliceだけではactual motor2をそのまま信じる方が悪かった。

**Decision:** `REJECT_GLOBAL_SHRINKAGE`。一律補正は採用しない。

### PR #226: lane-local GUARD05候補
固定候補:
- lane motor prior appearances <=5 → motor2=33.0
- 6+ → actual motor2

2,963R Overall:
- GUARD05 vs FULL LogLoss **-0.00017390**
- Brier **-0.00000432**
- actual ticket rank **-0.0145**

P00–05 / 103R:
- vs FULL LogLoss **-0.00500259**
- Brier **-0.00012438**
- rank **-0.4175**

P06+はFULLと同じなので、成熟motorのメリットを壊さない。

ただしこのルールは同じhistorical screenから生まれたため独立validationではない。

**Decision:** `FREEZE_CANDIDATE_REQUIRE_NEW_FORWARD`。

### PR #227: 結果に依存しない成熟度カウント
歴史評価のprior counterに同日進行の影響が混ざる可能性を排除するため、結果を一切使わない2方式を固定比較。

- CARD_ORDER: race-card順で先に存在するカードを数える
- PRIOR_DAY: TARGET_DATEより前の日付だけ数える

Overall FULL比:
- CARD_ORDER LL **-0.00014907** / Brier **-0.00000398** / rank **-0.0152**
- PRIOR_DAY LL **-0.00009457** / Brier **-0.00000291** / rank **-0.0084**

両方式とも3/3期間でFULLよりLogLoss/Brier/rank改善。

**Decision:** Forwardでは最も保守的な **PRIOR_DAY** を固定。same-day未実施raceを成熟度に数えない。

### PR #228: 独立Forward Shadow
新テーブル:
- `v2_motor_guard05_forward_shadow`

既存Motor2 candidate Shadowへ混ぜる案は却下した。既存レポートがrun_classを完全隔離しておらず、同じテーブルへ別モデルを入れると集計を汚す可能性があったため。

1 race 1 rowで保存:
- official generation metadata
- prior_day_counts[6]
- actual_motor2[6]
- guard_flags[6]
- BASE/FULL/GUARD05 probabilities[120]

Forward integrity:
- collectorはresults/oddsを読まない
- deadlineより3分以上前のみwrite
- `snapshot_at < deadline_at`
- first snapshot wins (`ON CONFLICT DO NOTHING`)
- collector default disabled / DRY_RUN
- health reportはread-only

Issue #42 commands:
- `/railway motor-guard05-forward-collect CONFIRM`
- `/railway motor-guard05-forward-health`

**Decision:** `KEEP_ISOLATED_SHADOW`。

### 2026-08-25: 最初のconfirmed Forward snapshot
PR #228 merge後、owner-only Issue #42 commandからwrite。

- payloads 12
- write rows 12
- invalid 0
- pending 12
- affected races 0
- guard lanes 0

この12RはGUARD05=FULL。効果比較のaffected母数ではない。

**Decision:** collector/integrityの初回writeは成功。効果判断は保留。

### PR #229: 毎朝07:20 JST自動収集
GitHub Actions schedule:
- `20 22 * * *`
- 07:20 JST daily

Railway service scheduleを増やさず、独立GitHub Actionsから既存confirmed collectorを実行する。
Concurrencyで重複runを直列化し、first snapshot ruleを維持。

**Decision:** `ADOPT_FORWARD_COLLECTION_ONLY`。

### Production影響 / 現在のgate
- Production v24: **変更なし**
- motor2 fixed33 in Production: **変更なし**
- LINE / BUY / WATCH / SKIP: **変更なし**
- Railway Variables/settings/schedules: **変更なし**
- N02/N01/Bao: **変更なし**
- PR #169: Draft hold継続

GUARD05 status:
- **KEEP_SHADOW**
- **Production promotion = BLOCK**

次のgate:
- 新規chronological Forwardの**affected races**が蓄積すること
- affectedでFULLよりLogLoss/Brier/actual-ticket rankが再現して改善すること
- 日別・場別でも大きく崩れないこと
- threshold=5 / PRIOR_DAY / probability coefficientsを途中で変更しないこと
- 十分な証拠後も自動昇格せずmanual reviewすること

---

<!-- HISTORY_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->
## 2026-08-25 12:45 JST — Opponent Pressure統合方式とMotor V12反転の判断

### Opponent Pressure: head-only mappingを研究本線として維持
既存PRを再監査し、v24三連単への統合はPR #202/#203の固定head-only mappingが最も根拠が強いことを再確認。

historical OOS 3splitではOverall Brier / LogLoss / ticket rankが全て改善したが、realized Forward 468Rでは:
- Brier **-0.00006135**
- LogLoss **-0.00183905**
- rank **+0.284**

R05-08と8/24に弱さがある。

**Decision:** `KEEP_FORWARD_RESEARCH`。日付/R帯/場を後付け除外しない。ProductionはBLOCK。

PR #231/#232で既存固定監査をIssue #42から再実行できるread-only bridgeとして整備した。

### PR #207 fixed log-odds transportを再評価
468R Overallでv24比:
- Brier **+0.00006538**
- LogLoss **+0.00093481**
- rank **+0.577**

**Decision:** `HOLD / NO_FORWARD_SUPPORT`。R09-12だけの良さからsubgroup採用しない。

### Motor V12 recent reversal
PR #220 holdoutでは5場Overall actual motor2が改善した一方、V12 / 36Rが3指標悪化。

PR #219を再確認するとV12 mature P21+はpre-holdout 3期間すべてLogLoss改善。
PR #233でvenue×dateを全セル固定表示した結果、V12 36Rは8/16-18の1節だけで:
- 8/16: 改善
- 8/17: 悪化
- 8/18: 悪化

**Decision:** V12を除外しない。直近小標本を見てvenue filterを作らない。actual motor2 / GUARD05はForward継続し、ProductionはBLOCK。

### Production impact
- none
- v24 / LINE / BUY-WATCH-SKIP unchanged
- Railway Variables/settings/schedules unchanged
- N02/Bao unchanged
- PR #169 Draft hold unchanged

---

<!-- HISTORY_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->
## 2026-08-25 17:54 JST — Exhibition STをcurrent v24上の固定Forward研究へ昇格

### 仮説
展示ST順位が古いBao market baselineだけでなく、current v24の三連単確率へincremental valueを持つかを、過去に確定した係数を動かさず検証する。

### PR #235: fixed future OOS
BASE=current Production PRE v24相当（motor2=33、boat2=34、PROB_TEMP=2.20）。
ST scoreはPR #122の最初のtraining cutoffで決まった:
- z(-start_timing_rank)
- 1着/2着/3着 weight 1.0/0.6/0.3
- beta **-0.02固定**

2026-01-01..08-22 / 34,697R:
- Brier **-0.00001292**
- LogLoss **-0.00041811**
- rank **-0.0142**
- LogLoss改善 4/4 fixed windows、8/8 months

**Decision:** `PROMISING_FIXED_OOS_REQUIRE_FORWARD`。効果量は小さいが期間一貫性がある。race-band/venue差を見た後のfilterや係数調整はしない。

### PR #236: isolated frozen Forward Shadow
専用 `v2_exhibition_st_forward_shadow` を追加。

Forward integrity:
- official beforeinfoのみ
- deadline 8〜15分前
- results/odds非参照
- beta=-0.02固定
- BASE/ST 120確率を保存
- first snapshot wins
- Production/LINE consumerなし

初回confirmed collectionは3R、invalid/timing/source error 0、all pending。

**Decision:** `KEEP_ISOLATED_FORWARD_SHADOW`。

### PR #237: scheduled collection
8〜15分前の7分幅windowを手動実行だけで取りこぼさないため、GitHub Actionsを08:00〜21:59 JSTに5分間隔で追加。

初回専用CI failureはworkflow内の禁止語assertが自分自身へmatchする検査バグ。Production/collector不具合ではない。self-matchを除去後、主要5 CIが全PASSしsquash merge。

**Decision:** `ADOPT_FORWARD_COLLECTION_ONLY`。

### 同時点の既存研究gate
Opponent Pressure head-only 468RはBrier/LogLoss改善、rank悪化でmixed。
- `KEEP_FORWARD_RESEARCH`
- Production BLOCK
- R05-08/date filterを後付けしない。

GUARD05は12 frozen rowsすべてpending、affected evaluated 0。
- `KEEP_SHADOW`
- manual review only
- PRIOR_DAY / threshold 5固定。

### Production impact
- Production v24 / FINAL: **変更なし**
- LINE / BUY / WATCH / SKIP: **変更なし**
- Railway Variables/settings/service schedules: **変更なし**
- N02/N01/Bao: **変更なし**
- PR #169: **Draft hold継続**

次のgateは、Opponent Pressure / GUARD05 / Exhibition STの各fixed Forwardが新規結果で再現性を示すこと。十分な証拠後も自動昇格せずmanual reviewする。

---

<!-- HISTORY_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->
## 2026-08-25 18:28 JST — Exhibition ST ForwardのGitHub scheduler遅延を収集loopで吸収

### 観測
PR #237の5分cronはmainへ正常mergeしたが、最初のschedule eventは18:21 JSTまで遅延した。
jobは成功したものの156Rすべて8〜15分window外でwrite 0。

**Decision:** 5分cron頻度だけでは7分幅Forward windowのchronological evidenceを保証できない。

### PR #239
既存Baoで使っているdelay-resilient internal loopを、Exhibition ST collectorだけへ適用。
- 07:00 JSTからtrigger可能
- 2分loop
- 90分継続
- concurrency serial hand-off

collector自体のbeta=-0.02、8〜15分window、official-beforeinfo-only、first-write-winsは不変。

**Decision:** `ADOPT_DELAY_RESILIENT_FORWARD_COLLECTION`。
これはモデル調整ではなくForward evidence acquisitionの欠損対策。windowを広げたりpost-hoc dataを許可したりしない。

### Production impact
- Production v24 / FINAL: none
- LINE / BUY / WATCH / SKIP: none
- Railway Variables/settings/service schedules: none
- coefficient / threshold / N02 / N01 / Bao: none
- PR #169: Draft hold



---

<!-- HISTORY_MILESTONE_20260830_POSTGRES_SERVICE_LOST -->
## 2026-08-28〜30 — Railway Postgres service消失を確認、Volume保全優先の復旧フェーズへ

### 発端
TOTO用Railway Project作成中にRailway Web UIが `Oh no! Looks like the page derailed` となり、同時期にboat-ai-v2でもDB系cronが失敗。

初期調査では:
- Railway Project Token connection: SUCCESS
- environment config: read SUCCESS
- cron側Variable key `DATABASE_URL`: 存在
- ただし実行時 `DATABASE_URL が必要です` でcrash
- `railway variable list --service postgres`: FAIL

当初はRailway側の一時障害も疑い、設定変更せず監視した。

### 2026-08-30 UI + Bridgeで構造異常を確定
Railway Project Canvasで:
- application/cron servicesは存在
- **`postgres` serviceが存在しない**
- **`postgres-volume` のみ残存**

過去Bridge inventoryでは14 services（postgres含む）だったが、現在13 services。
したがって単なる一時接続障害ではなく、**Postgres serviceが失われ、Volumeがdetachedになった状態**へ診断を更新。

### データ保全状況
Railway UI:
- `postgres-volume`
- usage 約3.76GB / max 5GB
- region US West
- unmounted
- existing `Pre-Security-Patch Backup` 約3.5GBを確認

**Decision:** Volume/backupは現状維持。
Wipe/Delete/安易なmount/recreateを禁止。

### DB参照診断
主要serviceの `DATABASE_URL` keyは残るがresolved valueは空。
read-only診断:
- learning-all: empty
- final-check: empty
- data-prepare: empty
- window-night: empty
- config-layer resolved URL: NO

これは `${{postgres.DATABASE_URL}}` の参照先service欠落と整合。

### Volume file read-only diagnostic
PR #246でdetached volumeから `PG_VERSION` を読む専用workflowを追加。
- Railway設定変更なし
- Volume書き込みなし
- Production service deployなし

結果:
- root list FAIL
- /pgdata list FAIL
- PG_VERSION unreadable

**Interpretation:** CLI file API failureであり、Volume消失判定ではない。UI usage 3.76GBが残っているためデータ存在を優先的に信頼。
Postgres major versionは未確定。

### Production impact
DB依存serviceの多くがCRASHED。
特に:
- cron-data-prepare
- cron-final-check
- morning/day/night windows
- cron-nightly-results
- cron-daily-report
- cron-racer-course-stats

Production判定/LINE/データ収集は正常運用とみなさない。

### Recovery policy
**NO_DESTRUCTIVE_RECOVERY_WITHOUT_VERSION_AND_DATA_GUARDS**

復旧は:
- Volumeを残す
- backupを残す
- 元Postgres version/configを特定
- 正規Postgres serviceを再構成
- compatible mount
- read-only integrity audit
- cron health audit
の順。

Productionモデル、係数、閾値、LINE、N02/Bao、PR #169には触れない。



---

<!-- HISTORY_MILESTONE_20260830_POSTGRES_RECOVERY_PREFLIGHT -->
## 2026-08-30 — Postgres 18/config回収、recovery preflight PASS、Stage 1はDraft hold

### 仮説
detached `postgres-volume` の中身を守ったまま、削除された元Postgresと同じmajor/configを再構成できれば、Production consumersを接続する前にisolated stagingでDB integrityを検証できる。

### 検証
read-only Railway CLI / GraphQL diagnosticsを段階追加。

確認した事実:
- `postgres` service absent
- `postgres-volume` READY / detached / 約3761.75 MB / us-west2 / mount `/var/lib/postgresql/data`
- `Pre-Security-Patch Backup` 3582 MB reference、2026-09-22まで有効
- 2026-08-28にDeployment / ServiceInstance removed event
- original image `ghcr.io/railwayapp-templates/postgres-ssl:18`
- exact digest `sha256:e617e80d34d40def28ab197662197acc5cd6c1dc120db9cf38d835a2386c226c`
- PGDATA `/var/lib/postgresql/data/pgdata`
- restart ON_FAILURE / max 10
- snapshot variable count 13 / credential continuity available internally
- DB URLsはRailway dynamic referenceで、old literal host依存なし

PR #270 preflight:
- 25/25 guard PASS
- `READY_FOR_MANUAL_REVIEW`

PR #276 TCP schema:
- `tcpProxyCreate` / `tcpProxyDelete` をread-only schemaで確認
- staged DB auditの一時接続手段を確保

### Stage 1設計
PR #277をDraft作成:
- owner-only Issue #42 exact CONFIRM
- scheduleなし
- workflow_dispatchなし
- `postgres-recovery` isolated service
- preserved volume attach
- exact PG18 config
- temporary TCP proxy
- read-only DB integrity audit
- proxy cleanup
- Stage 2 promotionは別承認

PR validation:
- dedicated Stage 1 validation PASS
- Critical Python syntax PASS
- V21 parser sanity PASS
- Production shadow isolation PASS
- Critical mojibake guard PASS
- recover jobはPR eventでSKIPPED

### 追加reviewで見つけたhardening
実行前に以下を必須修正:
1. existing backupをmutation直前にも再guard
2. TCP proxy作成前の `DATABASE_PUBLIC_URL` 設定を避ける
3. config update後のunconditional redeployを避け、二重restartを防ぐ

このhardeningはまだPR #277へ反映していないため、Stage 1 activationは引き続きBLOCKする。

### 決定
- `POSTGRES_RECOVERY_PREFLIGHT = PASS`
- `PR_277 = BLOCK_DRAFT_ONLY`
- `NO_RECOVERY_MUTATION_EXECUTED`
- `NO_PRODUCTION_RECONNECT`
- `REQUIRE_EXPLICIT_MANUAL_APPROVAL_AFTER_HARDENING`

### Production影響
none:
- DB serviceはまだ復旧していない
- Production consumersは未接続
- model / LINE / BUY-WATCH-SKIP / N01 / N02 / Bao / thresholds unchanged
- PR #169 Draft hold unchanged


---

<!-- HISTORY_MILESTONE_20260831_STAGE1_BACKUP_GUARD -->
## 2026-08-31 — Recovery Stage 1 hardening完了、manual backup 50%制限を反映

PR #277 Draftの追加安全監査を実施。

確認:
- original Postgres runtime/configは既にPostgreSQL 18として解決済み
- preserved `postgres-volume`: 約3.76 GB / 5 GB
- Railway公式仕様ではmanual volume backupはvolume容量の50%まで
- したがってStage 1内のfresh manual backup作成はineligibleになる可能性が高い

変更:
- `volumeInstanceBackupCreate` をStage 1から除外
- existing `Pre-Security-Patch Backup` をpresence / expiry / exact 3582 MBでguard
- volume attach直前に同backupを再guard
- `DATABASE_PUBLIC_URL` 事前設定なし
- explicit `serviceInstanceRedeploy` なし
- validationでmanual backup mutation不存在を強制

PR #277 head:
- `3a401f9d7e97beeb7ebb8470be50323a1d7b840b`

CI:
- Stage 1 workflow SUCCESS（validate PASS / recover SKIPPED）
- Critical Python syntax SUCCESS
- V21 parser sanity SUCCESS
- Production shadow isolation SUCCESS
- Critical mojibake guard SUCCESS

Railway read-only状態:
- bridge SUCCESS
- 13 services
- `postgres` absent
- `vars postgres` FAIL

Decision:
- **STAGE1_DRAFT_READY_FOR_EXPLICIT_MANUAL_APPROVAL**
- no merge
- no Stage 1 command
- no Railway recovery mutation
- no Production reconnect
- PR #169 hold


---

<!-- HISTORY_POSTGRES_RECOVERY_DIGEST_DRIFT_20260831 -->
## 2026-08-31 — Postgres recovery image tag driftを事前検出、deleted digest固定へ変更

PR #277 Draftのstatic safety reviewで、`ghcr.io/railwayapp-templates/postgres-ssl:18` が削除前と同一digestを指し続ける保証がない点を追加監査。

read-only GitHub Actions / GHCR確認:
- deleted deployment digest:
  `sha256:e617e80d34d40def28ab197662197acc5cd6c1dc120db9cf38d835a2386c226c`
- current `:18` digest:
  `sha256:8dbbfcb7fafacc22c01dc0c425c38793b5d0449163a3d178d3e3767d43e6f3ee`
- digest drift: CONFIRMED
- deleted digest availability: CONFIRMED

初回のlive-tag equality guardは安全側にCI failureし、危険を検出した。
その後Stage 1をdigest-pinned sourceへ変更:
- `ghcr.io/railwayapp-templates/postgres-ssl@sha256:e617...`
- PR時にpinned digest存在確認
- execution直前にも再確認
- deployment SUCCESS後にmetadata digest再確認

最新head `1debf573f83d54c6455deeb3e7b685ae38ccf164`:
- Stage 1 workflow SUCCESS
- Python syntax SUCCESS
- V21 parser sanity SUCCESS
- Production shadow isolation SUCCESS
- mojibake guard SUCCESS
- recover SKIPPED

Production / Railway mutationは一切実行していない。

Decision:
- `MUTABLE_TAG_RECOVERY = FORBIDDEN`
- `PINNED_DELETED_DIGEST = REQUIRED`
- `STAGE1 = DRAFT_AWAIT_EXPLICIT_APPROVAL`


---

<!-- HISTORY_POSTGRES_RECOVERY_STAGE1_SUCCESS_20260831 -->
## 2026-08-31 — Preserved Postgres volumeをisolated stagingで起動、DB integrity PASS

ユーザーの明示承認を受け、Stage 1 recoveryを実行。

GitHub:
- connectorのDraft解除mutation不具合によりPR #277をclose
- exact same audited headからPR #282を非Draft作成
- 5 CI SUCCESS後にmerge
- main merge commit: `b503b32a2c129dd0e8a6b47c954c906fa85689be`

Issue #42:
- `/railway postgres-recovery-stage1 CONFIRM`
- Actions run `33336008053`: SUCCESS

実行結果:
- isolated `postgres-recovery` created
- preserved `postgres-volume` attached
- exact deleted PostgreSQL 18 digestでdeployment SUCCESS
- PostgreSQL 18.6起動
- temporary TCP proxyでread-only DB audit
- proxy cleanup SUCCESS
- Production service `postgres` は作成/renameしていない
- Production consumer Variablesは変更していない

DB integrity:
- size 3,471,750,847 bytes
- v2_races 65,046
- v2_race_entries 390,276
- v2_results 64,902
- v2_odds_trifecta estimate 7,401,959
- odds table size 1,827,889,152 bytes
- latest race_date 2026-08-28
- pg_is_in_recovery=False

Post inventory:
- services 14
- postgres-recovery SUCCESS
- original postgres absent
- DB-dependent cronはまだCRASHED（Stage 1でProduction referenceを意図的に未接続）

Decision:
- **STAGE1_PASS_AWAIT_MANUAL_PROMOTION_REVIEW**
- Stage 2 promotion / Production reconnectは別の明示承認が必要
- model / LINE / BUY-WATCH-SKIP / N01 / N02 / Bao / threshold / PR #169 unchanged


---

<!-- HISTORY_POSTGRES_RECOVERY_STAGE2_COMPLETE_20260831 -->
## 2026-08-31 — Postgres Recovery Stage 2完了、Production DB参照と当日データ収集を復旧

Stage 1でpreserved `postgres-volume` を `postgres-recovery` に安全に接続しDB integrity PASS後、
Production consumersの再接続をStage 2として実施した。

### 初期rename案の失敗と安全側停止
当初は `postgres-recovery` を同一service IDのまま `postgres` へrenameする設計だった。

Issue #42:
- `/railway postgres-recovery-stage2 CONFIRM`

preflight / public endpoint / DB integrityはPASSしたが、
Railway Project Tokenによる `serviceUpdate(name=postgres)` は
`not_authorized` で拒否された。

重要:
- renameは実行されていない
- preserved volumeは移動していない
- DB再起動なし
- temporary TCP proxyはcleanup SUCCESS
- Production consumersはこの時点で再deployしていない

Decision:
**DO_NOT_FORCE_RENAME_WITH_PROJECT_TOKEN**

### Compatibility namespace方式へ変更
PR #289:
- real DB = `postgres-recovery`
- compatibility service = `postgres`
- compatibility serviceはVolumeを持たない
- DB関連Variablesは `postgres-recovery` へのRailway Referenceのみ
- real DB service / volume / pinned PostgreSQL digestを維持

Issue #42で再実行し:
- public TCP proxy作成
- `DATABASE_PUBLIC_URL` dynamic reference復元
- PostgreSQL 18.6 read-only integrity PASS
- compatibility `postgres` service作成
- alias isolation PASS

Result:
**STAGE2_PROMOTION_PASS_VERIFY_CONSUMERS**

### Production consumer relink
PR #292:
13 application/cron servicesの `DATABASE_URL` のみを
`postgres-recovery.DATABASE_URL` Railway Referenceへ変更。

安全条件:
- fixed allowlist
- `skipDeploys=True`
- literal secret copyなし
- 他Variable変更なし
- relink step自身ではredeployなし

Issue #42:
- `/railway postgres-recovery-stage2-relink CONFIRM`

Result:
- staged 13/13
- `STAGE2_RELINK_STAGED_VERIFY_BEFORE_REDEPLOY`

read-only DB reference診断後:
- postgres-recovery / postgres / 全application consumerでresolved URL確認
- config layer resolved URL = YES

### Production consumer redeploy
PR #295:
CLI redeployが確定しなかった固定10 serviceのみ、
GraphQL `serviceInstanceRedeploy` で再deployするguarded pathを追加。

Issue #42:
- `/railway postgres-recovery-stage2-redeploy CONFIRM`

Result:
- redeploy accepted **10/10**
- DB service / compatibility service変更なし
- volume / backup変更なし
- model / LINE / N01 / N02 / Bao / thresholds変更なし

post-redeploy inventory:
- services discovered: **15**
- `postgres-recovery`: SUCCESS
- compatibility `postgres`: present
- 全application / cron service: SUCCESS

Decision:
**STAGE2_PRODUCTION_CONSUMERS_RESTORED**

### 2026-08-31 recovery catch-up
Stage 2完了時点で通常前夜data prepareがDB障害期間中に欠損していたため、
PR #296で2026-08-31固定のmanual catch-up workflowを追加。

安全条件:
- owner-only exact CONFIRM
- `TARGET_DATE=2026-08-31`
- scheduleなし
- workflow_dispatchなし
- normal `run_daily_data_prepare_pg.py`
- `ODDS_IS_FINAL=False`
- result collectionなし
- model / LINE / threshold / volume / backup / service renameなし

実行結果:
- races 144
- entries 864
- results 0
- odds rows 1,399
- success 144
- process exit 0

07:55 JST today-health:
- races 144 / deadline_ready 144
- entries 864 / full6 144
- odds 1,399 rows / 65 races
- results 0
- `TODAY_HEALTH_RESULT=PASS_READ_ONLY`

morning/day/night oddsは締切前のためpartialだった。
これは復旧異常ではなく、通常window収集前の状態。

### 最終構成
- PostgreSQL実体: `postgres-recovery`
- preserved volume: `postgres-volume` -> `postgres-recovery`
- compatibility namespace: `postgres`
- consumer DATABASE_URL: recovered DBへのRailway Reference
- public endpoint: recovered DBのTCP proxy
- backup: existing `Pre-Security-Patch Backup` preserved

### 決定
**POSTGRES_RECOVERY_STAGE2_COMPLETE**

以後:
- compatibility構成を無計画にrename/deleteしない
- volume/backupをwipe/delete/restoreしない
- normal cronを追加変更せず稼働確認する
- morning window後にread-only healthを確認
- 異常がなければDB障害復旧フェーズを完了し、通常の予測精度改善へ戻る
- PR #169はDraft hold継続
