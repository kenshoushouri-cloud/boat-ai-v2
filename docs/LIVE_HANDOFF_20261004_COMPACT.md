# Compact Handoff — 2026-10-04

## 目的 / 期限
- 新競艇AIのProduction運用開始目標: **2026年10月中旬**。
- Productionは **V4**。V5/V5.1は**research-only**で、明示承認なしにProductionへ昇格しない。
- Railway費用方針: **月USD20以下を上限**とし、精度・安定性・必要なデータ取得を損なわない範囲で**可能な限り低コスト化する**。USD15以下にできる場合も積極的に削減する。
- 不要なservice/job/DB/volume/常時稼働/重い再計算を増やさず、新たなコスト増は必要性を確認してから行う。

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
- **Jul pilot実施済み**: target53 / HTTP53 / fetch failure0。ただし旧realtime parserでは展示parse **0行**、DB更新**0行**で安全停止。Jul missing 53は未解消。
- Exhibition-Time-only parser修正は **PR #548 merged / commit `28c9f56bc09961e6b19dd65caa07b95d8e4914bd`** で最終化。historical parser v3へ切替え、6艇＋time/rank/diff妥当性NGはwrite禁止、**対象がある各日でusable=0ならbatch FAIL**。
- safety run `37194597909` は **17 tests PASS**。candidate-v4 July plan-onlyも **target53 / HTTP=0 / DB write=0 / parser-v3 wired** でPASS。
- **Jul 53再pilotは既に実行済み**: historical parser v3使用53/53、HTTP53、fetch failure0、usable six-lane=0、quality gate blocked=53、DB write=0、`FAIL_PARSE_QUALITY`。Aug/Sepは未実行。
- storage read-only再確認: DB **4,390,311,615B** / WAL **83,886,080B** / volume **4,670.824448/5,000MB**。persistent growthなし。
- PR #549 mergedで1件read-only診断を追加。sample `20260701_10_08`（2026-07-01 戸田8R）は公式beforeinfoで1号艇の展示タイムが空欄、候補値は5艇分のみ。historical/realtime parserとも0行。少なくともこの例はmarkup不適合ではなく**official partial data**。

## Classification safety — COMPLETE
- PR **#550 merged / commit `0d0fd17f32d53a4f56e11a3563c34690fe6205b3`**。
- historical parser/backfillは `complete` / `official_partial` / `parser_failure` を明示分類。
- structured 1〜5艇の妥当な展示タイムは `official_partial` として件数可視化するが、**DB write/commit禁止**。
- 0艇/構造不明は `parser_failure`。6艇のみ既存time/rank/diff quality gateへ進む。
- batch fail statusも partial-only と parser-failure を区別。どちらもfail-closed。
- safety CI PASS。candidate-v4 July plan-onlyも **HTTP=0 / DB write=0**、backfill jobはSKIP。

## 次の1作業
**Jul欠損から少数サンプルだけread-only HTTP分類し、`official_partial` と `parser_failure` の実データ比率を確認する。53件全再HTTPはまだしない。**

条件:
- DB writeなし。Railway設定変更なし。
- 既知sample `20260701_10_08` のほか、異なる日から最小限のサンプルを選ぶ。
- result/odds/payout read禁止。
- Production/LINE/purchase変更なし。
- Aug/Sep禁止。少数sampleでparser failureが残るか確認してから次判断。

## 次チャット運用
最初に読むのは:
1. `docs/HANDOFF_LATEST.md`
2. そこが指定するcurrent compact handoff
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoffは履歴。必要時だけ参照。
handoff内のSHA/run/件数/容量は固定値にせず、**次の1作業に必要なものだけlive再取得**する。

`PROD_V4 / V5_RESEARCH_ONLY / COST_MINIMIZE_LE_20 / PARTIAL_CLASSIFICATION_MERGED / MIN_HTTP_CLASSIFY_NEXT / AUG_SEP_BLOCKED / ONE_TASK_ONLY`
