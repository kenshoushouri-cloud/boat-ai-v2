# Live Handoff — V5 Matched-Backtest Preflight

## Goal / current
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。Historical Recent Formは**2026-09-30まで補完済み**。
- Draft PR **#536** = V5比較仕様 + shared time split + fail-closed preflight。未merge。

## Frozen backtest contract
- V5 = `V5_M2_TOP2_BOTH_POSITIVE_V1`。V4 TOP6/TOP2を維持し、各TOP2 ticketへfrozen Motor2 score（6艇内z-score / weights 1.0,0.6,0.3 / score>0）を適用、**2点ともpassしたraceだけ採用**。
- odds/EVはselectionに使わない。**100円/点、TOP2=200円/race**。
- shared split = **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。window間retune禁止。
- 評価 = ROI / 月間利益 / 購入数・額 / 的中率 / 最大DD / 連敗。候補1日1race以上は目安、月間利益目標 **+50,000円**。volume/点数/stake水増し禁止。

## 2026-10-04 live gate check — candidate-v4
- V4 formal available = **10日**、resolved = **9/20**。10/01は未resolved。
- S03_M2 = **66/100 officially evaluated**（positive 68 / timing rejected 3 / missing motor 0）。
- evidence contract = **clean**。
- historical matched-readiness = **PASS_READ_ONLY**。full reconstructed core = **47,431 / 70,170 = 67.59%**。
- DB write / odds / payout / Production / LINE / BUY / Railway config change = **0**。

## Important boundary
- Historical backtestはprospective gateの代替にはならないが、current policy上 **V4 20日 / S03 100件はhistorical backtest自体の前提とは明記されていない**。
- PR #536は現在これらをbacktest実行blockerにしているため、境界を次作業で修正確認する。Production昇格/凍結review gateとは分離する。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。1回に1作業 / 短い出力 / read-only優先。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。live値は必要時だけ再取得。

## Next ONE task
**PR #536のpreflightを修正し、historical matched-contract backtest readiness と V5 prospective freeze/promotion gates（V4 20 / S03 100）を分離する。**
- backtest結果参照前のV5仕様/time split固定は維持。
- Production/Railway設定は変更しない。

`MID_OCT_LAUNCH / LIVE_V4_9_OF_20 / S03_66_OF_100 / HIST_READINESS_PASS / FIX_GATE_BOUNDARY_NEXT / COST_LE_20 / ONE_TASK_ONLY`
