# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 競艇AIを安全に本番運用可能な状態へ完成。運用開始目標 = **2026年10月中旬**。
- Critical path: **V5比較仕様/time split固定 → matched-contract backtest → V4比較 → 運用方式確定 → historical archive最適化 → 運用開始**。
- Production = **V4**。V5 = **research-only**。historical reconstructionはbacktest用でProspective gateへ加算しない。

## Current
- GitHub `main` = code SoT。
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`。
- Historical Recent Form = **2026-09-30まで補完済み**。final read-only auditで残差がなければ取得完了扱い。
- Draft PR **#536** = matched-contract backtest fail-closed preflight。Railway実行なし、Production変更なし、未merge。

## Backtest contract
- **current V4 / V5 candidate core / optional V5.1** を **same time split / no-leakage / same-contract** で比較。
- V5仕様とtime splitは**結果を見る前に固定**。V5がV4と実質同一なら比較扱いにしない。
- 評価はROIだけでなく、月間利益・購入数・購入額・的中率・最大DD・連敗も確認。
- Economics: **100円/点、TOP2=2点=200円/レース、候補は1日1レース以上を目安、月間利益目標 +50,000円**。
- 候補数・購入点数・stakeを水増しして目標達成しない。Backtest結果だけでProductionへ自動昇格しない。

## Cost / safety
- Railway cost hard target = **USD 20/month以下、安いほど良い**。不要なservice/job/DB/volume追加を避ける。
- **1回に1作業 / 短い出力 / read-only優先**。
- Railway Agent / Railway AI禁止。`list_variables` / `railway variable list`禁止。
- purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認が必要。
- SHA・run・件数・容量はhandoff値を固定視せず、必要時だけlive再取得。
- 古いhandoffは特定の過去判断が必要な時だけ参照。

## Next ONE task
**V5 research candidateの比較仕様とshared chronological time splitを、結果参照前のresearch-only contractとして固定する。**
- Production/Railway設定は変更しない。
- PR #536のpreflight条件に適合させる。
- backtest実行はこの固定完了後。

`MID_OCT_LAUNCH / V5_SPEC_SPLIT_FREEZE_NEXT / V4_PRODUCTION / HIST_COMPLETE / ECON_100YEN_TOP2_50K / COST_LE_20 / ONE_TASK_ONLY`
