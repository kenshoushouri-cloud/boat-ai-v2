# Next Chat Start Here — 2026-09-30 14:39 JST

以下の本文を、新しいChatGPTトークへ**そのまま貼り付けて**使用してください。

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
4. **`docs/LIVE_HANDOFF_20260930_1439.md`**
5. **`docs/NEXT_CHAT_START_HERE.md`**

補助資料:
- `docs/MONTHLY_PROFIT_TARGET_FEASIBILITY_20260930.md`
- `docs/V4_FCOUNT_LIVE_ACTIVATION_20260930.md`
- GitHub Issue #42 最新コメント
- open PR / Draft PR
- GitHub Actions
- Railway Production

`SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` を全体仕様・背景の完全版、
`LIVE_HANDOFF_20260930_1439.md` を最新ライブ差分として扱ってください。

それ以前のSHA・Cron・件数・PR状態・run/deploy状態は履歴として扱い、現在値と仮定しないでください。

その後、必ずread-onlyで現在値を再取得してください。

- GitHub current main SHA
- latest main merge
- open PR / Draft PR
- 重要PRのmergeability / CI
- active / pending GitHub Actions
- Railway Production fallback Cron
- Railway latest deployment
- Railway staged / pending config
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
- run `36669671807` — Historical official B-file bulk backfill

GitHub `main` をコードの Source of Truth、
Railway PostgreSQL を Production data の Source of Truth とします。

## システム構築の目的

締切前に利用可能だった情報だけを使い、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値を持つ競艇AIを構築し、実運用で安定収益を目指します。

運用目標:

- 2026-10-15前後のV5 core freeze / operational-readiness review
- 質を優先した概ね1日1〜3レース
- 月間純利益 **+50,000円**
- ROIだけでなく利益額、DD、連敗、later-half、sample size、自然候補数を確認
- 通知件数/月収目標のためだけにselector/thresholdを緩めない
- stake scalingはprospective edge確認後
- purchaseは現在無効、`purchase_action=false`

## 日次タイムライン — JST

- **08:15** source cutoff
- **08:16** nominal GitHub prospective schedule
- **08:20** Railway fallback dispatcher
- **08:32** availability hard-stop
- 各race deadline前にformal freeze
- **23:30** nightly results / settlement
- settlement後にV4 + S03 combined checkpoint

2026-09-29 formal V4は永久にUNAVAILABLEです。
historical reconstructionで復活させず、V4 formal dayへ加算しないでください。

## 直近Production基盤

最終handoff直前のread-back:

- main: `861d05d051976c74707556b31a146cdc4ab2d649`
- Railway fallback Cron: **08:20 JST / `20 23 * * *`**
- latest fallback deployment: `3c8e6394-75d2-4c27-bea1-a6cc12a40cfd` — **SUCCESS**
- staged config: none
- 9/30 08:21:47 JST fallback dispatch実績あり

これはスナップショットなので、新チャットで必ず再取得してください。

## V5 core mandatory gates

- formal V4 >= **20 resolved FORMAL_AVAILABLE days**
- S03_M2 >= **100 officially evaluated observations**
- evidence contract clean

最後に文書化されたsettled baseline（2026-09-28まで）:

- V4: **8/20**, ROI 147.7273%, profit +4,200 JPY
- S03_M2: **63/100**, ROI 160.6349%, profit +3,820 JPY
- S03 second-half ROI 56.5625%

9/30以降は必ず最新settlementを確認して更新してください。

## Historical不足データ

不足historicalデータは**積極的に取得**する方針です。

historical truth:

- target deadline前に利用可能だった値
- target-race outcomeをfeature constructionへ入れない
- official target-day pre-race program/racelist/B/beforeinfoはprovenance付きで利用可能
- prior-only reconstructionはstrictly prior eventsのみ
- official pre-race F-countはhistorical inputへ利用可能
- outcome-guided coefficient/threshold searchは禁止
- historical reconstructionをprospective evidenceと呼ばない
- V4 20-day / S03 100-observation gateへ加算しない

Source priority:

1. BOAT RACE official
2. official prior-only reconstruction
3. provenance確認済みpre-race archive
4. 艇国データバンクはsupplemental / gap-fill / cross-check

Issue #42をhistorical acquisitionのstatus busとして確認してください。

最終read-back:
- run `36669671677`: terminal completion未確認。重複trigger前に再確認
- run `36669671807`: backfill job pending
- Issue #42 latest known B-file command: `2025-09-09 .. 2025-09-22`

## Open Draft PR

最終read-backでは以下はopen Draftで、head CIはgreenですが、current mainに対してmergeability=falseになっています。

- #500 — July 2025 historical pre-race raw acquisition
- #498 — prior-day official K recent_form reconstruction
- #497 — historical beforeinfo write-lane isolation
- #459 — LINE candidate volume near-miss diagnostic
- #458 — unavailable formal-day count regression test

そのままmergeせず、current mainへrebase/diff/revalidateしてから判断してください。

古いDraft #462-#467等は後続実装でsupersededの可能性があるため、そのままmergeしないでください。

## F-count

Future prospective F-count companionはactiveです。

- valid formal V4 freezeの後だけ
- formal six races × 6 lanes = exact 36 rows
- PostgreSQL READ ONLY
- read: race_id / lane / f_count
- separate artifact
- F-count failureはformal V4を壊さない
- model/LINE/stake/purchaseへ影響なし

Historical F-countはofficial target-day pre-race sourceならhistorical inputとして利用可能ですが、prospective evidenceとは別管理し、outcome-guided coefficient searchは禁止です。

## 月 +50,000円

月+50,000円は**selector tuning targetではなくscaling objective**です。

100円/ticket・TOP2・30日/月:

- 1 race/day → ROI 933.33%必要
- 2 race/day → ROI 516.67%必要
- 3 race/day → ROI 377.78%必要

順序:

1. prospective edge
2. natural quality volume
3. conservative ROI / later-half / DD / losing streak
4. bankroll/risk
5. stake proposal
6. 別承認後にProduction stake検討

## Production safety

勝手に変更しない:

- Production prediction/model
- Production selector/threshold/candidate logic
- Production stake
- new LINE real-send behavior
- purchase
- Railway Production service/Cron/variablesの新規変更
- Production DB contract外 write/schema/VACUUM

`purchase_action=false` を維持してください。

Railway `list_variables` は絶対に呼ばないでください。

## 確認なしで継続してよい作業

- read-only audit
- research
- historical backtest
- prospective Forward evaluation
- safe evidence collection
- Draft PR作成/更新
- CI
- docs/handoff
- 承認済みcontract内のprovenance-safe / fill-missing-only historical acquisition

最新状態との差分を整理したうえで、

1. prospective dataを落とさない
2. 9/30 formal/F-count/settlementを確認
3. V4/S03 counts/economicsを更新
4. historical不足データ取得を進める
5. open Draftをcurrent mainへ整理
6. matched-contract backtestを準備
7. economicsを再現性で評価
8. その後にstake / Production proposalを検討

の順で、10月中頃の目標へ向けて作業を続けてください。
