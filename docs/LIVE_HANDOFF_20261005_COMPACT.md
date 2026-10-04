# Compact Handoff — 2026-10-05

## 目的・期限
- Production運用開始目標: **2026年10月中旬**。
- Production=**V4**。V5/V5.1=**research-only**。current data SoT=`postgres-hobby-fullhistory-candidate-v4`。
- Railway費用は**月USD20以下**、可能ならUSD15以下。精度・安定性を落とさず最小化。
- 容量確保を不足データ補完より優先。formal V5 backtestは容量対策＋不足データ処理後。

## 固定条件
- **1回に1作業**。古いhandoffは大量参照しない。
- Railway Agent/AI、`list_variables`、`railway variable list`禁止。
- purchase / LINE / stake / plan / volume resize / TOTO staged patch変更禁止。
- historical reconstructionは研究/backtest専用。prospective gate creditに使わない。

## 現在地
- Live gate: V4 **9/20**、S03_M2 **66/100** → BLOCKED。gateは下げない。
- Exhibition Time補完は**一時停止中**。Jul terminal=53、Aug04/05各2件official_partialをterminal登録し、合計**57**。partial/absentはwrite禁止。
- candidate-v4 volume直近live約**4.673GB / 5GB**、archive約**0.523GB / 5GB**。容量値は行動前にlive再取得。
- PR #576 merged。candidate-v4 read-only固定motor/boatアブレーション実施済み（2026-07-01..08-15、7311 races）。
  - MOTOR vs BASE logloss delta **-0.002996**
  - BOAT vs BASE **-0.000678**
  - BOTH vs BASE **-0.003682**
  - negative=改善。motor/boatは現時点でarchive候補ではない。
- Recent Form last5はblind VAL/OOSで**不採用**、収集は継続。
- Recent Form storage read-only: relation約**933MB**、recent_form列約**659MB**。容量整理候補だが依存確認前に移動/削除しない。

## 方針
- 予測精度を一貫して悪化させる情報はモデルで使わず、**全期間をarchive退避候補**にする。取得は継続し将来再検証可能にする。
- 削除よりarchiveを優先。退避前に依存関係・解放容量・復元方法を確認する。

## Next ONE task
**Recent Formを全期間archive候補にできるか、Production/V4・frozen V5・現行backtestの依存関係をread-onlyで確認する。**

条件:
- まだ移動・削除しない。
- DB/Production/Railway設定を変更しない。
- 安全な退避/復元方法と想定解放容量を確認してからarchive判断。

## 次チャット
最初に読むのは `HANDOFF_LATEST.md` → current compact → `NEXT_CHAT_START_HERE.md` の3点だけ。
SHA/run/件数/容量は固定値扱いせず、次の1作業に必要なものだけlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / CAPACITY_FIRST / BACKFILL_PAUSED / RECENT_FORM_AUDIT_NEXT / COST_MINIMIZE_LE_20 / ONE_TASK_ONLY`
