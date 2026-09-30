# Next Chat Start Here — 2026-09-30 14:46 JST

以下の本文を、新しいChatGPTトークへそのまま貼り付けて使用する。

---

@Railway  
@GitHub

新競艇AI開発プロジェクトの続きです。

最初に GitHub repository

`kenshoushouri-cloud/boat-ai-v2`

を確認し、以下を**最優先で全文読んでください**。

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
4. **`docs/LIVE_HANDOFF_20260930_1446.md`**
5. `docs/NEXT_CHAT_START_HERE.md`

その後、GitHub Issue #42、open PR / Draft PR、GitHub Actions、Railway Productionをread-onlyで再取得してください。

`SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` をプロジェクト全体の完全版、
`LIVE_HANDOFF_20260930_1446.md` を14:46 JST時点の最新live差分として扱ってください。
古いSHA・Cron・件数・PR/run/deploy状態は履歴であり、現在値と仮定しないでください。

必ず再取得する項目:
- current main SHA / latest merge
- open PR / Draft PR / mergeability / CI
- active / pending GitHub Actions
- Railway fallback Cron / latest deployment / staged config
- 2026-09-30 formal V4 artifact availability
- 2026-09-30 availability guard
- 2026-09-30 F-count companion
- nightly settlement readiness
- V4 resolved formal-day count
- S03_M2 officially evaluated count
- latest V4/S03 economics
- monthly +50,000円 target gap
- Issue #42 historical acquisition progress
- run `36669671677` — Historical beforeinfo long campaign
- run `36669671807` — Historical official B-file bulk

GitHub `main` をcode Source of Truth、Railway PostgreSQLをProduction data Source of Truthとします。

## システム構築の目的

締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値を持つ競艇AIを構築し、実運用で安定した収益を目指します。

目標:
- 2026-10-15前後のV5 core freeze / operational-readiness review
- 質優先で概ね1日1〜3レース。質がなければ0でもよい
- 月間純利益 **+50,000円**
- ROIだけでなくprofit/DD/連敗/later-half/sample/natural volumeを評価
- 通知数や月収目標のためだけにselector/thresholdを緩めない
- stake scalingはprospective edge確認後
- `purchase_action=false`

## 日次タイムライン — JST

- 08:15 source cutoff
- 08:16 nominal GitHub schedule
- **08:20 Railway fallback dispatcher**
- 08:32 availability hard-stop
- race deadline前にformal freeze
- 23:30 nightly results / settlement
- settlement後にV4 + S03 combined checkpoint

2026-09-29 formal V4は永久にUNAVAILABLEです。historical reconstructionで復活させず、formal countへ加算しないでください。

## V5 core mandatory gates

- formal V4 >= **20 resolved FORMAL_AVAILABLE days**
- S03_M2 >= **100 officially evaluated observations**
- evidence contract clean

最後にdocumented settled baseline:
- V4 **8/20**, ROI 147.7273%, +4,200 JPY
- S03_M2 **63/100**, ROI 160.6349%, +3,820 JPY
- S03 second-half ROI 56.5625%

新チャット開始時に必ず最新化してください。

## Historical不足データ

現在は不足historical dataを積極取得します。

原則:
- target deadline前に利用可能だった値をhistorical truthとする
- target-race outcomeをfeature constructionへ入れない
- official target-day pre-race program/racelist/B/beforeinfoはprovenance付きで利用可
- reconstructionはstrictly prior eventsのみ
- historical F-countもofficial pre-race sourceなら利用可
- outcome-guided coefficient/threshold searchは禁止
- historical evidenceをprospective gateへ加算しない

source priority:
1. BOAT RACE official
2. official prior-only reconstruction
3. provenance確認済みpre-race archive
4. 艇国はsupplemental / gap-fill / cross-check

Issue #42をhistorical acquisitionの実行/status busとして確認してください。

14:46 snapshot:
- beforeinfo coverage audit: 70,026 races、complete beforeinfo 5,220 = **7.45%**
- exhibition_time6 62,205 / exhibition_st6 62,180
- wind/wave 62,827
- **temperature/water_temperature 5,289** が大きなcoverage gap
- run `36669671677`: queued/pending、まだjob未materialize
- run `36669671807`: backfill pending
- duplicate trigger前に必ずrun/concurrency確認

## High-priority Draft PR

14:46 read-backで以下はDraft / mergeable=true / current head CI all SUCCESS:
- #500 — July 2025 historical pre-race raw acquisition
- #498 — prior-day official K recent_form reconstruction
- #497 — historical beforeinfo write-lane isolation
- #459 — LINE candidate volume near-miss diagnostic
- #458 — unavailable formal-day regression

古い #462-#467 等は後続実装でsupersededの可能性があるため、そのままmergeしないでください。

## F-count

Future prospective companionはactive:
- valid formal V4 freeze後だけ
- exact 36 rows
- PostgreSQL READ ONLY
- read race_id/lane/f_count
- separate artifact
- failureはformal V4を壊さない
- model/LINE/stake/purchaseへ影響なし

Historical F-countはpredeadline official sourceならhistorical input可。ただしprospectiveとは別管理し、outcome-guided coefficient searchは禁止。

## 月 +50,000円

月+50,000円はselector tuning targetではなくscaling objective。

100円/ticket・TOP2・30日/月:
- 1 race/day → ROI 933.33%必要
- 2 race/day → ROI 516.67%
- 3 race/day → ROI 377.78%

順序:
1. prospective edge
2. natural quality volume
3. conservative ROI / DD / losing streak
4. bankroll/risk
5. stake proposal

## Production safety

勝手に変更しない:
- Production prediction/model
- selector/threshold/candidate logic
- stake
- new LINE real-send behavior
- purchase
- Railway Production service/Cron/variablesの新規変更
- Production DB contract外 write/schema/VACUUM

`purchase_action=false` を維持。
Railway `list_variables` は絶対に呼ばない。

## 継続してよい作業

確認なしで:
- read-only audit
- research
- historical backtest
- prospective Forward evaluation
- safe evidence collection
- Draft PR作成/更新
- CI
- docs/handoff
- 承認済みcontract内のprovenance-safe / fill-missing-only historical acquisition

最初に最新状態との差分を整理したうえで、
1. prospective dataを落とさない
2. historical不足を埋める
3. V4/S03 evidence gatesを進める
4. matched-contract backtestを準備
5. economicsを再現性で評価
6. その後stake / Production proposal
の順で、10月中頃の目標に向けて作業を続けてください。
