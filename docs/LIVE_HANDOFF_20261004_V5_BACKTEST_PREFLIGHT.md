# Live Handoff — V5 Matched-Backtest Preflight\n\n## Goal / contract\n- 運用開始目標=**2026年10月中旬**。Production=**V4**、V5=**research-only**。Railway<=**USD20/month**。\n- V5=`V5_M2_TOP2_BOTH_POSITIVE_V1`。100円/点、TOP2=200円/race。odds/EV不使用。split固定済み、retune禁止。\n- V4/V5ともCourse missing laneは**neutral**。historical結果を見てCourse-complete-onlyへ変更しない。\n\n## Historical inputs\n- Opponent 2026-09-01..10は**1,488/1,488 strict prior-only再構築済み**。DB非変更。\n- Course-complete=58,412/70,170。gap=11,758だがneutral扱いでhard blockerではない。\n- V4 prospective=**9/20 days**、S03_M2=**66/100**、evidence clean。\n\n## Course complete vs neutral diagnostic — run 37184436582 SUCCESS\n- 毎日V4 TOP6を**結果参照前に凍結**。frozen races=**2,742**、TOP2×100円。同じV4契約でcohort分離。\n- Course complete: evaluated **1,913** / hit **20.86%** / ROI **80.42%** / profit **-74,900円** / maxDD **85,130円** / max losing **42**。\n- Course neutral-missing: evaluated **800** / hit **20.00%** / ROI **71.31%** / profit **-45,900円** / maxDD **46,330円** / max losing **35**。\n- completeはROI **+9.11pt**、hit rate **+0.86pt**。月別ROIは**15か月中11か月**でcompleteが上。\n- bootstrap 95% ROI CI: complete **71.09–90.27%**、neutral **60.07–84.01%**。重なりがあり、Course欠損だけの因果差とは断定しない。\n- 両群ともoverall ROI<100%。この結果でselector/gateを後付け変更しない。診断専用。\n\n## V5.1 feature research lane
- Intake: `docs/V51_EXTERNAL_PREDICTION_KNOWLEDGE_INTAKE_20261004.md`。
- First candidate: `V51_RECENT_FORM_LAST5_TOP3_V1`。仕様=`docs/V51_RECENT_FORM_FIRST_CANDIDATE_20261004.md`。
- Exhibition ST最新run `37185447967`: **2,050 evaluated / timing-invalid 0**。frozen beta=-0.02はoverall tri Brier/LogLoss/rankを僅かに悪化 → retuneせず優先度を下げる。
- Priority: **Recent Form last5 → Exhibition time → start-exhibition course movement → weather/water**。
- 現V5 coreはscope-lock維持。V5.1はTRAINで1回freeze→VALIDATION/OOS no-retune→Forward再現後のみ採用検討。

## Collection/adoption separation
- 精度向上が確認できたfeatureだけV4/V5.xへ採用する。
- 不採用featureでも、将来再検証価値があり**低コスト・deadline前・provenance明確**なら取得は継続する。
- 「使わない」≠「収集停止」。collector停止はcost/storage/将来価値を別途判断する。
- baselineやsample数が変わった時にunused featureを再評価可能にする。

## Safety\n- DB write / Production change / LINE / purchase / stake changeなし。\n- Railway Agent/AI、`list_variables` / `railway variable list`禁止。1回1作業、read-only優先。\n\n## Next ONE task\n**frozen neutral-missing V4/V5契約のまま、matched-backtestで本当に評価可能なrace集合を結果参照前に確定する。**\n- Course完全性をhard gate化しない。\n- economics本体はprospective gate条件とpreflightを守る。\n\n`COURSE_DIAG_DONE / COMPLETE_ROI_80_42 / NEUTRAL_ROI_71_31 / NO_POST_OUTCOME_RETUNE / SAME_CONTRACT_READINESS_NEXT / ONE_TASK_ONLY`\n