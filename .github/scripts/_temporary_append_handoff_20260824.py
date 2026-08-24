# -*- coding: utf-8 -*-
from pathlib import Path
import re

STAMP = "2026-08-24 21:10 JST"
MARKER = "<!-- HANDOFF_MILESTONE_20260824_OPP_MOTOR -->"

handoff_path = Path("docs/PROJECT_HANDOFF.md")
history_path = Path("docs/PROJECT_HISTORY.md")

handoff = handoff_path.read_text(encoding="utf-8")
handoff = re.sub(r"更新日時: .*", f"更新日時: {STAMP}", handoff, count=1)
if MARKER not in handoff:
    handoff += r'''

---

<!-- HANDOFF_MILESTONE_20260824_OPP_MOTOR -->
## 追記: 2026-08-24 21:10 JST — Opponent Pressure実結果 / モーター交換・成熟度

この節は PR #191〜#194 完了後の重要マイルストーン。Productionロジックは変更していない。

### main基準点
この追記作成直前の main:
- `a34e48d3fbc809ab173925e18eb774cae0e639e6`
- PR #194 マージ後。

再開時は必ず current main を再取得する。

### Opponent Pressure — 実結果Forward
PR #191で既存 `v2_opponent_pressure_shadow_v2` と確定着順を比較するread-only Forward evaluatorを追加。
初回は旧 `v2_result_entries` を読んだため0評価となった。現在のnightlyは `v2_results` の `first_lane..sixth_lane` が正なので、PR #192で評価側のみ修正した。

2026-08-22〜08-24のfrozen Shadow:
- Shadow rows: 468
- `v2_results` official rows: 324
- evaluated: **292**
- pending: 176
- malformed: 0
- integrity skip: 0

Overall 292R:
- win Brier: `0.10984498 -> 0.10869775` / delta **-0.00114723**
- top3 Brier: `0.21241847 -> 0.21071051` / delta **-0.00170796**
- winner logloss: `1.34694537 -> 1.33417941` / delta **-0.01276596**
- winner rank: `2.0582 -> 2.0514` / delta **-0.0068**

日別でも8/22・8/23ともBrier/loglossは改善。

**判断:**
- historical OOSと実結果Forwardの方向が一致し、通常予想系の補助特徴量として有望。
- ただし実結果はまだ292R・2日分中心なので **Productionへ入れない**。
- daily Shadowを継続し、日数・場・レース条件をまたいだ再現性を確認してから次段階へ。

### モーター交換時期 — Source policy
モーター世代開始日はDB first-seenから推定しない。

優先順位:
1. **BOAT RACE / 各場公式** = 一次情報
2. **艇国DB** = 補助・クロスチェック
3. Railway DB first-seen = 診断用途のみ。公式開始日として使わない。

2026-08-24に公式ページで固定確認したcurrent-generation subset:
- venue 03 江戸川: **2026-05-11**
- venue 05 多摩川: **2026-04-18**
- venue 12 住之江: **2026-03-23**
- venue 14 鳴門: **2026-04-11**
- venue 23 唐津: **2025-09-05**

### PR #193 — 世代開始からの日数別モーター実測値
5場、official start以降、motor data complete **5,095R**。
BASE=fixed motor2 33.0、MOTOR=出走表の実測motor2。v24式/係数/PROB_TEMPは固定、boat2=34.0固定。

Overall:
- logloss delta **-0.00324000**
- Brier delta **-0.00007750**
- winner rank delta **-0.2075**

世代開始後の日数別 logloss delta:
- 0–14日: n582 / **-0.00579696**
- 15–30日: n522 / **-0.00440829**
- 31–60日: n723 / **-0.00234561**
- 61–120日: n1510 / **-0.00303145**
- 121日+: n1758 / **-0.00259356**

若い0–30日もaggregateでは悪化しなかった。一方、venue×ageには一部悪化区間あり。

**判断:** 「交換直後だから実測motor2を一律に弱める」という単純補正は採用しない。

### PR #194 — 個別モーターの事前出走回数別
公式世代開始日から、各motor_noの**現在レースより前の出走表登場回数だけ**を時系列カウント。同一レースをカウントしてから評価しないため、same-race leakageなし。
レースは6艇中もっとも事前登場回数が少ないmotorで分類。

Coverage:
- result races: 5,114
- evaluated / motor complete: **5,095**
- prior <10 sample: 815
- prior 20+ sample: 3,707

最小prior count別 logloss delta:
- 0–4: n438 / **-0.00240089** / rank delta `+0.0776`
- 5–9: n377 / **-0.00719944** / rank delta `-0.6286`
- 10–19: n573 / **-0.00454600** / rank delta `-0.3700`
- 20–39: n1081 / **-0.00439443** / rank delta `-0.4218`
- 40+: n2626 / **-0.00205133** / rank delta `-0.0708`

全固定binでloglossは改善したが、0–4ではwinner rankが僅かに悪化し、場別の低母数binには悪化例もある。

**判断:**
- motor実測値そのものの有用性は強まった。
- しかし「prior N未満なら除外/○%減」のような閾値を、この同じ結果から後付けで作らない。
- 交換時期・公式世代開始・個体母数をメタデータとして保持し、Forwardで場別安定性を確認する。
- Production v24の固定33.0は、まだ変更しない。

### 次の優先順位（この追記時点）
1. Opponent Pressure daily Shadowを継続し、実結果Forwardを日数・場をまたいで再評価。
2. motor実測値は公式世代開始日/個体prior countを伴う独立Shadowまたは固定read-only比較でForward確認する。後付け閾値調整はしない。
3. 公式motor generation startの場カバレッジを増やす。艇国DBは補助照合に使う。
4. Baoは既存gateを維持。馬王型は通常予想のプラスアルファ。
5. PR #169はDraft維持。Production/LINE/threshold/Railway設定は未変更。
'''
    handoff_path.write_text(handoff, encoding="utf-8")

history = history_path.read_text(encoding="utf-8")
if MARKER not in history:
    history += r'''

---

<!-- HANDOFF_MILESTONE_20260824_OPP_MOTOR -->
## 2026-08-24 20:49〜21:10 JST — 相手構成Forwardとモーター交換成熟度を再検証

### Opponent Pressure: historical OOSから実結果Forwardへ
過去チャットで検討していた「自選手のコース × 相手コース × 相手級別」の相性を、既存Opponent Pressure Shadowで実結果評価。

- PR #191: realized Forward evaluator追加。
- 初回0評価から、現行nightly結果の正本が `v2_results(first_lane..sixth_lane)` であることを再確認。
- PR #192: evaluatorの結果結合先だけを現行構造へ修正。
- 292Rでwin Brier / top3 Brier / winner logloss / winner rankのOverall 4指標がすべて改善。

**Decision:** `PROMISING_FORWARD_RESEARCH_ONLY`。通常予想系の有力補助候補だが、2日中心の292RではProduction採用しない。Forward継続。

### モーター交換時期の扱いを明示
ユーザー指摘「モーターは交換時期に注意」を受け、DB first-seenではなく公式使用開始日を使う方針を再確認。

2026-08-24公式確認subset:
- 江戸川 2026-05-11
- 多摩川 2026-04-18
- 住之江 2026-03-23
- 鳴門 2026-04-11
- 唐津 2025-09-05

Source policyは **公式一次 / 艇国DB二次照合 / DB first-seen診断のみ**。

### PR #193: 世代開始後の日数別
5,095Rでactual motor2の効果を固定比較。
0–14日から121日+まで全age binのOverall loglossが改善。

**Decision:** 「交換直後を一律に弱める」補正を却下。venue×ageには悪化区間があるため、より直接的な個体母数へ進む。

### PR #194: 個体の事前出走回数別
6艇のうち最もprior appearanceが少ないmotorを基準に固定bin化。current raceを加算する前に評価し、same-race leakageなし。

- P00–04 n438: logloss -0.00240089、rank +0.0776
- P05–09 n377: -0.00719944
- P10–19 n573: -0.00454600
- P20–39 n1081: -0.00439443
- P40+ n2626: -0.00205133

**Decision:** 全binでlogloss改善のため、低母数を理由にactual motor2を一律除外しない。一方、場別には低母数で悪化例があるため、このデータから後付けcutoff/shrinkage係数を作らない。Forwardで場別再現性を確認する。

### Production safety
PR #191〜#194はすべてread-only audit/評価。Production予想、LINE、Railway Variables/settings、v24/N02 threshold、Bao係数/promotion、PR #169は変更していない。
'''
    history_path.write_text(history, encoding="utf-8")

print("HANDOFF_MILESTONE_UPDATE=PASS")
