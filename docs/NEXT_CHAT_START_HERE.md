# Next Chat Start Here — 2026-09-30 14:30 JST

以下の本文を、新しいChatGPTトークへそのまま貼り付けて使用する。

---

@Railway  
@GitHub

新競艇AI開発プロジェクトの続きです。

最初に GitHub repository

`kenshoushouri-cloud/boat-ai-v2`

を確認し、以下のファイルを**最優先で全文読んでください**。

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`
4. `docs/LIVE_HANDOFF_20260930_1430.md`

補助資料として必要に応じて以下も確認してください。

- `docs/MONTHLY_PROFIT_TARGET_FEASIBILITY_20260930.md`
- `docs/V4_FCOUNT_LIVE_ACTIVATION_20260930.md`
- `docs/NEXT_CHAT_START_HERE.md`
- GitHub Issue #42 の最新コメント
- open PR / Draft PR
- GitHub Actions
- Railway Production

`SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` をプロジェクト全体の完全版引き継ぎ、
`LIVE_HANDOFF_20260930_1430.md` を14:30 JST時点の最新ライブ差分として扱ってください。

それ以前の古いSHA・Cron・件数・PR状態・run/deploy状態は歴史的背景として扱い、現在値と仮定しないでください。

その後、必ずread-onlyで現在値を再取得してください。

- GitHub current main SHA
- latest main commit / merge
- open PR / Draft PR
- 各重要PRのmergeability / CI
- active / pending GitHub Actions
- Railway Production fallback Cron
- Railway latest deployment
- Railway staged / pending config
- 2026-09-30 formal V4 artifact availability
- availability guard
- F-count companion availability
- nightly settlement readiness
- V4 resolved formal-day count
- S03_M2 officially evaluated count
- latest V4/S03 economics
- monthly +50,000円 target gap
- Issue #42 historical acquisition progress
- historical beforeinfo long campaign run `36669671677`
- historical B-file bulk run `36669671807`

GitHub `main` をコードの Source of Truth、
Railway PostgreSQL を Production data の Source of Truth とします。

## システム構築の目的

締切前に利用可能だった情報だけを使い、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値を持つ競艇AIを構築すること。

運用目標:

- 2026-10-15前後のV5 core freeze / operational-readiness review
- 質を優先した概ね1日1〜3レースの通知候補
- 月間純利益 **+50,000円**
- ROIだけでなく利益額、DD、連敗、後半performance、サンプル数、自然候補数を確認
- 通知件数や月収目標のためだけにselector/thresholdを緩めない
- stake scalingはprospective edge確認後
- purchaseは現在無効、`purchase_action=false`

## 日次タイムライン — JST

- 08:15 source cutoff
- 08:16 nominal GitHub schedule
- **08:20 Railway fallback dispatcher**
- 08:32 availability hard-stop
- 各race deadlineより前にformal freeze
- 23:30 nightly results / settlement
- settlement後にV4 + S03 combined checkpoint

2026-09-29 formal V4は永久にUNAVAILABLEです。
historical reconstructionで復活させず、V4 formal dayへ加算しないでください。

## V5 core mandatory gates

- formal V4 >= **20 resolved FORMAL_AVAILABLE days**
- S03_M2 >= **100 officially evaluated observations**
- evidence contract clean

最後に文書化されたsettled baselineは2026-09-28まで:

- V4: **8/20**, ROI 147.7273%, profit +4,200 JPY
- S03_M2: **63/100**, ROI 160.6349%, profit +3,820 JPY
- S03 second-half ROI 56.5625%

これらは新チャット開始時に必ず最新化してください。

## Historical不足データ

不足historicalデータは現在**積極的に取得する方針**です。

historical truth:

- target deadline前に利用可能だった値を使用
- target-race outcomeをfeature constructionへ入れない
- official target-day pre-race program/racelist/B/beforeinfoはprovenanceを保持してhistorical inputへ利用可能
- prior-only reconstructionはstrictly prior eventsのみ
- historical F-countもofficial pre-race sourceなら利用可能
- outcome-guided F-count coefficient/threshold searchは禁止
- historical reconstructionをprospective evidenceと呼ばない
- V4 20-day / S03 100-observation gateへ加算しない

Source priority:

1. BOAT RACE official
2. official prior-only reconstruction
3. provenanceが確認できるpre-race archive
4. 艇国データバンクはsupplemental / gap-fill / cross-check

Issue #42をhistorical acquisitionの実行/status busとして確認してください。

14:30 JST時点では以下2runはpendingでした。重複trigger前に必ず最新状態を確認してください。

- `36669671677` — Historical beforeinfo long campaign
- `36669671807` — Historical official B-file bulk backfill

## 現在のhigh-priority Draft PR

14:30 JST read-backでは以下は全てmergeable=true / head CI greenでした。

- #500 — July 2025 historical pre-race raw acquisition
- #498 — prior-day official K recent_form reconstruction
- #497 — historical beforeinfo write-lane isolation
- #459 — LINE candidate volume near-miss diagnostic
- #458 — unavailable formal-day count regression test

ただし次チャットではcurrent mainとの差分を再取得してから判断してください。
古いhistorical Drafts #462-#467等は後続実装でsupersededされている可能性があるため、そのままmergeしないでください。

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

100円/ticket・TOP2・30日/月では:

- 1 race/day → ROI 933.33%必要
- 2 race/day → ROI 516.67%必要
- 3 race/day → ROI 377.78%必要

したがって、

1. prospective edge
2. natural quality volume
3. conservative ROI / DD / losing streak
4. bankroll/risk
5. stake proposal

の順で判断してください。

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

## 作業継続

確認なしで継続してよい範囲:

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
2. historical不足データを埋める
3. V4/S03 evidence gatesを進める
4. matched-contract backtestを準備する
5. economicsを再現性で評価する
6. その後にstake / Production proposalを検討する

の順で、10月中頃の目標へ向けて作業を続けてください。
