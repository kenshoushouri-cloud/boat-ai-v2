from pathlib import Path
import re

STAMP = "2026-08-25 18:28 JST"
H_MARK = "<!-- HANDOFF_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->"
R_MARK = "<!-- HISTORY_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->"

H_APPEND = r'''

---

<!-- HANDOFF_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->
## 追記: 2026-08-25 18:28 JST — Exhibition ST Forward scheduler遅延対策

### main基準点
この追記直前の main:
- `71166721f6dc7f5037eea37a1648c676274f6407`
- PR #239 `Ops: make exhibition ST Forward schedule delay-resilient` マージ後。

再開時は必ずcurrent mainを再取得する。

### 観測した問題
PR #237 merge後の最初のscheduled runは **18:21 JST** に開始。
workflow自体は成功したが:
- target races: 156
- 8〜15分window内 payloads: **0**
- outside_window: **156**
- write rows: **0**

manual confirmed collectorも同時刻帯ではpayload 0だった。
collector/parserの失敗ではなく、GitHub scheduled eventが約20分遅れて起動したため、7分幅のfrozen capture windowを5分cronだけでは保証できないことを確認した。

### PR #239 — delay-resilient loop
既存Bao auto captureの実績ある設計をExhibition STへ限定適用。

変更:
- trigger開始を **07:00 JST**へ前倒し
- cron: `*/5 22,23,0-12 * * *`
- scheduled job内で **2分間隔 / 90分** collection loop
- timeout 100分
-既存concurrency groupを維持、`cancel-in-progress: false`

固定のまま変更していないもの:
- beta = **-0.02**
- capture window = **8〜15分前**
- official beforeinfo only
- BASE/ST 120 probability definition
- `ON CONFLICT (race_id) DO NOTHING`
- first snapshot wins
- results/odds非参照
- Production/LINE consumerなし

PR #239 CI:
- Exhibition ST Forward scheduled collector: PASS
- Production shadow isolation: PASS
- Critical Python syntax: PASS
- Critical mojibake guard: PASS
- V21 parser sanity: PASS

### 現在の判断
- **ADOPT_DELAY_RESILIENT_FORWARD_COLLECTION**
- Production promotionは引き続きBLOCK。
- scheduler遅延を特徴量やwindow変更で埋めない。
- frozen 8〜15分window / beta=-0.02を維持したまま、新規Forward evidenceの欠損だけを減らす。
- Railway Variables / service schedules / Production v24 / LINE / BUY-WATCH-SKIPは変更していない。
- PR #169はDraft hold継続。
'''

R_APPEND = r'''

---

<!-- HISTORY_MILESTONE_20260825_EXH_ST_DELAY_RESILIENCE -->
## 2026-08-25 18:28 JST — Exhibition ST ForwardのGitHub scheduler遅延を収集loopで吸収

### 観測
PR #237の5分cronはmainへ正常mergeしたが、最初のschedule eventは18:21 JSTまで遅延した。
jobは成功したものの156Rすべて8〜15分window外でwrite 0。

**Decision:** 5分cron頻度だけでは7分幅Forward windowのchronological evidenceを保証できない。

### PR #239
既存Baoで使っているdelay-resilient internal loopを、Exhibition ST collectorだけへ適用。
- 07:00 JSTからtrigger可能
- 2分loop
- 90分継続
- concurrency serial hand-off

collector自体のbeta=-0.02、8〜15分window、official-beforeinfo-only、first-write-winsは不変。

**Decision:** `ADOPT_DELAY_RESILIENT_FORWARD_COLLECTION`。
これはモデル調整ではなくForward evidence acquisitionの欠損対策。windowを広げたりpost-hoc dataを許可したりしない。

### Production impact
- Production v24 / FINAL: none
- LINE / BUY / WATCH / SKIP: none
- Railway Variables/settings/service schedules: none
- coefficient / threshold / N02 / N01 / Bao: none
- PR #169: Draft hold
'''


def update(path_str, marker, addition):
    p = Path(path_str)
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"^更新日時:.*$", f"更新日時: {STAMP}", text, count=1, flags=re.MULTILINE)
    if marker not in text:
        text = text.rstrip() + addition + "\n"
    p.write_text(text, encoding="utf-8")

update("docs/PROJECT_HANDOFF.md", H_MARK, H_APPEND)
update("docs/PROJECT_HISTORY.md", R_MARK, R_APPEND)
print("PROJECT_DOCS_DELAY_MILESTONE_UPDATE=PASS")
