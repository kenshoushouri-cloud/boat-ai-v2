from pathlib import Path

STAMP = "更新日時: 2026-08-25 12:45 JST"
HANDOFF_MARKER = "<!-- HANDOFF_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->"
HISTORY_MARKER = "<!-- HISTORY_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->"

handoff_append = r'''

---

<!-- HANDOFF_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->
## 追記: 2026-08-25 12:45 JST — Opponent Pressure v24統合Forward / Motor V12直近反転診断

この節は PR #231〜#233 完了後の重要マイルストーン。**Production v24 / LINE / BUY-WATCH-SKIP / Railway設定は変更していない。**

### main基準点
この追記直前の main:
- `07e52455ac210128f0f2dd62355694b75fe76410`
- PR #233 `Audit: decompose recent motor holdout by venue and date` マージ後。

再開時は必ずcurrent mainを再取得する。

### Opponent Pressure — 現在のForward状態
既存 `v2_opponent_pressure_shadow_v2` は2026-08-22から日次収集継続。
8/25昼時点:
- Shadow: **624R**
- top3が確定した三連単評価可能: **468R**
- 6艇全着順integrityを要求する基本realized evaluator: **428R**

基本realized 428R Overall:
- win Brier delta **-0.00092528**
- top3 Brier delta **-0.00195974**
- winner LogLoss delta **-0.01096028**
- winner rank delta **-0.0023**

全体では引き続き有望。ただしvenue別では:
- win Brier改善 11/17場
- top3 Brier改善 15/17場
- LogLoss改善 10/17場
- rank改善 6/17場

R帯別ではR01-04 / R09-12は概ね良好、R05-08はwinner rankが僅かに悪化。

### v24三連単へ統合する固定head-only方式
既存研究を再確認し、単純な全lane weight再配分ではなく、PR #202/#203の **head-only mapping** が現在の本命研究方式。

固定定義:
- Opponent Pressureは**1着確率だけ**へ反映
- coefficient = **1.0固定**
- 2着/3着のconditionalはcurrent v24のまま
- threshold/date/venue選択なし

PR #203 historical OOSでは3固定splitすべてOverallでBrier / LogLoss / actual-ticket rank改善。
代表:
- split 2026-03-31: LL **-0.01036749** / rank **-0.352**
- split 2026-04-30: LL **-0.00969562** / rank **-0.265**
- split 2026-05-31: LL **-0.01007095** / rank **-0.259**

一方、realized Forward 468R:
- 120-class Brier delta **-0.00006135**
- actual-ticket LogLoss delta **-0.00183905**
- actual-ticket rank delta **+0.284**（悪化）

R05-08 / 156R:
- Brier **+0.00020560**
- LogLoss **+0.00859710**
- rank **+0.679**

日別では8/24が弱く、特に8/24 R05-08が悪化。

**判断:**
- historical OOSは強いが、3日中心のForwardはmixed。
- **KEEP_FORWARD_RESEARCH / Production BLOCK**。
- 8/24やR05-08を見た後に除外filterを作らない。
- 同じhead-only coefficient=1.0を固定したままForwardを増やす。

Issue #42 read-only commands:
- `/railway opponent-pressure-forward-stratified`
- `/railway opponent-pressure-v24-head-forward`
- `/railway opponent-pressure-v24-head-daily`

### fixed log-odds transportは不支持
PR #207の固定log-odds transportを再確認。
468R Overall、v24比:
- trifecta Brier **+0.00006538**
- LogLoss **+0.00093481**
- rank **+0.577**

R09-12だけは改善したがOverallは3指標悪化。

**判断:** `NO_FIXED_LOG_ODDS_FORWARD_SUPPORT_YET`。log-odds方式を追わず、head-only固定案のForwardを継続する。

### Motor actual rate — V12直近反転の診断
PR #220 independent holdout 2026-08-16..08-24 / 240RではALL_ACTUAL motor2がOverall改善:
- LL **-0.00354788**
- Brier **-0.00009918**
- rank **-0.2583**

ただし住之江 V12 / 36Rだけ悪化:
- LL **+0.00453061**
- Brier **+0.00006796**
- rank **+0.3333**

PR #219のpre-holdout V12 mature P21+は3期間すべてLogLoss改善:
- 2026-05-11..06-15: **-0.010378**
- 06-16..07-15: **-0.000588**
- 07-16..08-15: **-0.000926**

PR #233で全5場をvenue×date分解。V12の36Rは1節3日だけ:
- 8/16 n12: LL **-0.00109457**
- 8/17 n12: LL **+0.00504850**
- 8/18 n12: LL **+0.00963791**

全20 venue×date cell:
- LL改善 14/20
- Brier改善 13/20
- rank改善 12/20

**判断:**
- V12は長期的に不支持ではなく、直近1節後半2日の小標本反転。
- **V12を後付け除外しない。**
- actual motor2は有望のまま。ただしProduction一律置換はまだしない。
- GUARD05（PRIOR_DAY / <=5保護）の独立Forwardを固定継続する。

### 現在の通常予想Aの優先状態
1. Opponent Pressure head-only: historical OOS strong / realized Forward mixed → 固定Forward継続。
2. actual motor2: independent holdout Overall positive / venue・meet変動あり → GUARD05 Forward継続。
3. どちらもProductionへまだ入れない。
4. PR #169はDraft hold継続。
'''

history_append = r'''

---

<!-- HISTORY_MILESTONE_20260825_OPP_HEAD_MOTOR_V12 -->
## 2026-08-25 12:45 JST — Opponent Pressure統合方式とMotor V12反転の判断

### Opponent Pressure: head-only mappingを研究本線として維持
既存PRを再監査し、v24三連単への統合はPR #202/#203の固定head-only mappingが最も根拠が強いことを再確認。

historical OOS 3splitではOverall Brier / LogLoss / ticket rankが全て改善したが、realized Forward 468Rでは:
- Brier **-0.00006135**
- LogLoss **-0.00183905**
- rank **+0.284**

R05-08と8/24に弱さがある。

**Decision:** `KEEP_FORWARD_RESEARCH`。日付/R帯/場を後付け除外しない。ProductionはBLOCK。

PR #231/#232で既存固定監査をIssue #42から再実行できるread-only bridgeとして整備した。

### PR #207 fixed log-odds transportを再評価
468R Overallでv24比:
- Brier **+0.00006538**
- LogLoss **+0.00093481**
- rank **+0.577**

**Decision:** `HOLD / NO_FORWARD_SUPPORT`。R09-12だけの良さからsubgroup採用しない。

### Motor V12 recent reversal
PR #220 holdoutでは5場Overall actual motor2が改善した一方、V12 / 36Rが3指標悪化。

PR #219を再確認するとV12 mature P21+はpre-holdout 3期間すべてLogLoss改善。
PR #233でvenue×dateを全セル固定表示した結果、V12 36Rは8/16-18の1節だけで:
- 8/16: 改善
- 8/17: 悪化
- 8/18: 悪化

**Decision:** V12を除外しない。直近小標本を見てvenue filterを作らない。actual motor2 / GUARD05はForward継続し、ProductionはBLOCK。

### Production impact
- none
- v24 / LINE / BUY-WATCH-SKIP unchanged
- Railway Variables/settings/schedules unchanged
- N02/Bao unchanged
- PR #169 Draft hold unchanged
'''


def update(path: str, marker: str, append_text: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines[:8]):
        if line.startswith("更新日時:"):
            lines[i] = STAMP
            text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            break
    if marker not in text:
        text = text.rstrip() + append_text + "\n"
    p.write_text(text, encoding="utf-8")


update("docs/PROJECT_HANDOFF.md", HANDOFF_MARKER, handoff_append)
update("docs/PROJECT_HISTORY.md", HISTORY_MARKER, history_append)
print("DOC_MILESTONE_UPDATE=PASS")
