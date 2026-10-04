# Compact Handoff — 2026-10-04

## 目的・固定条件
- Production運用開始目標: **2026年10月中旬**。
- Production=**V4**。V5/V5.1=**research-only**。
- Railway費用: **月USD20を上限**。精度・安定性・必要データ取得を損なわない範囲で可能な限り安くする。USD15以下も歓迎。
- 1回に1作業。Production current data SoT=`postgres-hobby-fullhistory-candidate-v4`。
- V5 frozen candidate=`V5_M2_TOP2_BOTH_POSITIVE_V1`。
- Railway Agent/AI、`list_variables`、`railway variable list`禁止。
- purchase/LINE/stake/plan/volume resize/TOTO staged patch変更禁止。
- historical reconstructionはbacktest専用。prospective gate creditに使わない。

## 現在地
- Live gates: **V4 9/20、S03_M2 66/100 → BLOCKED**。gateは下げない。
- Recent Form last5はblind VAL/OOSで不採用、収集継続。
- Exhibition Time OOS missing **4,703**。低コストExhibition-Time-only modeを使用。
- Jul missing **53**は再pilot済み: HTTP53 / fetch failure0 / DB write0。6艇quality gateを満たさずfail-closed停止。Aug/Sep未実行。
- PR #555で `official_absent` を追加。分類は `complete / official_partial / official_absent / parser_failure`。partial/absentはwrite禁止、6艇有効値のみwrite gateへ進む。
- Jul 53件: **official_partial 39 / zero-value 14 / complete 0**。zero-value代表3件は6艇行あり・展示タイム全空欄。
- 直近storage read-only: DB **4,390,311,615B** / WAL **83,886,080B** / volume **4,670.824448/5,000MB**。

## 次の1作業
**zero-value代表3件だけをread-only再分類し、新 `official_absent` が実データで成立するか確認する。**

条件:
- 最大HTTP3 / DB writeなし / Railway設定変更なし。
- result・odds・payout read禁止。Production/LINE/purchase変更なし。Aug/Sep禁止。

## 次チャット
最初に読むのは `HANDOFF_LATEST.md` → current compact → `NEXT_CHAT_START_HERE.md` の3点だけ。
古いhandoffは履歴。SHA/run/件数/容量は必要時のみlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / COST_MINIMIZE_LE_20 / OFFICIAL_ABSENT_MERGED / VERIFY_3_NEXT / AUG_SEP_BLOCKED / ONE_TASK_ONLY`
