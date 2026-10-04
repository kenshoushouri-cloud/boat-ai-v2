# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Critical path: **V5 preflight → matched-contract backtest → V4比較 → 運用方式確定 → archive最適化 → 運用開始**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。Historical Recent Formは**2026-09-30まで補完済み**。

## Frozen backtest contract — Draft PR #536
- V5 candidate = `V5_M2_TOP2_BOTH_POSITIVE_V1`。
- V4 probability/structural TOP6/TOP2は維持。V4 TOP2各ticketへfrozen Motor2 score（6艇内z-score、weights 1.0/0.6/0.3、score>0）を適用し、**2点ともpassしたraceだけ採用**。
- odds/EVはselectionに使わない。100円/点、TOP2=200円/race。
- shared split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。window間retune禁止。
- 実行条件: **V4>=20 resolved days / S03_M2>=100 official observations / clean evidence / historical readiness PASS**。
- 評価: ROI、月間利益、購入数/額、的中率、最大DD、連敗。候補1日1race以上は目安、月間利益目標**+50,000円**。volume/点数/stake水増し禁止。
- PR #536はDraft・CI SUCCESS・未merge。Railway実行なし、Production変更なし。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。不要なservice/job/DB/volume追加を避ける。
- **1回に1作業 / 短い出力 / read-only優先**。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。
- purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。live値は必要時だけ再取得。

## Next ONE task
**candidate-v4をread-onlyで確認し、V4 20日 / S03_M2 100件 / clean evidence / historical matched-readiness のlive gate状態だけ判定する。**
- backtest economicsはまだ実行しない。
- 低コスト優先。Production/Railway設定は変更しない。

`MID_OCT_LAUNCH / V5_SPEC_SPLIT_FROZEN_PR536 / LIVE_GATES_NEXT / ECON_100YEN_TOP2_50K / COST_LE_20 / ONE_TASK_ONLY`
