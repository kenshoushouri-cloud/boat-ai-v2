# boat-ai-v2 — Current Research State

更新日時: 2026-08-31 JST

このファイルは予測精度・Shadow / Forward研究を行う時だけ読む。
履歴ログではなく、**固定ルール・現在の証拠・Promotion状態**だけを保持する。

## 1. Production baseline

Production本線:
- current v24 PRE
- FINAL realtime
- LINE
- BUY / WATCH / SKIP

研究系をProductionへ自動昇格しない。

比較研究で使っているcurrent v24相当baseline:
- motor 2-place rate: 33.0 fixed
- boat 2-place rate: 34.0 fixed
- PROB_TEMP: 2.20

Production baseline自体を、このstate fileを理由に変更しない。

## 2. Opponent Pressure — head-only

Purpose:
- 選手のown lane / classと相手lane / class構成を補助特徴量化

Current fixed research form:
- **head-only mapping**
- 1着確率だけへ反映
- coefficient = **1.0 fixed**
- 2着/3着conditionalはcurrent v24維持
- 後付けdate / venue / R-band filterを作らない

Latest compressed Forward checkpoint:
- shadow: **1,092R**
- evaluated: **948R**
- pending: **144R**
- overall Brier delta: **-0.00017564**
- actual-ticket LogLoss delta: **-0.00736051**
- actual-ticket rank delta: **-0.251**
- R05-08は弱いが、観測後除外はしない

State:
**PROMISING_RESEARCH_ONLY / PRODUCTION BLOCK**

Next:
- fixed coefficientのまま日数・場をまたぐForwardを増やす
- 十分な新規証拠が集まった時だけmanual promotion review

## 3. Racer Course Top3 Forward

Feature:
- official racer × course top3 rate

Fixed rule:
- coefficient = **0.50**
- source complete-case
- source created_at <= 08:15 JST
- deadline前
- first-write-wins Forward Shadow
- Forward中に係数を動かさない

Latest compressed checkpoint:
- rows: **261**
- evaluated: **220**
- pending: **41**
- COURSE vs BASE Brier delta: **-0.00550111**
- LogLoss delta: **-0.22471240**
- actual-ticket rank delta: **-9.1409**

State:
**BLOCK_MANUAL_REVIEW_ONLY / RESEARCH ONLY**

## 4. Exhibition ST Forward

Fixed rule:
- beta = **-0.02**
- official beforeinfo only
- deadline **8〜15分前**
- BASE / ST 120 probabilities freeze
- results / odds非参照でcollect
- first snapshot wins
- scheduler delay対策済み

Latest compressed checkpoint:
- shadow: **239**
- evaluated: **208**
- pending: **31**

State:
**BLOCK_MANUAL_REVIEW_ONLY / PRODUCTION BLOCK**

Do not:
- betaをForward中に再調整
- 後付けrace-band filterを作成
- Production / LINE consumerへ接続

## 5. Motor actual / GUARD05

Goal:
- actual motor2の有用性を使いつつ、交換直後の低母数だけ保護

Fixed Forward definition:
- COUNT_MODE = **PRIOR_DAY**
- prior-day appearances <= **5** → motor2 = 33.0
- >= 6 → actual motor_place2_rate
- official motor generation startをprimary source
- DB first-seenを公式世代開始日として使わない

Latest compressed checkpoint:
- rows: **43**
- evaluated: **39**
- pending: **4**
- affected evaluated: **0**

State:
**BLOCK_MANUAL_REVIEW_ONLY**

Critical:
- affected sampleが0の間はGUARD05効果を判定しない
- threshold 5 / PRIOR_DAY定義をForward途中で変更しない
- venue反転を見て後付け除外しない

## 6. Bao / Motor2 / Exhibition research

Baoは通常予想の代替ではなくresearch / auxiliary。

Fixed coefficients:
- Motor2 beta = **0.06**
- Exhibition beta = **0.06**

Evidence policy:
- exact frozen evidence only
- market early = 6 boats / 120 tickets complete
- partial evidenceをformal Forwardへ使わない
- mutable realtime snapshotを正式Forward evidenceへ使わない

Promotion:
- gate到達でもautomatic Production promotion禁止
- manual review止まり
- latest gate件数が必要な場合だけ専用read-only auditを実行し、古いHandoff全文は読まない

## 7. N02 / candidate research

N02 fixed:
- prob rank 11〜20
- market rank 2〜5
- odds 3〜6
- R07〜R10
- any venue / event
- select mode EV

State:
- N02 CORE fixed
- N01 inactive
- live scarcityのためForward evidence蓄積優先

Do not:
- 候補が少ないことを理由にodds band / rank / R帯を後付け調整
- 同じOOSをtrainingとして再利用

## 8. 馬王型 / theoretical price

Policy:
- 通常予想のプラスアルファ
- v24 raw probabilityをそのまま理論オッズ / EVへ使わない
- calibration確立前に「AI確率 × 市場オッズ」をProduction判断へ昇格しない

State:
**AUXILIARY RESEARCH**

## 9. Research promotion rules

どのfeatureも:
1. historical fitだけで採用しない
2. fixed OOS / walk-forward
3. frozen Forward
4. realized evaluation
5. day / venue / condition stability
6. manual review
7. Production changeは別PR

Observation後に都合のよいfilterを足さない。

## 10. Research priority after Ops stability

DB障害復旧・outage-gap確認が完了した後:
1. Opponent Pressure head-only fixed Forward
2. Racer Course Top3 fixed Forward
3. Exhibition ST fixed Forward
4. GUARD05 affected Forward
5. Bao formal gate audit
6. 十分な証拠があるものだけmanual promotion review

## 11. Deep-history lookup

過去の詳細が必要な時だけ:
- `PROJECT_HANDOFF.md`
- `PROJECT_HISTORY.md`
- `DEVELOPMENT_STATUS.md`
- relevant PR / commit

検索語を限定し、全文取得しない。

## 12. Maintenance rule

このファイルは現在状態だけ。
- 目安: 180行以内
- stale countは置換
- 過去のcountを時系列追記しない
- featureのfixed rule / current evidence / state / nextだけ残す
- 採用/却下理由の詳細はHISTORYへ
