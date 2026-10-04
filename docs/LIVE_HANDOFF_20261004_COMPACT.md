# Compact Handoff — 2026-10-04

## 目的 / 期限
- 新競艇AIのProduction運用開始目標: **2026年10月中旬**。
- Productionは **V4**。V5/V5.1は**research-only**で、明示承認なしにProductionへ昇格しない。
- Railway費用目標: **月USD20以下**。不要なservice/job/DB/volume/重い再計算を増やさない。

## 固定運用ルール
- 1回に1作業。出力は短くする。
- Production current data SoT: `postgres-hobby-fullhistory-candidate-v4`。
- V5 frozen candidate: `V5_M2_TOP2_BOTH_POSITIVE_V1`。TOP2=2点、100円/点、200円/race。odds/EV不使用。
- historical reconstructionはbacktest専用。prospective gate creditに使わない。
- featureは**取得と採用を分離**。採用はVALIDATION/OOS + Forwardで精度向上確認後のみ。不採用でも低コスト・pre-race・provenance明確なら収集継続。
- Railway Agent/AI、`list_variables`、`railway variable list`は禁止。
- purchase/LINE/stake/plan/volume resize/TOTO staged patchを変更しない。

## 現在地
- Historical matched selectionはpre-outcome freeze済み: shared **70,164** / V4 **2,742** / V5 **1,522**。
- Prospective gatesは直近確認で **V4 9/20、S03_M2 66/100、evidence clean → BLOCKED**。gateは下げない。economics backtestは未実行。
- V4 prospective-freezeのstale DB service問題は修正済み。過去日のprospective証拠は後付け再構築しない。
- Recent Form last5はblind VAL/OOSでLogLoss/Brier改善したがmean rank悪化のため**不採用**。収集は継続。
- Exhibition Time historical coverage: 全体91.63%、OOS67.60%。OOS missing **4,703 races**は主にbackfill未完。
- 最小コスト方針: Exhibition-Time-onlyで **4,703 HTTP**（generic 12,424より約62%削減）、Jul 53 / Aug 2,086 / Sep 2,564。
- Exhibition-Time-only modeはPR #544で実装済み。candidate-v4対象、weather/ST/tilt/courseは書かず、time/rank/diffのみmissing-fill。
- **Jul pilot実施済み**: target53 / HTTP53 / fetch failure0。ただしrealtime parserでは展示parse **0行**、DB更新**0行**で安全停止。Jul missing 53は未解消。
- pilot後: DB約4.389GB、WAL約83.9MB、volume約4,670.8/5,000MB。Aug/Sepは未実行。

## 次の1作業
**Exhibition-Time-onlyをhistorical parser v3へ切替え、parse qualityをfail-closed化して安全テストだけ通す。再pilotはまだ実行しない。**

条件:
- 既存53件へ再HTTP/DB writeしない安全テストを優先。
- parser出力が6艇・展示タイム妥当値を満たさなければwrite禁止。
- result/odds/payout read禁止。
- Production/LINE/purchase変更なし。
- parser修正PASS後にのみJul 53再pilotを別作業として検討。Aug/SepはそれまでBLOCK。

## 次チャット運用
最初に読むのは:
1. `docs/HANDOFF_LATEST.md`
2. そこが指定するcurrent compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoffは履歴。必要時だけ参照。
handoff内のSHA/run/件数/容量は固定値にせず、**次の1作業に必要なものだけlive再取得**する。

`PROD_V4 / V5_RESEARCH_ONLY / COST_LE_20 / JULY_PILOT_ZERO_WRITE / PARSER_V3_FIX_NEXT / AUG_SEP_BLOCKED / ONE_TASK_ONLY`
