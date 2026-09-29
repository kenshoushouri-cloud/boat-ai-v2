# 新競艇AI開発プロジェクト — Master Handoff

## LATEST OVERRIDE — 2026-09-29 17:13 JST

この文書を次チャットの最優先引き継ぎ資料として扱うこと。
古いSHA・Cron・ROI・件数は歴史的背景として扱い、作業開始時に必ず GitHub main / open PR / CI / Railway Production を再取得すること。

---

## 1. システム構築の目的

最終目的は、競艇3連単に対して、
- 結果を事前に見ない;
- 取得時刻を証明できる情報だけを使う;
- 候補・買い目・評価ルールを事前固定する;
- 長期的に ROI 100% 超を維持できる可能性を Forward で検証する;
- 良いバックテストではなく、再現可能な実運用証拠を積む;

という条件を満たす予測・選別システムを構築すること。

現在Production名称は **V4**。
研究上は、V4を基礎にした次世代構成を **V5 research candidate** として整理している。

V5の2026-10-15目標は、
「長期収益性の証明」ではなく、
**V5 core research candidate の仕様をfreezeして次のForward段階へ入れること**。

---

## 2. Source of Truth

### Code
GitHub repository:
`kenshoushouri-cloud/boat-ai-v2`

GitHub `main` をコードのSource of Truthとする。

handoff作成時点のmain:
`0dfe3518ea2789a701ffad90da170bf2b7d9f798`

ただし次チャット開始時に必ず再取得すること。

### Production data / runtime
Railway project:
`268a5b17-0712-440a-884d-27f7fa887a2d`

Production environment:
`5ffb02f6-5ec8-4268-9bda-8e30431ff625`

Railway PostgreSQLをProduction dataのSource of Truthとする。

Fallback dispatcher:
- service: `candidate-discovery-v4-fallback-dispatcher`
- service ID: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`

Nightly results:
- service: `cron-nightly-results`
- service ID: `cd1b51a4-93f4-43db-82a3-7995fbe5781c`

---

## 3. 作業権限

### 確認なしで継続してよい
- read-only監査
- historical / Forward research
- 結果リークのないbacktest / diagnostic
- Draft PR作成・更新
- CI
- docs / handoff更新
- safe evidence collection
- pure/offline contract設計

### 明示承認が必要
- Production-effect PR merge
- Railway Production Variables / Cron / service / volume / migration変更
- Production DB INSERT / UPDATE / DELETE / schema / VACUUM
- Production model / coefficient / threshold / candidate / selector / stake変更
- live Forward routeのProduction activation
- F-count live capture / persistence / schedule
- LINE real-send
- purchase activation / auto purchase
- paid / external action

### 禁止
- outcome後のhistorical F-count snapshot backfill
- historical F-count coefficient search
- recent_formのpost-outcome reconstruction
- formal V4 selector/rank/ticketsをF-count研究都合で変更
- threshold/countを利益や件数を作るために緩める
- Railway plaintext variable value enumeration/display
- `railway variable list`
- unavailable formal dayの後付け再構築
- auto purchase activation

---

## 4. 現在のProduction V4固定契約

変更禁止ではないが、変更には明示承認が必要。
V5 scope reviewまではbaselineとして扱う。

- Racer Course coefficient: **0.50**
- Opponent Pressure: **1.0 / first-place-only**
- Motor2 beta: **0.06**
- probability temperature: **2.20**
- selector signals:
  - `head_p1`
  - `head_margin`
  - `top3_mass`
  - `concentration`
- formal core: **TOP6 races**
- formal tickets: **TOP2 per race**
- formal selectorにodds/EVを使わない
- Course/Opponent/Motor欠損はneutral
- `purchase_action=false`

主な基礎入力:
- racer class
- national win rate
- national place2 rate
- local place2 rate
- average ST
- venue/course bias
- Racer Course
- Opponent Pressure
- motor place2 rate

---

## 5. 日次タイムスケジュール

### 朝 — prospective freeze
- source cutoff: **08:15 JST**
- nominal primary GitHub schedule: **08:16 JST**
- GitHub scheduled workflowは近日期待時刻から大幅遅延することがあり、信頼性が低い
- current Production fallback Cron: **08:25 JST**
- fallback service internally also currently assumes **08:25 checkpoint**
- availability hard-stopの代表値: **08:32 JST**
- provider-selected immutable formal artifactが締切前に取れた日だけ正式Forward evidenceに数える

重要:
**2026-09-29はformal artifact unavailable。再構築禁止。**

### 夜 — official result settlement
- nightly result Cron: **23:30 JST**
- recent start: approximately 23:30..23:34
- recent completion: approximately **23:38..23:42**
- combined Forward checkpointは **23:45 JST以降** が目安
- ただしtarget-day terminal readiness guardが最終判定で、未完了ならfail closed

Combined workflow:
`.github/workflows/research-forward-combined-checkpoint-manual.yml`

順序:
1. provider inventory / arbitration
2. immutable artifact hash validation
3. target-day terminal readiness
4. V4 read-only settlement
5. S03_M2 read-only checkpoint
6. combined review gates / V5 progress

---

## 6. Fallback timing incident — 最重要運用事項

### 2026-09-28
ユーザー明示承認によりRailway fallback Cronを:
- 08:25 -> **08:20 JST**
へ変更した。

### 2026-09-29 first live cycle
08:20 Cronは動いたが、dispatcher内部コードが旧08:25 checkpointのままだった。

Observed:
- dispatcher decision around **08:23:33 JST**
- result:
  `NOT_DUE / before_0825_checkpoint`
- fallback workflow_dispatchは作られなかった

Natural GitHub scheduleも大幅遅延:
- run `36513182505`
- created around **11:33 JST**
- deadline後のため正しくfail closed

結果:
- **2026-09-29 formal prospective artifact = UNAVAILABLE**
- reconstruct/backfill禁止
- 9/29 day-strength labelも作らない
- 9/29をV4 resolved dayやday-strength gateへ数えない

### Production rollback
Railway Cronは安全のため:
- 08:20 -> **08:25 JST**
へrollback済み。

Current Railway read-back at 2026-09-29 17:13 JST:
- Cron: `25 23 * * *` = **08:25 JST**
- latest dispatcher deployment:
  `0cc94e40-71af-4cb6-85c0-19e60532ea2e`
- status: **SUCCESS**
- pending work: none
- staged/unmerged config: none

### PR #452
Open Draft:
`Fix: align fallback dispatcher checkpoint to 08:20 JST`

- PR: #452
- head: `73dd7f593be1199edf32bb0710458548a6d2d32d`
- mergeable: true
- all CI: SUCCESS
- not merged

Changes:
- internal checkpoint 08:25 -> 08:20
- activation manifest alignment
- regression tests:
  - 08:19:59 => NOT_DUE / no GitHub call
  - exactly 08:20 => dispatch permitted

**前回の08:20承認は、この新しいcode+Cron activationを自動承認しない。**
Production再activationは新しい明示承認が必要。

---

## 7. 最新settled economics — through 2026-09-28

Canonical read-only refresh:
- workflow run `36538181451`
- job `109307018169`
- artifact `11018808467`
- digest `sha256:72eb6b5d309859f1b3ad82d886b2603c2006f59fb1af2365debbb97145cb6d21`

### Formal V4 TOP2
- resolved formal days: **8**
- settled races: **44**
- head accuracy: **63.6364%**
- bets: **88**
- hits: **12**
- investment: **8,800 JPY**
- return: **13,000 JPY**
- profit: **+4,200 JPY**
- ROI: **147.7273%**

Robustness:
- second chronological half ROI: **135.2083%**
- leave-one-day worst ROI: **112.3684%**
- leave-one-hit min ROI: **109.4186%**
- bootstrap P(ROI>100%): **85.63%**

Next frozen review:
- 10 resolved formal days
- remaining **2**

2026-09-28 single day:
- 12 bets / 1 hit
- investment 1,200 JPY
- return 660 JPY
- profit **-540 JPY**
- ROI **55.0%**

### S03_M2
- evaluated: **63**
- invalid: 1
- pending: 0
- hits: 4
- investment: 6,300 JPY
- return: 10,120 JPY
- profit: **+3,820 JPY**
- ROI: **160.6349%**
- max DD: 2,000 JPY
- max losing streak: 20
- first half ROI: 268.0645%
- second half ROI: **56.5625%**
- bootstrap P(ROI>100%): **77.61%**
- remaining to 100-review: **37**

Interpretation:
- overall remains >100%;
- S03 recent half is weak;
- do not retune before frozen review.

---

## 8. Day-strength future-only shadow

Main-integrated workflow:
`.github/workflows/research-v4-day-strength-shadow-manual.yml`

Frozen rule:
- target >= 2026-09-28
- `day_strength = mean(formal TOP6 race_score)`
- reference = median immediately prior 7 FORMAL_AVAILABLE day strengths
- KEEP_SHADOW iff target >= reference
- otherwise SKIP_SHADOW
- no DB/result/payout/odds read
- unavailable days never reconstructed
- shadow never changes formal action automatically

### 2026-09-28
- target strength: **0.93618881**
- reference: **0.93817204**
- classification: **SKIP_SHADOW**

After settlement:
- 9/28 formal TOP2 ROI = 55.0%
- SKIP would have avoided -540 JPY on that one day

This is **one-day descriptive evidence only**.
Do not promote the rule from one day.

### 2026-09-29
- formal artifact unavailable
- no day-strength label

Current optional progress:
- future classified/resolved days: **1**
- KEEP: **0**
- SKIP: **1**

Admission gate:
- >=10 future resolved days
- >=3 KEEP
- >=3 SKIP

---

## 9. V5 research candidate — completion target

Target:
**2026-10-15 V5 core freeze review**

Meaning of completion:
- mandatory prospective evidence gates reached;
- review packet can be generated;
- V5 core research specification can be deliberately frozen;
- then a new Forward phase can start.

Not meaning:
- long-run ROI >100% proven;
- automatic Production switch;
- automatic purchase.

### Mandatory V5 core gates
- Formal V4 >= **20 resolved FORMAL_AVAILABLE days**
- S03_M2 >= **100 evaluated observations**
- evidence contract remains clean

Current:
- V4: **8 / 20**, remaining **12**
- S03: **63 / 100**, remaining **37**
- status: `COLLECTING_CORE_EVIDENCE`

9/29 does not count.

### Optional/nonblocking
Day-strength:
- own gate 10 days + KEEP>=3 + SKIP>=3

F-count:
- not required for V5 core
- live activation not approved

V5 scope lock through 10/15:
- no new V5-core feature
- no deadline-driven gate lowering
- no post-outcome retuning
- recent_form / L-count / exhibition / weather-water / odds-EV selector / new unpreregistered features are deferred to later V5.1 research

Relevant main-integrated:
- #437 V5 milestone
- #438 combined V5 progress
- #440 V5 freeze review packet
- #441 V5 scope lock

---

## 10. F-count future path

Dependency chain:
- #397 prospective head-error diagnostic
- #398 hash-bound companion contract
- #400 exact-36-row pure adapter
- #413 current formal-artifact compatibility + activation manifest

Current:
- technical prep green
- live DB read/capture/persistence/schedule **not approved**
- no historical backfill
- no historical coefficient search

Do not start live F-count without explicit approval.

---

## 11. Historical evidence that must not be misused

Long-history V4 replay was poor:
- current formal 2pt historical ROI around **75.069%**
- no fixed 1-5 point count was profitable

This is important negative evidence.

Old pre-freeze S03 profitability was invalidated by timing audit:
- old historical profitable support rejected

Current positive numbers come from **prospective frozen evidence**, not from pretending the old backtest became profitable.

Do not claim profitability is proven.

---

## 12. Immediate next work — ordered

### Safe now
1. Start every new chat by reading:
   - `docs/HANDOFF_MASTER_20260929.md`
   - `docs/PROJECT_HANDOFF.md`
   - `docs/CURRENT_STATE.md`
2. Re-fetch:
   - GitHub main
   - open PRs
   - CI
   - Railway Production status/config
3. Keep #452 Draft green and inspect only read-only/safe evidence unless new approval arrives.
4. Preserve 9/29 as unavailable.
5. Continue nightly result settlement / combined checkpoint.
6. Continue V4 toward 10-day then 20-day review.
7. Continue S03 toward 100 observations without retune.
8. Continue future day-strength only on valid FORMAL_AVAILABLE days.
9. Track V5 core target 2026-10-15.

### Next approval-sensitive decision
The main pending Production decision is:
**whether to merge/activate #452 and retry fallback 08:20 with code+Cron aligned.**

Before activation:
- recheck current main / #452 head / CI
- recheck Railway Cron still 08:25
- recheck source/build/startCommand/runtime/replica
- ensure staged/pending none
- obtain explicit user approval

If approved:
- merge Production-effect code only under approved plan
- change Cron exactly 08:25 -> 08:20
- verify terminal SUCCESS
- first live cycle must be measured
- rollback path remains 08:25

---

## 13. Current final state summary

At handoff preparation:
- GitHub main: `0dfe3518ea2789a701ffad90da170bf2b7d9f798`
- Railway fallback Cron: **08:25 JST**
- dispatcher deployment: **SUCCESS**
- staged/pending: none
- #452: Draft, mergeable, all CI SUCCESS, not merged
- 9/29 formal: **UNAVAILABLE**
- V4: **8/20**, ROI **147.7273%**, +4,200 JPY
- S03: **63/100**, ROI **160.6349%**, +3,820 JPY
- day-strength: 1 day, KEEP 0 / SKIP 1
- V5 target: **2026-10-15**
- Production V4 model/selector/stake unchanged
- `purchase_action=false`

`MASTER_HANDOFF_20260929 / PROD_FALLBACK_0825 / PR452_GREEN_NOT_MERGED / 929_UNAVAILABLE / V4_8_OF_20 / S03_63_OF_100 / V5_TARGET_20261015 / NO_RETUNE / PURCHASE_FALSE`
