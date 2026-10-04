# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Critical path: **Opponent 9/1..9/10 collision-safe reconstruction → V5 live gates → matched-contract backtest → V4比較 → 運用方式確定 → archive最適化 → 運用開始**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。

## Frozen backtest contract — Draft PR #536
- V5 candidate = `V5_M2_TOP2_BOTH_POSITIVE_V1`。V4 TOP6/TOP2維持＋frozen Motor2 score。2点ともscore>0のraceだけ採用。
- odds/EV不使用。100円/点、TOP2=200円/race。
- split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。retune禁止。
- 候補1日1race以上は目安、月間利益目標**+50,000円**。volume/点数/stake水増し禁止。

## Live gates / Opponent provenance
- V4 resolved formal days = **9/20**。S03_M2 = **66/100**。evidence contract = clean。
- Opponent readinessは **historical102 または timing-clean forward-v2** を明示provenanceで受理する実装をPR #536へ追加。
- 2026-09 lightweight read-only再計測: **4,656 races / usable 3,168 (68.04%) / historical102 144 / timing-clean v2 3,024 / no-row 0 / invalid-existing 1,488**。
- invalid-existingは **2026-09-01..09-10の全1,488 races**。safe fill-missing-only candidates = **0**。
- よって既存rowをoverwrite/deleteして102へ置換しない。DBへのOpponent fillは現時点で不要。
- full-range readiness再計測は180s timeout。軽量Opponent診断run **37181923203 = SUCCESS**。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。1回1作業、read-only優先。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。

## Next ONE task
**2026-09-01..09-10の1,488 invalid-existing Opponent rowsについて、既存v2を変更せずhistorical102相当を使えるcollision-safe backtest経路をcurrent mainで確定する。**
- DB schema変更/overwrite/deleteはしない。
- storage/費用を増やさない方式（non-persistent/on-the-fly優先）を検討。
- backtest economicsはまだ実行しない。

`MID_OCT_LAUNCH / V5_PR536 / V4_9_OF_20 / S03_66_OF_100 / OPP_NO_ROW_0 / OPP_INVALID_1488 / COLLISION_SAFE_NEXT / COST_LE_20 / ONE_TASK_ONLY`
