# Boat AI Complete Handoff — 2026-09-30 14:14 JST

> ## LIVE ADDENDUM — 2026-09-30 14:39 JST
>
> この完全版を読んだ後、必ず **`docs/LIVE_HANDOFF_20260930_1439.md`** を読む。
> 貼り付け用開始文は **`docs/NEXT_CHAT_START_HERE.md`**。
> 14:39 read-backではmain pre-docs=`861d05d...`、Railway fallback=08:20 JST、latest deploy `3c8e6394...` SUCCESS、stagedなし。
> #500/#498/#497/#459/#458はopen Draft・head CI greenだがcurrent-main mergeability read-back=falseのため、rebase/revalidate前にmergeしない。
> historical long-beforeinfo run `36669671677` はterminal未確認、B-file bulk run `36669671807` はbackfill pending。
> 次チャット開始時に必ず全状態を再取得してから続行する。


この文書は、新競艇AI開発プロジェクトを**次のチャットでGitHubだけ確認すれば再開できる状態**にするための完全版引き継ぎです。

> **最優先ルール**
>
> 1. GitHub `main` をコードの Source of Truth とする。
> 2. Railway PostgreSQL を Production data の Source of Truth とする。
> 3. この文書の数値・SHA・run/deploy状態は 2026-09-30 14:14 JST 時点のスナップショットであり、作業開始時に必ず再取得する。
> 4. 古い `LATEST OVERRIDE`、古いSHA、古いCron、古い件数は履歴として扱い、最新状態を推測で引き継がない。
> 5. historical reconstruction と prospective evidence を絶対に混同しない。

---

## 0. 次のチャットで最初に読む順番

最初に以下を読む。

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. **`docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`（この文書）**
4. 必要に応じて:
   - `docs/MONTHLY_PROFIT_TARGET_FEASIBILITY_20260930.md`
   - `docs/V4_FCOUNT_LIVE_ACTIVATION_20260930.md`
   - `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260929.md`（履歴）
5. GitHub Issue **#42** の最新コメント（historical acquisition 実行状況）
6. open PR / CI / GitHub Actions / Railway Production を再取得

再開時は、文書の値を現在値と仮定せず、必ず以下を read-only で再確認する。

- current `main` SHA
- open PR / Draft PR
- PR CI
- GitHub Actions の active/pending historical jobs
- Railway Production fallback Cron
- Railway latest deployment
- Railway staged / pending changes
- V4 formal artifact availability
- S03_M2 officially evaluated count
- historical data coverage / acquisition progress

---

# 1. システム構築の目的

このプロジェクトの最終目的は、

> **結果漏洩・後知恵・過学習を避けながら、締切前に利用できる情報だけで、再現性のあるプラス期待値の競艇予測・選定システムを構築し、実運用で安定した収益を目指すこと。**

単日の高ROIを作ることが目的ではない。

目的ではないもの:

- 毎日必ず買うこと
- 6レースを無理に出すこと
- 通知数だけを増やすこと
- historical backtest を見た後に閾値を都合よく調整すること
- unavailable day を後から再構築して Forward 件数へ入れること
- 一時的な高ROIを長期収益性と断定すること
- 月+50,000円を達成するためだけに候補条件を緩めること

品質が高いなら **1日1〜3レース程度**でもよい。
品質がない日は **0レース**でもよい。

---

# 2. 運用目標

## 2.1 開発・運用時期

現在の開発ターゲット:

- **2026-10-15 前後: V5 core freeze / operational-readiness review**
- ユーザー希望: **10月中頃の運用開始**

ただし 10/15 は利益保証日ではない。

10/15 に目指すのは:

- V5 core の証拠ゲートが揃っている
- matched-contract historical evidence が増えている
- prospective evidence と historical reconstruction の区別が保たれている
- Production候補仕様を凍結して次のForward/運用判断へ進める

ゲート未達・再現性不足なら、日付を理由にProductionへ無理に昇格させない。

## 2.2 収支目標

明示された運用目標:

- **月間純利益 +50,000円**
- 実用上の通知候補目安: **1〜3レース/日**

ただしこれは selector tuning target ではない。

現在の100円/点、TOP2前提の単純計算:

| 通知レース/日 | 月間投資（30日、2点、100円） | +50,000円に必要なROI |
|---:|---:|---:|
| 1 | 6,000円 | 933.33% |
| 2 | 12,000円 | 516.67% |
| 3 | 18,000円 | 377.78% |

したがって、

> **まずエッジを証明し、その後に自然な候補量を確認し、最後に別承認でstake scalingを検討する。**

月+50,000円のために候補条件を緩めたり、先に賭け金を上げない。

現在のV4 formal 6R/day × TOP2 × 100円で、仮にROI 147.7273%が30日継続した場合:

- 月間投資: 36,000円
- descriptive projected profit: 約 **+17,182円**

これは +50,000円には届かない。

stake scaling は、sample gate・後半ROI・leave-one-day/hit・DD・連敗・bankroll制約を確認した後に別途検討する。

---

# 3. 現在の世代構成

## Production = V4

Productionの予測/選定契約は凍結中。

主要入力:

- racer class
- national win rate
- national place2 rate
- local place2 rate
- average ST
- venue/course bias
- Racer Course coefficient **0.50**
- Opponent Pressure coefficient **1.0**, first-place-only
- Motor2 beta **0.06**
- probability temperature **2.20**

formal selector:

- `head_p1`
- `head_margin`
- `top3_mass`
- `concentration`
- formal TOP6 races
- formal TOP2 tickets
- formal selector は odds/EV を読まない
- missing Course/Opponent/Motor は neutral
- `purchase_action=false`

Production model / selector / threshold / stake / LINE behavior は、明示承認なしに変更しない。

## Research target = V5 core

V5 core は「V4係数を少し変える」だけではなく、次世代研究候補として管理する。

V5 core mandatory gates:

1. formal V4 **20 resolved FORMAL_AVAILABLE days**
2. S03_M2 **100 officially evaluated observations**
3. evidence contract clean

2026-09-28までの最後に文書化されたsettled checkpoint:

- V4: **8/20**
- S03_M2: **63/100**

historical reconstruction の件数はこのgateに加算しない。

---

# 4. 現在のProspective経済性

## Formal V4 TOP2 — settled through 2026-09-28

- resolved formal days: **8**
- frozen races: 48
- official settled: 44
- void: 4
- TOP2 bets: 88
- hits: 12
- investment: 8,800円
- return: 13,000円
- profit: **+4,200円**
- ROI: **147.7273%**
- second chronological half ROI: **135.2083%**
- leave-one-day worst ROI: **112.3684%**
- leave-one-hit minimum ROI: **109.4186%**
- whole-day bootstrap P(ROI>100%): **85.63%**
- 2026-09-28単日: ROI 55.0%, profit -540円

良いが、まだ8日なのでstake scalingや長期収益確定には不足。

## S03_M2 — settled through 2026-09-28

- officially evaluated: **63/100**
- invalid: 1
- hits: 4
- investment: 6,300円
- return: 10,120円
- profit: **+3,820円**
- ROI: **160.6349%**
- max DD: 2,000円
- max losing streak: 20
- first half ROI: 268.0645%
- second half ROI: **56.5625%**
- bootstrap P(ROI>100%): **77.61%**

重要:

- 直近Forward overallは高い
- しかし second half は100%未満
- historical timing-safe S03_M2 は悪い
  - original-window ROI: **26.1842%**
  - all-available strict timing-safe ROI: **19.5098%**

したがって S03_M2 は「有望と確定」ではない。
**historicalでは弱く、直近Forwardだけ強く見える anomaly を凍結条件のまま100件まで確認中**。

---

# 5. 通知数とProduction LINEの重要な区別

formal V4 と現在のProduction LINE候補ロジックは別系統。

## formal V4

- TOP6 race
- TOP2 ticket
- no odds/EV selector

## current Production LINE

旧 v24/v22 系ロジックを使用。

基本 low candidate:

- `11 <= prob_rank <= 20`
- `market_rank == 1`
- `3.0 <= odds < 5.0`
- さらに venue/day/race filters

2026-09-23..09-29 read-only audit:

- day/night target races: **1,029**
- ready: **846**
- after session filtering: 約 **553**
- frozen low-core matches: **2**
- actual pre-LINE candidate: **1**

つまりLINEが少ない主因は通知設備ではなく、**旧Production candidate条件が非常に狭いこと**。

2026-09-24 night は candidate=1 / selected=1 / LINE HTTP 200 で送信成功しており、LINE配管自体は動作確認済み。

S03_M2 result-blind volume:

- 2026-09-23..09-29: **19 unique races**
- 平均: **2.71 races/day**
- 7日のうち5日が1〜3 races/day

ただし volume feasibility であり、profitability proof ではない。

Draft PR **#459** がLINE candidate volume / near-miss診断を持つ。
CIはgreenだったが現在mainより古いbaseなので、利用するならrebase/revalidateする。

---

# 6. 毎日の運用タイムライン — JST

現行の重要タイムライン:

| 時刻 | 意味 |
|---|---|
| **08:15** | source cutoff / morning source boundary |
| **08:16** | nominal GitHub schedule。遅延実績があるため単独では信用しない |
| **08:20** | Railway fallback dispatcher Cron |
| **08:32** | availability hard-stop |
| race deadlines | formal freeze は各deadlineより前でなければならない |
| **23:30** | nightly results / settlement path |

Railway fallback current Cron:

- `20 23 * * *` UTC
- = **08:20 JST**

2026-09-30の実ログ:

- 08:21:47 JST
- `action=DISPATCH_FALLBACK`
- target_date=2026-09-30
- reason=`no_valid_primary_artifact_observable`

これは 08:20 code/Cron alignment が実運用で動いた証拠。

ただしこの文書作成時点では、**9/30 formal artifactをresolved dayとしてカウント済みとは扱わない**。
次チャット開始時にGitHub Actions artifact / availability / settlementを確認してから増やす。

---

# 7. 2026-09-29 incident — 絶対に忘れない

9/29 は Railway Cronを08:20へ動かした時点で、dispatcher内部コードがまだ08:25 checkpointだった。

08:23:33 JST:

- `action=NOT_DUE`
- reason=`before_0825_checkpoint`

fallback dispatchなし。

GitHub natural scheduleも約11:33 JSTで遅すぎ、correctly failed closed。

結論:

> **2026-09-29 formal prospective V4 artifact = UNAVAILABLE**

禁止:

- 9/29 formalの再構築
- 9/29をV4 formal resolved dayへ加算
- 9/29 day-strength labelの捏造
- historicalデータでformal prospective dayを後付けすること

現在はPR #452がmerge済みで、コードcheckpointも08:20、Railway Cronも08:20へ整合済み。

---

# 8. Railway / GitHub current snapshot — 2026-09-30 14:14 JST

## GitHub

current main:

- **`647a43e60d627938e55de4239af15265819659bd`**
- merge PR #496
- title: **Add long-range historical beforeinfo campaign**

PR #496 CI:

- Critical Python syntax: SUCCESS
- Critical mojibake guard: SUCCESS
- Production shadow isolation: SUCCESS
- V21 parser sanity: SUCCESS
- Historical beforeinfo long campaign: SUCCESS

## Railway fallback

project:

- `boat-v2-postgres`
- project id: `268a5b17-0712-440a-884d-27f7fa887a2d`
- Production env: `5ffb02f6-5ec8-4268-9bda-8e30431ff625`

fallback service:

- id: `84010f63-8e5a-4ad3-8718-bdad3dd9c436`
- name: `candidate-discovery-v4-fallback-dispatcher`
- Cron: **08:20 JST**
- latest deployment:
  - `839be48f-af8f-4a53-8ba4-5b8abdc13f8a`
  - status: **SUCCESS**
  - commit: current main `647a43e...`
- staged config: none
- unmerged/staged environment changes: none

**Railway `list_variables` は絶対に呼ばない。**

---

# 9. F-count policy

## Future prospective F-count

PR #460 merge済み。

future-only companion capture は active。

設計:

1. valid formal V4 freeze が先
2. formal six racesだけ
3. 6 races × 6 lanes = exact 36 rows
4. DB READ ONLY
5. read only:
   - `race_id`
   - `lane`
   - `f_count`
6. separate hash-bound artifact
7. F-count失敗はformal V4を壊さない
8. LINE/model/stake/purchaseへ影響なし

## Historical F-count

2026-09-30のユーザー指示により historical policy は更新された。

許可:

- official target-day racelist / B-file F-count を historical predeadline input として取得・利用
- 当日レース前情報として本質的に公開される値は、historical reconstructionへ使える

ただし:

- historical F-count を使った outcome-guided coefficient searchは禁止
- prospective evidence とラベルを混ぜない
- Production modelへ自動反映しない

古い「historical F-count backfill全面禁止」の記述は、この限定されたpredeadline historical input policyによって supersede される。

ただし **formal prospective artifact backfill禁止**は今も有効。

---

# 10. Historical missing-data acquisition — 現在の最重要並行作業

ユーザー方針:

> **不足データは可能な限り早く取得し、2025年7月以降のbacktest品質を改善する。**

historical truth:

- そのレースのdeadline前に利用できた値が正しいfeature value
- target-race outcomeはfeature constructionへ入れない
- inherently pre-race な official program/racelist/B/beforeinfo は historical predeadline-by-nature として扱える
- deterministic reconstruction は target deadline より strictly prior のイベントのみ
- historical reconstruction は必ず別provenanceで管理
- prospective V4/S03 gateには数えない

## Source priority

1. **BOAT RACE official**
2. BOAT RACE official prior-only reconstruction
3. BoatraceCSV等のpre-race archive（source semanticsがpredeadlineと確認できる場合）
4. 艇国データバンクは supplemental / gap-fill / cross-check

艇国 rules:

- automated access interval >= 3 seconds
- known URLs only
- single IP
- CSS/JS/image等のstatic assetsを反復取得しない
- official BOAT RACE downloadを優先
- present-day aggregateをhistorical valueとして直接使わない
- as-of cutoffを証明できる dated history のみ prior-only reconstruction/cross-checkに使う

---

# 11. Historical data coverage audit

Issue #42 read-only coverage audit:
2025-07-01..2026-09-29

total races:

- **70,026**

coverage:

- exhibition_time full-six: **62,205**
- exhibition_st full-six: **62,180**
- wind_speed: **62,827**
- wave_height: **62,827**
- temperature: **5,289**
- water_temperature: **5,289**
- complete_beforeinfo: **5,220**
- complete_beforeinfo_pct: **7.45%**

重要:

- 展示time/STとwind/waveはかなり埋まっている
- temperature / water_temperature が大きな穴
- 「レース件数不足」より「現在契約と同じ情報量を再現できる行が少ない」ことが問題

2025-07:

- races 5,196
- complete_beforeinfo 5,056
- complete_beforeinfo_pct **97.31%**

2025-08以降はtemperature/water_temperature欠損のためcomplete_beforeinfoが大きく崩れる月が多い。

これが過去backtestと現在Forwardの差を疑う理由の一つ。

---

# 12. Historical acquisition current execution

## Already merged / active infrastructure

### PR #496 — merged

**Ops: add long-range historical beforeinfo campaign**

- one owner-gated command
- max 500 days
- <=220-day segments
- <=31-day runtime chunks
- max-parallel=1
- official archived beforeinfo
- missing-only writes
- no results/odds/payout read
- no Production decision changes

current main is this merge.

### beforeinfo long campaign

GitHub Actions run:

- **36669671677**
- name: Historical beforeinfo long campaign
- status at 14:14 JST: **pending**

Issue #42 command exists for:

- 2025-07-01 .. 2026-09-29

Do not assume completion until run/result comments are confirmed.

### B-file bulk backfill

GitHub Actions run:

- **36669671807**
- name: Historical official B-file bulk backfill
- status at 14:14 JST: **pending**

Do not duplicate-trigger without first checking current run/concurrency.

---

# 13. July 2025 new raw pre-race acquisition

Open Draft PR **#500**:

- title: `Research: acquire July 2025 historical pre-race data`
- head: `7b0661720878f2a540e57be656d36d2ca9033b1c`
- mergeable: true
- all CI: SUCCESS

actual workflow:

- run **36670259441**
- status: **SUCCESS**

artifact:

- name: `historical-prerace-202507-36670259441`
- artifact id: `11077248923`
- size: 4,695,275 bytes
- digest: `sha256:134db90c2594f03b310aae75287bb57534844f52d7064c02cfd6716d8de46d84`
- manifest SHA256:
  `b1649792b29383d7947a946d0fc314ff4f8ccd8d3345edbb719fea029e5a6adc`

coverage:

- Race Cards: **31/31**, 5,072 race rows
- Recent Local: **31/31**, 5,072 race rows
- Recent National: **31/31**, 5,013 race rows
- Race Title: 0/31
- Waku10: 0/31
- Motor Stats: 0/31
- transport/runtime errors: 0

interpretation:

- July 2025はRace Cards / Recent Local / Recent Nationalのpre-race archive coverageが非常に良い
- Recent NationalはRace Cardsより59 rows少ないのでnormalization gapを確認する
- Title/Waku10/Motor Statsは別official/fallback reconstructionが必要、または unavailable のまま扱う
- このPRは raw acquisition artifact only
- **DB importはまだ含まない**
- result/payout/oddsは取得しない

このデータは matched-contract historical backtest を改善する重要候補。

---

# 14. recent_form historical reconstruction

Open Draft PR **#498**:

- title: `Research: reconstruct historical recent_form from prior-day official K (rebased)`
- head: `c81539ffd6c6bf57831ee4c9c03ceb01f91462a1`
- mergeable: true
- CI all SUCCESS
- dedicated run **36668084265**: SUCCESS

contract:

- BOAT RACE official K-derived history
- target features use **strictly earlier calendar dates only**
- same-day results excluded
- future results excluded
- no `v2_results` / odds / payout read
- fill empty `recent_form` only
- historical reconstruction only
- no prospective gate count
- no Production selector/model/LINE/stake/purchase change

PRはまだopen Draft。
merge/DB write前にmainとの差分とconfirmation gateを再確認する。

---

# 15. Historical beforeinfo write-lane isolation

Open Draft PR **#497**:

- title: `Ops: isolate historical beforeinfo write lane`
- head: `c296191f7c1c3c02086c8fe2b37b7aec2c37a955`
- mergeable: true
- CI all SUCCESS

目的:

current shared `historical-production-write` concurrencyでは、

- entry/B-file/Opponent campaign
- beforeinfo exhibition/weather campaign

が同じpending slotを取り合い、pending runが置換される可能性がある。

PR #497 は beforeinfoだけ:

- `historical-beforeinfo-write`

へ分離。

beforeinfo writes:

- `v2_realtime_exhibition_snapshots`
- `v2_realtime_weather_snapshots`

entry/Opponentとは別tableなので、同一beforeinfo内のserial性を維持しながらthroughputを上げる設計。

次チャットでは #497 を優先確認候補とする。

---

# 16. その他 historical acquisition 状況

2026-09-30 09:50 JST時点の最新文書記録:

- official entry/racelist numeric backfill: 2025-08-11までconfirmed
- 2025-08-12 onward batches: running
- racer_name / branch / origin fill-missing-only: merged PR #474
- metadata-aware 2025-07-01..07-07 pilot: running
- Course applied-term proxy:
  - 2025H2 complete
  - 2026H1 running
- Opponent prior-only replay:
  - 2025-07 complete
  - 2025-08 complete
  - 2025-09 had statement timeout during concurrent entry writes; retry after entry I/O settles
- daily B-file parity work exists to reduce future HTTP load

艇国 motor batch:

- 2025-07-15 selected 12 motors: read-only cross-check PASS
- `prior_only_structure_pass_count=0`
- present aggregateはhistorical valueに使わない
- 2026-09-15 cross-check attempt: statement timeout
- supplemental only

---

# 17. Open PRs — 次チャットで優先確認

## High priority current

| PR | 状態 | 役割 |
|---|---|---|
| **#500** | Draft / mergeable / CI green | July 2025 pre-race raw acquisition, artifact成功 |
| **#498** | Draft / mergeable / CI green | prior-day official Kからrecent_form再構築 |
| **#497** | Draft / mergeable / CI green | beforeinfo write concurrency lane分離 |
| **#459** | Draft / old base / CI green at head | LINE candidate volume / near-miss診断 |
| **#458** | Draft / old base / CI green at head | unavailable formal day regression |

## Older historical acquisition Drafts

#462, #463, #464, #465, #466, #467 等は、
後続PRで実装・方針が進んでいるため、**そのままmergeしない**。

使う場合:

1. current mainとの差分確認
2. superseded functionality確認
3. 必要部分だけrebase/cherry-pick
4. CI再実行

#482 は古いdocs progress PRで現在non-mergeable。
最新handoffで内容を置き換えるため、current source of truthとして扱わない。

---

# 18. Historical dataとProspective evidenceの境界

ここが最重要。

## historical reconstruction

目的:

- 2025-07以降のbacktestを現在の情報契約に近づける
- missing dataによる誤判定を減らす
- V5/V5.1 feature候補を広い期間で検証する

許可される例:

- target-day official pre-race program/racelist/B/beforeinfo
- strictly prior official K history
- applied-term racer archive
- prior-only Opponent reconstruction
- historical F-count from target-day pre-race source

## prospective evidence

目的:

- 本当に締切前にその時点で取得した証拠
- V4 20-day / S03 100-observation gate
- Production promotion判断

historical reconstructionはprospective gateに加算しない。

特に:

> **過去データが後から取得できても、9/29のformal V4 unavailable dayを復活させることはできない。**

---

# 19. なぜhistorical backtestが悪かった可能性があるか

長期履歴そのものは多いが、feature coverageが不均一だった。

既知の旧coverage例:

- Motor: 約97.8%
- Course: 約14.7%
- Opponent: 約3.0%

つまり2,592 races等の長期backtestでも、
**現在V4/V5相当の全情報を使えたrace数はずっと少ない可能性**がある。

ただし、

- データ不足 = ルールが本当は利益的

とは断定しない。

S03_M2のMotor coverageは高かったため、
historical S03_M2低ROIを欠損だけで説明することもできない。

今後のmatched-contract backtestでは:

- source provenance
- predeadline semantics
- feature completeness
- time split
- no outcome leakage

を揃えて再評価する。

---

# 20. 10月中頃までの優先作業順

## P0 — prospective dataを1日も落とさない

- 08:20 fallback維持
- formal artifact / availability guard確認
- future F-count companion取得
- 23:30 settlement
- unavailable dayはunavailableのまま

## P1 — historical missing-data acquisition

- beforeinfo long campaign
- B-file bulk
- July 2025 pre-race archive normalization
- recent_form prior-only reconstruction
- Course/Opponent coverage
- provenance-safe historical F-count

目的:
matched-contract backtestのデータ品質を上げる。

## P2 — V5 core gates

- V4 20 resolved FORMAL_AVAILABLE days
- S03_M2 100 official observations
- evidence contract clean

V4 8日から、今後すべてvalidなら20日到達の最短目安はおおむね **2026-10-11**。
missing formal dayがあれば後ろへずれる。

S03_M2は最後のdocumented settled値63/100。
次チャットでは9/29以降のterminal resultを反映して最新化する。

## P3 — matched-contract historical backtest

historical data coverageが十分になったら:

- current V4 contract
- candidate V5 core
- optional V5.1 information

を同じevidence contractで比較する。

outcomeを見てから閾値を探し回らない。
preregistered split / OOS / Forwardへつなぐ。

## P4 — candidate volume

1〜3 races/dayは目安。
#459 near-miss診断をcurrent mainへrebaseして使う候補。

量を先に作らず:

1. edge
2. natural volume
3. risk
4. stake

の順番。

## P5 — 月+50,000円 feasibility

毎回 combined checkpoint で:

- 30日換算投資
- 30日換算利益
- target gap
- sample gate
- conservative ROI
- DD / losing streak

を確認。

stake proposalは最後。

---

# 21. 10/15で判断する内容

10/15前後に判断すべきもの:

1. V4 20-day gateを満たしたか
2. S03 100-observation gateを満たしたか
3. historical matched-contract dataがどこまで改善したか
4. V4 prospective economicsが後半でも維持されているか
5. S03のrecent weaknessが改善/継続/悪化したか
6. F-count prospective coverageが十分か
7. V5 core specをfreezeできるか
8. 1〜3 race/dayで自然にquality候補が出るか
9. monthly +50,000円へ必要なstake/riskが現実的か
10. Production proposalを出す価値があるか

日付だけでProduction activationしない。

---

# 22. 作業権限 / safety boundaries

## 確認なしで継続してよい

- read-only audit
- research
- historical backtest
- prospective Forward evaluation
- safe evidence collection
- Draft PR作成/更新
- CI
- docs / handoff
- historical acquisitionの既存承認済みsafe workflowsの確認・継続
- provenance-safe / fill-missing-only historical acquisition within approved contract

## 新しい明示承認を必要とする

- Production prediction/model変更
- Production selector/threshold/candidate logic変更
- Production stake変更
- new LINE real-send behavior
- purchase activation
- Railway Production service/Cron/variablesの新規変更
- Production DBのcontract外 INSERT/UPDATE/DELETE/schema/VACUUM
- historical acquisition contractを越えるcanonical overwrite
- paid/external actions

## 絶対禁止 / fail closed

- unavailable formal dayの後付け
- target-race outcomeをfeatureへ混ぜる
- result leakage
- outcome-guided historical coefficient/threshold fishing
- gateを日付に合わせて緩和
- notification countのためだけにthresholdを緩和
- `purchase_action=true` の自動化
- Railway plaintext variable enumeration
- **Railway `list_variables` call**

---

# 23. 次のチャットでの再開チェックリスト

次チャットは以下の順で開始する。

### A. GitHub / Railway状態

- current main SHA
- latest merge title
- open PRs
- active/pending GitHub Actions
- Railway fallback Cron
- fallback latest deployment
- staged/pending Railway config

### B. Today prospective

- 2026-09-30 formal artifactは作成できたか
- availability guardは通ったか
- F-count companionは作成できたか
- 9/30はまだ未settledならcountしない

### C. Economic checkpoint

- V4 resolved days
- V4 ROI/profit/halves/leave-one/DD
- S03 evaluated count
- S03 ROI/profit/second-half/DD
- monthly +50,000 target gap

### D. Historical acquisition

- runs `36669671677` / `36669671807` の現在状態
- Issue #42の新しいbot summary
- PR #500
- PR #498
- PR #497
- coverage audit更新
- beforeinfo/weather/temp gaps
- entry/racelist progress
- Course/Opponent progress

### E. 次の作業

最優先は:

1. prospectiveを落とさない
2. historical不足を埋める
3. matched-contract backtestを準備
4. V5 gatesを満たす
5. economicsを再現性で判断
6. その後stake / Production proposal

---

# 24. 現在の一行ステータス

`MAIN_647A43E / FALLBACK_0820_ALIGNED_SUCCESS / 930_FALLBACK_DISPATCH_OK / V4_LAST_SETTLED_8_OF_20 / S03_LAST_SETTLED_63_OF_100 / FCOUNT_FUTURE_CAPTURE_ACTIVE / HISTORICAL_ACQUISITION_ACTIVE / BEFOREINFO_AND_BFILE_JOBS_PENDING / JULY2025_PRERACE_ARTIFACT_SUCCESS / MONTHLY_PLUS_50000_TARGET / PROD_MODEL_UNCHANGED / PURCHASE_FALSE`

---

# 25. 次チャットで絶対に誤解しないこと

- historical backfillは現在**積極的に実施する方針**
- ただし prospective evidence の後付けはしない
- historical F-countはpredeadline sourceなら利用可能
- ただし outcome-guided coefficient searchはしない
- 1〜3通知/日は目安でありselector gateではない
- 月+50,000円は最終経済目標でありthreshold tuning targetではない
- Production LINEの0件はformal V4の0件を意味しない
- S03 overall高ROIだけを見て昇格しない
- 10/15はreview targetであり利益保証日ではない
- 9/29 V4 formalは永久にUNAVAILABLE
- Production purchaseはまだ無効

この文書と最新GitHub/Railway read-backを起点に作業を続行する。
