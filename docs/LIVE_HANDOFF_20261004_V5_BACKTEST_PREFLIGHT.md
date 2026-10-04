# Live Handoff — V5 Matched-Backtest Preflight

## Goal / contract
- 運用開始目標=**2026年10月中旬**。Production=**V4**、V5=**research-only**。Railway<=**USD20/month**。
- V5=`V5_M2_TOP2_BOTH_POSITIVE_V1`。100円/点、TOP2=200円/race。odds/EV不使用。split固定済み、retune禁止。
- V4/V5ともCourse/Opponent missingは**neutral**。historical結果を見て後付けgate変更しない。

## Historical matched selection — PRE-OUTCOME FROZEN
- run `37185954388` SUCCESS / artifact `11296773501`。
- total races **70,170** / exact6 **70,170** / Motor2 incomplete **6** / shared evaluable **70,164**。
- V4選択は結果参照前に **2,742 races** を凍結。V5はそのV4 TOP2だけへfrozen Motor2 scoreを適用し **1,522 races** が通過。
- TRAIN_REFERENCE: V4 **1,104** / V5 **620**。
- VALIDATION: V4 **1,086** / V5 **564**。
- OOS: V4 **552** / V5 **338**。
- freeze SHA256=`7627be7b155a6baadf8bf74e36ebef199439ed976348510334003bf686453839`。
- selection時 outcome/odds/payout read=0 / DB write=0 / Production change=0。

## Historical inputs / diagnostics
- Opponent 2026-09-01..10は**1,488/1,488 strict prior-only再構築済み**。DB非変更。
- Course-complete=58,412/70,170。gap=11,758だがneutral扱いでhard blockerではない。
- Course診断: complete ROI 80.42% vs neutral 71.31%。両群ROI<100%、後付けCourse gateは禁止。
- Prospective live gate run `37185954224` SUCCESS: V4 **9/20 days**、S03_M2 **66/100**、evidence **clean**。`V5_LIVE_GATES_RESULT=BLOCKED`。

## V5.1 feature research lane
- First candidate=`V51_RECENT_FORM_LAST5_TOP3_V1`。現V5 coreには入れない。
- Priority: **Recent Form last5 → Exhibition time → start-exhibition course movement → weather/water**。
- Exhibition ST latest run `37185447967`: 2,050 evaluated、overall改善なし。retuneせず収集継続。
- 取得と採用は分離: 精度向上featureのみ採用。不採用でも低コスト・事前取得・provenance明確なら収集継続。

## Safety
- DB write / Production change / LINE / purchase / stake changeなし。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。1回1作業、read-only優先。

## Prospective gate diagnosis — read-only
- V4 10/02・10/03: formal inventoryは両日とも `candidate_artifact_count=0 / valid_capture_count=0 / UNAVAILABLE_NO_VALID_CAPTURE`。
- 原因: current `.github/workflows/candidate-discovery-v4-prospective-freeze.yml` の `RAILWAY_DB_SERVICE='postgres-recovery'` がstale。現Production環境に `postgres-recovery` serviceは存在せず、SoTは `postgres-hobby-fullhistory-candidate-v4`。
- 新fallback dispatcherも同じGitHub workflowをdispatchするため、workflow側を直さない限り将来captureも解消しない。
- S03_M2は停止していない。10/02 logs: S03 matched day=3 / night=4、10/03: day=1 / night=3（window観測値、race/rule upsertのため単純加算uniqueではない）。
- latest gate audit: source S03 rows=142、timing rejected=3、missing motor=0、Motor2 score>0=68、official evaluated=66、pending=1、invalid result=1。
- よってS03 66/100の主因はcollector停止ではなく、frozen S03条件＋Motor2 positive条件＋official settlement待ちで自然増加が遅いこと。

## Next ONE task
**V4 prospective-freeze workflowのDB service参照だけを `postgres-recovery` → `postgres-hobby-fullhistory-candidate-v4` に修正し、安全テストでread-only・no-purchase/no-writeを確認する。**
- gateは下げない。
- 過去10/02・10/03をprospectiveとして再構築しない。
- S03 collectorは変更しない。
- economics backtestはまだ実行しない。

`SELECTION_FROZEN_2742_V4_1522_V5 / SHARED_70164 / FREEZE_SHA_7627BE7B / LIVE_GATES_NEXT / ONE_TASK_ONLY / COST_LE_20`
