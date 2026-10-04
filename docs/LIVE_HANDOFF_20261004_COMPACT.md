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
- PR #550でhistorical parser/backfillを `complete / official_partial / parser_failure` に分類。1〜5艇partialは可視化のみでwrite禁止、6艇のみtime/rank/diff gateへ進む。
- 実データread-only診断: 既知1件 + 異なる日5件 = **6/6 official_partial、すべてvalid_times=5、parser_failure=0**。追加診断はHTTP5 / DB write0。
- 直近storage read-only: DB **4,390,311,615B** / WAL **83,886,080B** / volume **4,670.824448/5,000MB**。

## 次の1作業
**Jul missing 53のDB側 `exhibition_time` 件数分布と欠損lane分布だけをread-only確認する。追加HTTPはしない。**

条件:
- DB writeなし / Railway設定変更なし / result・odds・payout readなし。
- Production/LINE/purchase変更なし。
- Aug/Sepはまだ実行しない。
- この確認でJul 53を「official partial由来のunfillable」と扱えるか判断し、次の最小コスト手順を決める。

## 次チャット
最初に読むのは `HANDOFF_LATEST.md` → current compact → `NEXT_CHAT_START_HERE.md` の3点だけ。
古いhandoffは履歴。SHA/run/件数/容量は必要時のみlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / COST_MINIMIZE_LE_20 / JUL_SAMPLE_6_OF_6_PARTIAL / DB_DISTRIBUTION_NEXT / AUG_SEP_BLOCKED / ONE_TASK_ONLY`
