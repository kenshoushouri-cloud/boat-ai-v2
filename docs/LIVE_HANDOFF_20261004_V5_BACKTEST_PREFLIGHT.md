# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標 = **2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Critical path: **Opponent gap是正/補完 → V5 live gates達成 → matched-contract backtest → V4比較 → 運用方式確定 → archive最適化 → 運用開始**。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。

## Frozen backtest contract — Draft PR #536
- V5 candidate = `V5_M2_TOP2_BOTH_POSITIVE_V1`。V4 TOP6/TOP2維持＋frozen Motor2 score。2点ともscore>0のraceだけ採用。
- odds/EV不使用。100円/点、TOP2=200円/race。
- split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。retune禁止。
- 候補1日1race以上は目安、月間利益目標**+50,000円**。volume/点数/stake水増し禁止。

## Live gate state
- V4 resolved formal days = **9/20**。S03_M2 = **66/100**。evidence contract = clean。
- historical readinessはread-only PASSだが、現行auditはOpponentを**model_version=102だけ**数えるため full core=67.59%。

## Opponent gap finding
- current replayは安全: **model_version=102 / strict prior-only / target outcome read=0 / <=7日 / ON CONFLICT(race_id) DO NOTHING**。
- ただし既存Opponent workflowsはまだ旧`postgres-recovery`向け。candidate-v4へはそのまま使わない。
- `v2_opponent_pressure_shadow_v2`は**race_id primary key**。既存のtiming-clean Production `model_version=2`行があるraceには102を追加できず、overwriteもしない。
- 一方、current readinessは102以外を明示的に無効扱いするため、2026-09の低coverageには**実欠損＋valid v2行を数えていない見かけ上の欠損**が混在する。
- 安全方針: **row自体が無いraceだけ102でfill-missing-only**。既存v2は保持し、readiness側でtiming-clean v2を別provenanceとして受理する。v2→102上書き/削除/schema変更はしない。

## Cost / safety
- Railway cost <= **USD20/month、安いほど良い**。1回1作業、read-only優先。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。

## Next ONE task
**Opponent readinessを `historical102 OR timing-clean forward-v2` のprovenance-aware判定へ安全に拡張し、candidate-v4で真のmissing race数をread-only再計測する。**
- まだDB write/backtest economicsは実行しない。
- その結果で、102 fillが必要な日付だけ最小範囲に確定する。

`MID_OCT_LAUNCH / V5_PR536 / V4_9_OF_20 / S03_66_OF_100 / OPP_PROVENANCE_FIX_NEXT / COST_LE_20 / ONE_TASK_ONLY`
