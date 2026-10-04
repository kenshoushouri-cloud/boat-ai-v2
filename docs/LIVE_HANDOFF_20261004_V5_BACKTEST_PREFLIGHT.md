# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Critical path: **reconstructed Opponent artifact統合 → historical readiness → V5 live gates → matched-contract backtest → V4比較 → 運用方式確定 → archive最適化 → 運用開始**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。

## Frozen backtest contract — Draft PR #536
- V5=`V5_M2_TOP2_BOTH_POSITIVE_V1`。V4 TOP6/TOP2維持＋frozen Motor2。2点ともscore>0のraceだけ採用。
- odds/EV不使用。100円/点、TOP2=200円/race。候補1日1race以上は目安、月間利益目標**+50,000円**。水増し禁止。
- split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。retune禁止。

## Live gates / Opponent
- V4 resolved formal days=**9/20**、S03_M2=**66/100**、evidence clean。
- 2026-09 Opponent: 4,656 races。既存usable=3,168、no-row=0、invalid-existing=1,488(9/1..9/10)。
- **9/1..9/10の1,488/1,488をstrict prior-onlyで非永続再構築済み**。run `37182477262` SUCCESS。
- artifact SHA256=`7c050718beede6f0efbb845bd5d2a7d22ce15d0eaf63e7e304f69b6c7a183bfd`、GitHub Actions retention=14日。
- DB_WRITE=0 / existing rows changed=0 / target outcome read=0 / Production change=0。既存v2をoverwrite/deleteしない。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。1回1作業、read-only優先。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。

## Next ONE task
**再構築Opponent artifactをmatched-contract readiness/backtest inputへread-onlyで統合し、残るhistorical core不足だけを再判定する。**
- economics/backtest結果はまだ見ない。
- DBへのOpponent書き込みはしない。

`MID_OCT_LAUNCH / V5_PR536 / OPP_1488_RECONSTRUCTED / V4_9_OF_20 / S03_66_OF_100 / ARTIFACT_INTEGRATION_NEXT / COST_LE_20 / ONE_TASK_ONLY`
