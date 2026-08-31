# boat-ai-v2 — Current Research State

更新日時: 2026-08-31 JST

予測精度・Shadow / Forward研究時だけ読む**現在状態**。履歴は持たない。

## 1. Production baseline
- Production: current v24 PRE → FINAL realtime → LINE → BUY / WATCH / SKIP
- 研究系はProductionと分離し、自動昇格しない。
- 比較baseline: motor2=33.0 fixed / boat2=34.0 fixed / PROB_TEMP=2.20
- このファイルを理由にProduction baselineを変更しない。

## 2. Opponent Pressure — head-only
Fixed:
- 1着確率だけへ反映
- coefficient=**1.0**
- 2着/3着conditionalはcurrent v24
- 後付けdate / venue / R-band filter禁止

Latest checkpoint:
- shadow **1,092R**
- evaluated **948R**
- pending **144R**
- Brier delta **-0.00017564**
- actual-ticket LogLoss delta **-0.00736051**
- actual-ticket rank delta **-0.251**
- R05-08は弱いが観測後除外しない

State: **PROMISING_RESEARCH_ONLY / PRODUCTION BLOCK**
Next: fixed coefficientのままForwardを増やし、十分な新規証拠後のみmanual review。

## 3. Racer Course Top3
Fixed:
- official racer × course top3 rate
- coefficient=**0.50**
- complete-case
- source created_at <=08:15 JST / deadline前
- first-write-wins
- Forward中に係数変更禁止

Latest checkpoint:
- rows **261**
- evaluated **220**
- pending **41**
- Brier delta **-0.00550111**
- LogLoss delta **-0.22471240**
- actual-ticket rank delta **-9.1409**

State: **BLOCK_MANUAL_REVIEW_ONLY / RESEARCH ONLY**

## 4. Exhibition ST
Fixed:
- beta=**-0.02**
- official beforeinfo only
- deadline **8〜15分前**
- BASE/ST 120 probabilities freeze
- collect時results / odds非参照
- first snapshot wins
- scheduler delay対策済み

Latest checkpoint:
- shadow **239**
- evaluated **208**
- pending **31**

State: **BLOCK_MANUAL_REVIEW_ONLY / PRODUCTION BLOCK**
Do not: beta再調整 / 後付けrace-band filter / Production・LINE接続。

## 5. Motor actual / GUARD05
Fixed:
- COUNT_MODE=**PRIOR_DAY**
- prior-day appearances <=**5** → motor2=33.0
- >=6 → actual motor_place2_rate
- official generation startをprimary source
- DB first-seenを公式開始日扱いしない

Latest checkpoint:
- rows **43**
- evaluated **39**
- pending **4**
- affected evaluated **0**

State: **BLOCK_MANUAL_REVIEW_ONLY**
Do not:
- affected=0で効果判定
- threshold 5 / PRIOR_DAYをForward途中で変更
- venue反転を見て後付け除外

## 6. Bao
Role: research / auxiliary。通常予想の代替ではない。

Fixed:
- Motor2 beta=**0.06**
- Exhibition beta=**0.06**
- formal evidenceはexact frozenのみ
- market earlyは6 boats / 120 tickets complete
- partial / mutable realtime evidenceをformal Forwardへ使わない

Promotion:
- gate到達でもautomatic Production promotion禁止
- manual review止まり
- 最新gate件数が必要な時だけ専用read-only auditを使う

## 7. N02
Fixed:
- prob rank 11〜20
- market rank 2〜5
- odds 3〜6
- R07〜R10
- any venue / event
- select mode EV

State:
- N02 CORE fixed
- N01 inactive
- Forward evidence蓄積優先

Do not:
- 候補不足を理由にodds / rank / R帯を後付け変更
- 同じOOSをtrainingとして再利用

## 8. 馬王型 / theoretical price
- 通常予想のプラスアルファ
- v24 raw probabilityをそのまま理論オッズ / EVへ使わない
- calibration確立前にProduction判断へ昇格しない
State: **AUXILIARY RESEARCH**

## 9. Promotion rule
全feature共通:
1. historical fitだけで採用しない
2. fixed OOS / walk-forward
3. frozen Forward
4. realized evaluation
5. day / venue / condition stability
6. manual review
7. Production changeは別PR

Observation後に都合のよいfilterを追加しない。

## 10. Priority after Ops stability
1. Opponent Pressure head-only
2. Racer Course Top3
3. Exhibition ST
4. GUARD05 affected Forward
5. Bao formal gate audit
6. 十分な証拠があるものだけmanual promotion review

## 11. Deep-history lookup
必要な時だけ:
- `PROJECT_HANDOFF.md`
- `PROJECT_HISTORY.md`
- `DEVELOPMENT_STATUS.md`
- relevant PR / commit

対象feature / PR / dateで部分検索し、全文取得しない。

## 12. Maintenance
- 目安: **180行以内**
- stale countは置換
- 過去countを時系列追記しない
- fixed rule / current evidence / state / nextだけ残す
- 詳細経緯はHISTORYへ
