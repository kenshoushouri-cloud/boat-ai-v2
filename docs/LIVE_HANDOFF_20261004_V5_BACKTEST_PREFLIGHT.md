# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Critical path: **historical core residual補完 → V5 live gates達成 → matched-contract backtest → V4比較 → 運用方式確定 → archive最適化 → 運用開始**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。

## Frozen backtest contract — Draft PR #536
- V5 candidate = `V5_M2_TOP2_BOTH_POSITIVE_V1`。
- V4 TOP6/TOP2を維持し、V4 TOP2各ticketへfrozen Motor2 score（6艇内z-score、weights 1.0/0.6/0.3、score>0）を適用。**2点ともpassしたraceだけ採用**。
- odds/EVはselectionに使わない。100円/点、TOP2=200円/race。
- shared split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。window間retune禁止。
- 評価: ROI、月間利益、購入数/額、的中率、最大DD、連敗。候補1日1race以上は目安、月間利益目標**+50,000円**。volume/点数/stake水増し禁止。

## Live gate state — 2026-10-04 read-only audit
- V4 resolved formal days = **9 / 20**。2026-10-01 formal artifactは6 raceの結果欠落で未resolved。
- S03_M2 officially evaluated = **66 / 100**。
- evidence contract = **clean / PASS**。
- historical matched-readiness audit = **PASS_READ_ONLY**だが full reconstructed V4 core = **47,431 / 70,170 races = 67.59%**。
- 最大の直近残差はOpponent replay。2026-09は **144 / 4,656 races**、full coreは **117 / 4,656 = 2.51%**。
- live audit workflow run **37180999192 = SUCCESS**。DB write / Production changeなし。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。不要なservice/job/DB/volume追加を避ける。
- **1回に1作業 / 短い出力 / read-only優先**。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。
- purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。live値は必要時だけ再取得。

## Next ONE task
**2026-09 historical Opponent replay不足の原因と、安全なfill-missing-only補完経路をcurrent mainで特定する。**
- backtest economicsはまだ実行しない。
- 低コスト優先。Production/Railway設定は変更しない。

`MID_OCT_LAUNCH / V5_SPEC_SPLIT_FROZEN_PR536 / V4_9_OF_20 / S03_66_OF_100 / HIST_CORE_67_59 / OPPONENT_REPLAY_NEXT / COST_LE_20 / ONE_TASK_ONLY`
