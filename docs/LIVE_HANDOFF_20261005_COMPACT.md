# Compact Handoff — 2026-10-05

## 目的・期限・固定条件
- Production運用開始目標: **2026年10月中旬**。
- Production=**V4**。V5/V5.1=**research-only**。Production current data SoT=`postgres-hobby-fullhistory-candidate-v4`。
- Railway費用は**月USD20以下**、可能ならUSD15以下。精度・安定性・必要データ取得を損なわない範囲で最小化。
- 1回に1作業。Railway Agent/AI、`list_variables`、`railway variable list`禁止。
- purchase/LINE/stake/plan/volume resize/TOTO staged patch変更禁止。

## 現在地
- Live gates: V4 **9/20**、S03_M2 **66/100** → BLOCKED。gateは下げない。
- Exhibition Time不足補完は**容量対策のため一時停止**。Jul terminal=53。Aug04/05は各2件official_partialでwrite0、terminal登録済み。terminal合計**57**。
- candidate-v4 volumeは直近liveで約**4.673GB / 5GB**。archiveは約**0.523GB / 5GB**。容量値は行動前にlive再取得。
- Recent Form last5はblind VAL/OOSで**不採用**、収集は継続。
- Recent Form storage read-only: relation約**933MB**、recent_form列約**659MB**。容量整理候補だが、依存関係確認前に削除・移動しない。
- PR #576 merged。candidate-v4 read-only固定アブレーション実行済み（2026-07-01..08-15、7311 races）。
  - MOTOR vs BASE: logloss delta **-0.002996**
  - BOAT vs BASE: **-0.000678**
  - BOTH vs BASE: **-0.003682**
  - negative=改善。現証拠ではmotor/boatは削除候補ではない。
- 上記アブレーションはDB write/Production変更なし。

## 次の1作業
**Recent Formを全期間archive候補にできるか、Production/V4・frozen V5・現行backtestの依存関係をread-onlyで確認する。**

条件:
- まだ移動/削除しない。
- 容量解放量と安全な退避/復元方法を確認してからarchive判断。
- candidate-v4の5GB headroom確保を不足データ補完再開より優先。
- formal V5 backtestは不足データ処理と容量対策後。今回のアブレーションは容量整理用の予備評価。

## 次チャット
最初に読むのは `HANDOFF_LATEST.md` → current compact → `NEXT_CHAT_START_HERE.md` の3点だけ。
古いhandoffは大量参照しない。SHA/run/件数/容量は必要時だけlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / CAPACITY_FIRST / BACKFILL_PAUSED / RECENT_FORM_AUDIT_NEXT / COST_MINIMIZE_LE_20 / ONE_TASK_ONLY`
