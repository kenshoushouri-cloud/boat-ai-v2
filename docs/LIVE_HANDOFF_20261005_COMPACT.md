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

## Backtest retention / exclusion policy
- formal backtestの基本対象期間は**2025-07-01以降の全期間**。
- この期間の、予測精度検証に必要なraw/historyは原則保持する。odds/result/weather/wave/motor/boat/course等を容量だけを理由に期間切りして捨てない。
- **精度悪化または採用gate FAILが確認された特徴量/使い方だけを、全期間でmodel/backtest入力から除外**する。
- 「ある補正式が悪化」≠「raw情報自体を削除」。rawが別の有効用途を持つ場合は保持する。
- 不採用情報も、低コストで取得可能なら収集継続し、将来再検証できるようarchive優先。削除は最後。
- **分類を混同しない**:
  - **除外確定（現仕様REJECT）**:
    - Recent Form last5 current spec: blind VAL/OOS gate FAIL → 現仕様はmodel入力から除外。収集継続。payloadはarchive候補。
    - Wave residual after market+Motor2+exhibition: rejected。**そのresidual設計のみ除外**。
    - Wind-speed residual after market+Motor2+exhibition: rejected。**そのresidual設計のみ除外**。
    - Global motor shrinkage: REJECT_GLOBAL_SHRINKAGE。**一律補正だけ除外**。
    - Naive prob*odds EV / high model-vs-market edge: reliability/ROI悪化が確認された**そのselector設計だけ除外**。
  - **未採用・研究継続（削除/archive対象にしない）**:
    - Exhibition ST: frozen historical OOSはPROMISING、Forward最新はoverall悪化でNOT_YET_ROBUST。**REJECT確定ではない**。
    - Exhibition Time: robust historical/OOS candidate。Forward evidence待ち。
    - Individual racer×own course×opponent course/class affinity: unstable OOS / do not use yet。**未採用保留**。
    - Relative wind-direction: historical coverage不足。**未評価保留**。
    - frozen V5 deferred items（l_count / exhibition_st / exhibition_time / weather_water / odds_ev_selector等）は、deferred=不採用ではない。
  - **採用・保持/評価継続**:
    - Motor/Boat fixed OOSは改善側。
- raw情報と派生補正を分離する。特定residualがREJECTでも、wave/wind/course/motor/odds等のrawは正式backtest用に保持する。

## 現在地
- Live gate: V4 **9/20**、S03_M2 **66/100** → BLOCKED。gateは下げない。
- Exhibition Time補完は**一時停止中**。Jul terminal=53、Aug04/05各2件official_partialをterminal登録し、合計**57**。partial/absentはwrite禁止。
- candidate-v4 volume直近live約**4.673GB / 5GB**、archive約**0.523GB / 5GB**。容量値は行動前にlive再取得。
- candidate-v4 footprint直近: DB約**4.392GB**、WAL約**83.9MB**。
- exact duplicate / same-key duplicate indexは直近read-only診断で**0件**。
- PR #576 merged。candidate-v4 read-only固定motor/boatアブレーション（2026-07-01..08-15、7311 races）:
  - MOTOR vs BASE logloss delta **-0.002996**
  - BOAT vs BASE **-0.000678**
  - BOTH vs BASE **-0.003682**
  - negative=改善。motor/boatはarchive候補ではない。
- Recent Form last5はblind VAL/OOSで**不採用**、収集は継続。
- Recent Form storage: relation約**933MB**、recent_form列約**659MB**、nonempty約418k rows。
- Production主要entrypoint / frozen V5 coreはRecent Form直接依存なし。research readiness/diagnosticには依存があるため、**column自体は残しpayloadのみarchive候補**。
- archive側にはRecent Form payload全量を受ける容量余裕あり。ただしcandidate側の物理回収にはrewriteが必要で、現在空き約327MBではWAL/一時領域込みで危険。まだ移動・削除しない。
- `v2_v24_motor2_forward_shadow`等research/shadowだけでは、安全に即時400MB超を空ける候補は未発見。
- `v2_realtime_odds_snapshots`等は全期間backtest保持対象なので、容量目的の期間archiveはしない。
- REJECT確定の専用storage再監査:
  - Wave residual / Wind-speed residual: rejected版はread-only in-memory計算で専用永続payloadなし。wave/wind名の既存派生relation合計も約0.295MBで、しかも別研究を含むため削除対象にしない。
  - Global motor shrinkage: read-only backtest計算のみ。専用table/payloadなし。
  - Naive prob*odds / model-vs-market edge: `v2_candidate_filter_shadow`をread-only評価。専用tableではなく、S01-S05/N01/N02等の他研究と共有し、raw_ev等もルール評価で使用されるため容量整理対象にしない。
  - よって現時点で**物理容量に効く明確なREJECT専用payloadはRecent Form current-spec（約659MB）が唯一の主要候補**。

## Next ONE task
**Recent Form current-specが唯一の主要なREJECT容量候補と確認できたため、同一5GB volume内rewriteを避けて物理容量を安全に回収する方法をread-onlyで設計する。Railway内の短命なcompact rebuild/cutover案を、費用<=USD20・復元/parity・全期間backtest保持条件で比較する。**

条件:
- まだ移動・削除しない。
- DB/Production/Railway設定を変更しない。
- 2025-07-01以降の正式backtest必須rawを削らない。
- raw全体ではなく、悪化が確認された特徴量/派生payload単位で評価する。

## 次チャット
最初に読むのは `HANDOFF_LATEST.md` → current compact → `NEXT_CHAT_START_HERE.md` の3点だけ。
SHA/run/件数/容量は固定値扱いせず、次の1作業に必要なものだけlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / FULL_BACKTEST_FROM_202507 / EXCLUDE_HARMFUL_FEATURES_ONLY / CAPACITY_FIRST / BACKFILL_PAUSED / COST_MINIMIZE_LE_20 / ONE_TASK_ONLY`
