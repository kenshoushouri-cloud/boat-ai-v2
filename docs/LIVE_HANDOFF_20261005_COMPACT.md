# Compact Handoff — 2026-10-05

## Goal / hard rules
- Production開始目標: **2026年10月中旬**。Production=**V4**、V5/V5.1=research-only。
- Data SoT=`postgres-hobby-fullhistory-candidate-v4`。
- Railway費用 **<=USD20/月、理想<=USD15**。CPU/RAM/Network/AIも最小化。
- **Railway Agent/AI禁止**、`list_variables` / `railway variable list`禁止。
- purchase / LINE / stake / plan / volume resize / TOTO staged patchは触らない。
- **1回に1作業**。古いhandoff大量参照禁止。live値は必要分だけ再取得。

## Backtest policy
- formal backtest対象は**2025-07-01以降の全期間**。
- raw/historyは期間切りで捨てない。
- 「REJECT確定」と「未採用/研究途中」を混同しない。
- REJECTは**その特徴量/補正のmodel入力だけ除外**。rawが他用途に使えるなら保持。
- archive優先、削除は最後。未採用/研究途中は容量整理対象にしない。

### REJECT確定
- Recent Form last5 current spec: blind VAL/OOS gate FAIL。収集継続、現仕様はmodel入力から除外。
- Wave residual / Wind-speed residual: 現residual設計のみREJECT。
- Global motor shrinkage: 一律補正のみREJECT。
- Naive prob*odds / high model-vs-market edge selector: 現selector設計のみREJECT。

### 未採用・研究継続
- Exhibition ST: NOT_YET_ROBUST、REJECT確定ではない。
- Exhibition Time: robust historical/OOS candidate、Forward待ち。
- racer×course×opponent affinity: unstable OOS / do not use yet。
- relative wind direction: coverage不足。
- V5 deferred items（l_count/exhibition/weather-water/odds selector等）は「未採用」であり削除対象ではない。
- Motor/Boat fixed OOSは改善側 → 保持。

## Current capacity facts
- candidate-v4 live disk **4.675166208GB / 5GB**。source direct rewrite禁止継続。
- archive live disk **2.33127936GB / 5GB**（Recent Form write後のWAL/physical overhead込み）。
- Recent Formは唯一の主要REJECT専用容量候補。
- Recent Form relation約 **933MB**、payload列約 **659MB**。
- Production主要entrypoint / frozen V5 coreはRecent Form直接依存なし。schema/column自体は残す。
- duplicate/same-key index=0。Exhibition ST約9.4MB、Wave/Wind派生約0.3MBで容量効果小。

## Low-resource compact preflight — PASS
Workflow: `.github/workflows/recent-form-compact-preflight-low-resource.yml`
- source candidate-v4 **read-only**
- Railway resource create=0 / archive write=0 / cutover=0 / AI/Agent=0
- fresh source DB **4,393,621,183 bytes**
- source `v2_race_entries` relation **933,183,488 bytes**
- compact relation（recent_form=NULL） **122,896,384 bytes**
- projected reclaim **810,287,104 bytes ≈ 810MB**
- fresh projected compact DB **3,583,334,079 bytes ≈ 3.583GB**
- 5GB logical headroom **約1.417GB**
- rows **425,772 = 425,772**
- non-Recent-Form binary SHA256 exact match
- transfer stream約 **156MB**
- parallel query workers=0 / maintenance_work_mem=64MB / AI=0
- full DB dumpを繰り返さない。今後もlow-resource方式を標準。

## Railway protection
- Production environmentに既存**3件 staged patch**あり。触らない/混ぜない。
- candidate-v3はsleeping・約4.553GB。explicit approvalなしにwipe/reuseしない。
- current-refresh direct restoreは過去のpartial --clean問題でSafety Hold。現candidateへ直接restoreしない。
- fresh disposable target方式を使う場合も、事前にarchive/parity/cost確認してから。

## Recent Form archive write + parity — PASS
- Target=`postgres-history-archive.public.v2_recent_form_archive`。
- source candidate-v4はread-onlyのまま。AI/Agent=0 / public proxy=0 / new Railway resource=0。
- rows **425,772 = 425,772**。
- identity=`(race_id,lane)`; key null=0; duplicate=0。
- deterministic payload_md5=`8580889f8cfb449e1656a943f30da350` exact match。
- source recent_form payload=659,381,918 bytes。
- archive relation=863,928,320 bytes; archive logical DB=1,118,164,671 bytes。
- archive live volume diskはwrite直後 **2.18402816GB / 5GB**。WAL/physical overheadを含むためlogicalより大きい。
- source live diskは **4.675084288GB / 5GB** でwrite前後ほぼ不変。
- temporary bridge=`candidate-v4-size-audit-temp` を既存resourceとして使用し、完了後idle化・bridge参照変数を空へ戻した。
- 既存Production staged patch 3件は未変更。
- source direct UPDATE/VACUUM FULL/rewriteは禁止継続。

## Compact target cost/headroom gate — PASS
- archive parityをidempotent read/verifyで再確認: **425,772 rows / MD5 exact / null=0 / duplicate=0**。追加insert=0。
- archive live disk **2.33127936GB / 5GB**。
- candidate-v4 live disk **4.675166208GB / 5GB**。
- fresh projected compact DB **3.583334079GB**、5GB内logical headroom **約1.416666GB**。
- 5GB volumeのfilesystem metadataを見ても1GB超の余裕を見込める。
- temporary target計画時間: **30〜60分枠**。完了後はparity確認して即削除。
- Railwayのactual-use課金前提で、30〜60分のtemporary DBは**期待追加cost <$0.10、safety budget <=$0.20**を目安。AI/Agent=0。
- candidate-v3は再利用しない。

## Next ONE task
**fresh disposable 5GB compact targetを1個だけ作成し、Recent Formを除いたcompact DBをrestoreしてparity確認する。**
必須条件:
- source candidate-v4はread-onlyのまま
- candidate-v3は触らない
- targetはtemporary / 5GB / low-resource
- restore後 DB size <5GB、全public table row-count parity、schema/index/constraint parity、non-Recent-Form exact parityを確認
- まだProduction cutover / source cleanupはしない
- verification完了後、cutover未実施ならtemporary targetの保持/削除を次の1作業として判断する。

## Chat-capacity対策
- 次チャットで読むのは **3点だけ**:
  1. `docs/HANDOFF_LATEST.md`
  2. そこが指すcurrent compact handoff全文
  3. `docs/NEXT_CHAT_START_HERE.md`
- 古いhandoff・PROJECT_HISTORY・長いworkflow全文は、次の1作業に必要な箇所だけ読む。
- GitHub/Railwayは巨大一覧を避け、exact path・限定検索・必要行だけ取得。
- 1ターン原則1～3 tool call。中間ログは最小。
- SHA/run/count/capacityは固定値扱いせず、行動直前に必要なものだけlive再取得。

`PROD_V4 / V5_RESEARCH_ONLY / FULL_BACKTEST_FROM_202507 / REJECT_NE_NOT_YET_ADOPTED / RECENT_FORM_COMPACT_PASS / LOW_RESOURCE / COST_LE_20 / ONE_TASK_ONLY`
