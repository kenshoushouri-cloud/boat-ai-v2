# Next Chat Start Here — 2026-09-30

以下は、新しいChatGPTトークへそのまま貼り付けて使用する開始文です。

---

@Railway  
@GitHub

新競艇AI開発プロジェクトの続きです。

最初に GitHub repository:

`kenshoushouri-cloud/boat-ai-v2`

の以下3ファイルを**最優先で全文確認**してください。

1. `docs/PROJECT_HANDOFF.md`
2. `docs/CURRENT_STATE.md`
3. `docs/SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md`

必要に応じて以下も確認してください。

- `docs/MONTHLY_PROFIT_TARGET_FEASIBILITY_20260930.md`
- `docs/V4_FCOUNT_LIVE_ACTIVATION_20260930.md`
- GitHub Issue #42 の最新コメント
- open PR
- GitHub Actions
- Railway Production

`SYSTEM_PURPOSE_TIMELINE_HANDOFF_20260930.md` を最新の完全版引き継ぎとして扱い、それ以前の古いSHA・Cron・件数・PR状態・日付記述は歴史的背景として扱ってください。

その後、必ず現在値をread-onlyで再取得してください。

- GitHub current main SHA
- latest main commit
- open PR / Draft PR
- CI status
- active / pending GitHub Actions
- Railway Production fallback Cron
- Railway latest deployment
- Railway staged / pending config
- 2026-09-30 formal V4 artifact availability
- F-count companion availability
- V4 resolved formal-day count
- S03_M2 officially evaluated count
- latest V4/S03 economics
- Issue #42 historical acquisition progress

GitHub `main` をコードの Source of Truth、Railway PostgreSQL を Production data の Source of Truth とします。
古いSHA・件数・deploy・Cron状態を現在値と仮定しないでください。

## 目的

締切前に利用できる情報だけで、結果漏洩・後知恵・過学習を避けながら、再現性のあるプラス期待値の競艇AIを構築すること。

運用目標:
- 10月中頃のV5 operational-readiness / core freeze review
- 質を優先した1日1〜3レース程度の通知候補
- 月間純利益 **+50,000円**
- ただし件数や月収目標のためにselector/thresholdを緩めない

## 現在の重要ルール

ProductionはV4のまま。
V5 core mandatory gates:
- formal V4 >=20 resolved FORMAL_AVAILABLE days
- S03_M2 >=100 officially evaluated observations
- evidence contract clean

historical reconstructionはこれらのProspective gateへ加算しない。

2026-09-29 formal V4は永久にUNAVAILABLE。
後から再構築・backfill・day countへ加算しない。

## Historical不足データ

不足historicalデータは現在積極的に取得する方針です。

historical truth:
- target deadline前に利用可能だった値を使う
- target-race outcomeをfeature constructionへ入れない
- official target-day pre-race program/racelist/B/beforeinfoはprovenanceを保持してhistorical inputへ利用可能
- prior-only reconstructionはstrictly prior eventsのみ
- historical F-countもofficial pre-race sourceなら利用可能
- outcome-guided F-count coefficient/threshold searchは禁止
- historical reconstructionをprospective evidenceと呼ばない

Source priority:
1. BOAT RACE official
2. official prior-only reconstruction
3. pre-race archive
4. 艇国データバンクはsupplemental/gap-fill/cross-check

Issue #42をhistorical acquisitionの実行/status busとして確認してください。

## 現在のProduction safety

- Production model/selector/threshold/stakeを勝手に変えない
- new LINE real-send behaviorを勝手に有効化しない
- purchaseを有効化しない
- `purchase_action=false`
- unavailable prospective dayを後付けしない
- Railway `list_variables` は絶対に呼ばない

## 作業継続

read-only監査、research、historical backtest、Forward評価、safe evidence collection、Draft PR、CI、docs/handoff、既存承認済みhistorical acquisitionは安全契約内で継続して構いません。

Production prediction/model/selector/threshold/stake/LINE/purchaseの新しい変更は、別途明示承認を取ってください。

最初に最新状態との差分を整理してから、10月中頃の目標へ向けて最も優先度の高い作業を続行してください。
