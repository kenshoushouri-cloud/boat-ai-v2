# Live Handoff — V5 Matched-Backtest Preflight

## Goal / critical path
- 運用開始目標=**2026年10月中旬**。Production=**V4**、V5=**research-only**。
- Production data SoT=`postgres-hobby-fullhistory-candidate-v4`。
- Critical path: **same-contract readiness補正 → V5 live gates → matched-contract backtest → V4比較 → 運用方式確定**。

## Frozen contract — Draft PR #536
- V5=`V5_M2_TOP2_BOTH_POSITIVE_V1`。V4 TOP6/TOP2＋frozen Motor2、2点ともscore>0のraceだけ採用。
- odds/EV不使用。100円/点、TOP2=200円/race。月間利益目標**+50,000円**、候補1日1race以上は目安。水増し禁止。
- split: **2025-07..12 TRAIN_REFERENCE / 2026-01..06 VALIDATION / 2026-07..09 OOS**。retune禁止。

## Historical readiness
- Opponent 9/1..9/10は**1,488/1,488 strict prior-only再構築済み**。DB非変更。9月Opponent=4,656/4,656 usable。
- 厳格な全feature-complete指標はV4 core=**51,760/70,170=73.76%**だが、これは実V4契約より厳しい。
- V4 prospective=**9/20 days**、S03_M2=**66/100**、evidence clean。

## Course gap — read-only診断
- run `37183820418` SUCCESS。Course-complete gap=**11,758 races / 12,741 entries**。
- 別sourceとのunique-key衝突=**0**。3 term proxy inventoryは全て存在・valid。
- 5,699 entries: 同term racer proxyありだが対象courseのprior startなし。current seedではrowを作らない。
- 7,042 entries: 同term racer proxy自体なし。racer_number欠損=0。
- **重要: V4 contractはCourse欠損laneをneutral(0)扱いする。V5も同じV4 probability coreを維持するため、Course完全性はmatched-backtestのhard gateではない。**
- よってCourseを無理にfillするDB writeは行わない。source再取得で完全率を100%へ寄せることを目的化しない。

## Cost / safety
- Railway <= **USD20/month**。1回1作業、短い出力、read-only優先。
- Railway Agent/AI、`list_variables` / `railway variable list`禁止。purchase / plan / volume resize禁止。TOTO staged patchに触れない。
- destructive/config/Production-effect変更は明示承認。

## Next ONE task
**historical readinessを実V4/V5のneutral-missing契約へ合わせ、結果/払戻を見ずにmatched-backtestで本当に評価可能なrace集合を確定する。**
- Course/Opponentのmissingを誤ってhard blockerにしない。
- V5 Motor2 overlayに必要な条件とBase必須条件だけを厳密に確認する。
- economics/backtest結果はまだ実行しない。

`MID_OCT_LAUNCH / V5_PR536 / COURSE_NEUTRAL_NOT_BLOCKER / SAME_CONTRACT_READINESS_NEXT / COST_LE_20 / ONE_TASK_ONLY`
