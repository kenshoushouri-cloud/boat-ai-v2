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

## V4 prospective-freeze fix
- PR `#537` merged, commit `49202477ee3a32bf14a3d2206173ad465f9d2368`。
- `RAILWAY_DB_SERVICE`: stale `postgres-recovery` → `postgres-hobby-fullhistory-candidate-v4`。
- safety run `37186947543` SUCCESS。Critical Python / Production shadow isolation / V21 parser / mojibake guardも全てSUCCESS。
- gate/selector/S03/購入/LINEは変更なし。10/02・10/03をprospectiveとして再構築しない。
- 10/04のscheduled/fallbackはfix merge前に実行済みのため、後からprospective creditを付けない。次の新規正式captureはfuture runのみ。

## V5.1 Recent Form readiness — PRE-OUTCOME
- PR `#538` / run `37187444850` SUCCESS / artifact `11297159857`。
- 全 **70,170 races** / exact6=70,170。Recent Form非neutral評価可能=**69,477 (99.0124%)**。
- V4/V5 shared Motor2-complete母集団 **70,164** 中、Recent Form評価可能=**69,471 (99.0123%)**。
- TRAIN_REFERENCE: **26,801 / 27,456 = 97.6144%**。
- VALIDATION: **28,178 / 28,200 = 99.9220%**。
- OOS: **14,498 / 14,514 = 99.8898%**。
- lane feature usable=**415,482 / 421,020 = 98.6846%**。
- stored recent_form provenance valid=418,442 entries。history items=2,076,922。
- **bad source=0 / bad date=0 / same-day=0 / future=0 / >5 history=0 / bad race_id=0** → prior-day provenance clean。
- outcome/odds/payout read=0 / DB write=0 / Production change=0。
- PR #538はresearch audit用。Production採用を意味しない。

## Recent Form coefficient search — PRE-OUTCOME LOCKED
- lock=`docs/V51_RECENT_FORM_COEFFICIENT_SEARCH_LOCK_20261004.md`。
- gridは **-0.50..+0.50の0.10刻み、11候補のみ**。後から拡張/細分化禁止。
- V4 course-adjusted rawへ `coef * within-race RecentForm z` を加え、それ以外のV4/V5 contractは不変。
- TRAIN_REFERENCE **26,801 races**のみでmean trifecta LogLoss最小の係数を1回選択。
- 係数freeze後にだけVALIDATION **28,178** / OOS **14,492**を評価。retune禁止。
- adoption gate: VALIDATION/OOSの両方で LogLoss改善 + Brier改善 + official trifecta mean rank非悪化。
- 0.00がTRAIN勝者、またはVAL/OOSどちらか失敗なら不採用。情報収集は継続。

## Recent Form TRAIN fit — COEFFICIENT FROZEN
- PR `#539` / run `37188106418` SUCCESS / artifact `11297696908`。
- pre-outcome TRAIN population=**26,801**、population SHA256=`2f62e64fbfec7cadec98af76ec6284ba92c15e40fc6e6aba6c860f9ce1af1a04`。
- official label available=**26,610 / 26,801**、unavailable=191。
- frozen grid 11候補のTRAIN mean LogLoss最小は **Recent Form coefficient = +0.30**。
- baseline coef 0.00: LogLoss **4.2263311279** / Brier **0.9787454838** / official mean rank **25.71665**。
- chosen coef +0.30: LogLoss **4.2002454391** / Brier **0.9777969808** / official mean rank **25.78963**。
- TRAINではLogLoss/Brier改善、mean rankは僅かに悪化。TRAINのprimary objectiveはLogLossなので規定どおり+0.30をfreezeし、採用判定はまだ行わない。
- freeze SHA256=`7b53c68c22ef351b85293205395938c12705ca87f03b50be9d87f196a95c3c9c`。
- VALIDATION/OOS read=0 / odds/payout read=0 / DB write=0 / Production change=0。

## Recent Form blind VALIDATION/OOS — REJECT
- PR `#540` / run `37188634434` SUCCESS / artifact `11297559218`。
- frozen coefficient **+0.30**、TRAIN freeze SHA検証PASS。retune/search=0。
- VALIDATION population **28,178** / official labels **27,725**:
  - baseline LogLoss **4.2126907283** → +0.30 **4.1816792387** = 改善
  - baseline Brier **0.9783780067** → +0.30 **0.9772222647** = 改善
  - baseline mean rank **25.28739** → +0.30 **25.29897** = **0.01158悪化**
  - preregistered gate = **FAIL**
- OOS population **14,492** / official labels **14,397**:
  - baseline LogLoss **4.2005819746** → +0.30 **4.1779239233** = 改善
  - baseline Brier **0.9780025146** → +0.30 **0.9771265313** = 改善
  - baseline mean rank **25.04466** → +0.30 **25.33417** = **0.28950悪化**
  - preregistered gate = **FAIL**
- decision=`REJECT_DO_NOT_ADOPT_CONTINUE_COLLECTION`。
- artifact SHA256=`cb438a9920048ad893d4655144d17848dfb723f0313e6d5c9ef107e1bf33b57d`。
- Recent Formは**現仕様ではV5.1に採用しない**。後付けretune/場別抽出は禁止。データ収集は継続。
- odds/payout read=0 / DB write=0 / Production change=0。

## Exhibition Time readiness — PRE-OUTCOME
- PR `#541` / run `37188984885` SUCCESS / artifact `11298441054`。
- official historical Exhibition Time 6-lane complete = **64,297 / 70,170 = 91.6303%**。
- shared Motor2-complete母集団では **64,297 / 70,164 = 91.6382%**。
- TRAIN_REFERENCE: **26,989 / 27,456 = 98.2991%**。
- VALIDATION: **27,497 / 28,200 = 97.5071%**。
- OOS: **9,811 / 14,514 = 67.5968%**。OOS欠損=**4,703 races**。
- 64,297 racesすべてで exhibition_time_rank / diff も6艇完備。duplicate lane=0。
- source: legacy `official_beforeinfo_historical` **62,205 races**、explicit reconstruction **2,092 races**。
- provenance unknown rows=0。全保存行はBOAT RACE公式historical beforeinfo由来として `PREDEADLINE_BY_NATURE`。
- exact original fetch timestampは不明/不要（historical policy）。prospective evidenceには数えない。
- result/odds/payout read=0 / DB write=0 / Production change=0。

## Exhibition Time OOS gap diagnosis — READ ONLY
- PR `#542` / run `37190349026` SUCCESS / artifact `11298477527`。
- OOS total **14,514 races** / time6 **9,811** / missing **4,703** / coverage **67.5968%**。
- 2026-07: **4,879 / 4,932 = 98.9254%**、missing 53。
- 2026-08: **2,840 / 4,926 = 57.6533%**、missing 2,086。
- 2026-09: **2,092 / 4,656 = 44.9313%**、missing 2,564。
- sourceは7/8月が `official_beforeinfo_historical`、9月complete分が `official_archived_beforeinfo_historical_reconstruction`。
- ZERO日が29日あり、代表的に **8/16..8/27**, **8/31..9/13**, **9/28..9/30**。一方でその後にcomplete/partial日が再出現するため、自然欠損ではなく**backfill実行範囲の不連続**が主因。
- 過去long campaign run `36667954064` は segment 1/2/3 のbackfill jobsが全てcancelled。後続の部分backfillで一部埋まったが、OOSに未完区間が残ったと判断。
- outcome/odds/payout read=0 / DB write=0 / Production change=0。

## Exhibition Time minimal-cost backfill plan — NO EXECUTION
- plan=`docs/V51_EXHIBITION_TIME_MIN_COST_BACKFILL_PLAN_20261004.md`。
- run `37190834004` / artifact `11299500355`。
- targeted Exhibition-Time-only=**4,703 HTTP**、generic current SQL=**12,424 HTTP**。**7,721件 / 約62.15%削減**。
- 0.50s sleep floor: **103.53分 → 39.19分**。
- Jul **53** / Aug **2,086** / Sep **2,564**。Julをpilotにする。
- max new rows=28,218、payload約6.14MB、relation増分目安約10.2MB + transient WAL。
- candidate-v4 disk current≈4.670/5GB、24h max≈4.769GB。毎batch後にdisk/WAL確認。
- generic beforeinfo workflowはstale `postgres-recovery` のため、そのまま実行しない。

## Next ONE task
**Exhibition-Time-only mode + candidate-v4 targetingを実装し、安全テストだけ通す。backfillはまだ実行しない。**
- weather等を理由にHTTP対象を増やさない。
- existing non-null preserve / missing-only。
- result/odds/payout read=0、LINE/purchase/Production change=0。

`EX_TIME_BACKFILL_PLAN_LOCKED_4703 / IMPLEMENT_SAFE_MODE_NEXT / NO_BACKFILL_YET / LIVE_GATES_BLOCKED / ONE_TASK_ONLY / COST_LE_20`
