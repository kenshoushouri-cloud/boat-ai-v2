# Next Chat Start Here — 2026-09-30 14:58 JST

以下を新しいChatGPTトークへそのまま貼り付けてください。

---

@Railway  
@GitHub

新競艇AI開発プロジェクトの続きです。

最初に GitHub repository

`kenshoushouri-cloud/boat-ai-v2`

の以下を最優先で全文確認してください。

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
4. **`docs/LIVE_HANDOFF_20260930_1458.md`**
5. `docs/NEXT_CHAT_START_HERE.md`

その後、Issue #42、current main、open PR、CI、GitHub Actions、Railway Productionをread-onlyで再取得してください。

GitHub `main` = code Source of Truth。
Railway PostgreSQL = Production data Source of Truth。
古いSHA・件数・Cron・run/deploy状態を現在値と仮定しないでください。

【目的】
締切前に利用可能だった情報だけで、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値を持つ競艇AIを構築し、実運用で安定収益を目指します。

【運用目標】
- 2026-10-15前後のV5 core freeze / operational-readiness review
- 質優先で概ね1日1〜3レース。質がなければ0でもよい
- 月間純利益 +50,000円
- 通知数や月収目標のためだけにselector/thresholdを緩めない
- stake scalingはprospective edge確認後
- `purchase_action=false`

【日次JST】
- 08:15 source cutoff
- 08:16 nominal GitHub schedule
- 08:20 Railway fallback
- 08:32 availability hard-stop
- race deadline前にformal freeze
- 23:30 nightly results / settlement
- nightly後にcombined V4 + S03 checkpoint

2026-09-29 formal V4は永久にUNAVAILABLE。historical reconstructionで復活させないでください。

【V5 core gates】
- V4 >=20 resolved FORMAL_AVAILABLE days
- S03_M2 >=100 officially evaluated observations
- evidence contract clean

Last documented settled:
- V4 8/20、ROI147.7273%、+4,200円
- S03_M2 63/100、ROI160.6349%、+3,820円
- S03 second-half ROI56.5625%

必ず最新settlementへ更新してください。

【現在の基盤snapshot】
- main pre-handoff: `780d2676ed22cd1b43f0cfb859f8098dc1e8f245`
- fallback Cron 08:20 JST
- latest fallback deploy `d424210d-26d9-43fd-bd19-b16aefffa9e0` SUCCESS
- staged none
- 9/30 08:21:47 fallback dispatch確認済み

最優先で9/30のformal artifact / availability guard / F-count companionを確認してください。

【Historical不足データ】
現在は積極取得方針です。ただし:
- target deadline前の値のみ
- target-race outcome leakage禁止
- official target-day pre-race dataはprovenance付きで可
- reconstructionはstrictly prior
- historical evidenceをprospective gateへ加算しない
- historical F-countはofficial pre-race sourceなら可
- outcome-guided coefficient/threshold searchは禁止

Source priority:
1. BOAT RACE official
2. official prior-only reconstruction
3. provenance確認済みpre-race archive
4. 艇国 supplemental

最新coverage:
- 70,026 races
- complete_beforeinfo 5,220 = 7.45%
- exhibition_time6 62,205
- exhibition_st6 62,180
- wind/wave 62,827
- temperature/water_temperature 5,289
temperature/water_temperatureが大きな不足です。

Active runs:
- `36669671677` beforeinfo long campaign: queued/pending、job未materialize
- `36669671807` B-file bulk: backfill pending
重複trigger前に再確認してください。

【High-priority Draft PR】
- #500 mergeable=true / CI green
- #498 mergeable=true / CI green
- #497 mergeable=false / CI green
- #459 mergeable=false / CI green
- #458 mergeable=false / CI green

#497/#459/#458はcurrent mainへrebase/diff/revalidate前にmergeしないでください。
古い#462-#467等はsuperseded可能性があるため、そのままmergeしないでください。

【月+50,000円】
100円/ticket・TOP2・30日/月:
- 1 race/day ROI933.33%必要
- 2 race/day ROI516.67%
- 3 race/day ROI377.78%

月+50,000円はselector tuning targetではなくscaling objectiveです。
edge → natural volume → conservative ROI/DD/連敗 → bankroll → stake proposal の順で判断してください。

【Production safety】
勝手に変更しない:
- Production model
- selector/threshold/candidate logic
- stake
- new LINE real-send
- purchase
- Railway service/Cron/variables
- contract外DB write/schema/VACUUM

Railway `list_variables` は絶対に呼ばない。
`purchase_action=false` を維持。

【確認なしで継続可】
- read-only audit
- research / historical backtest / prospective Forward
- safe evidence collection
- Draft PR / CI / docs
- 承認済みcontract内のprovenance-safe / fill-missing-only historical acquisition

まず最新状態との差分を整理し、
1. prospective dataを落とさない
2. 9/30 formal/F-count/settlementを確認
3. V4/S03を最新化
4. historical不足を埋める
5. matched-contract backtestを準備
6. economicsを再現性で評価
7. その後stake / Production proposal
の順で続けてください。
