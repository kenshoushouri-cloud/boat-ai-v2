from pathlib import Path
import re

STAMP = "2026-08-25 17:54 JST"

HANDOFF_MARKER = "<!-- HANDOFF_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->"
HISTORY_MARKER = "<!-- HISTORY_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->"

HANDOFF_APPEND = r'''

---

<!-- HANDOFF_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->
## 追記: 2026-08-25 17:54 JST — Exhibition ST fixed OOS / Forward Shadow自動収集

この節は PR #235〜#237 完了後の重要マイルストーン。**Production v24 / FINAL / LINE / BUY-WATCH-SKIP / Railway Variables・service scheduleは変更していない。**

### main基準点
この追記直前の main:
- `656f7d25d21b2a16b4cd33074913513d8760f971`
- PR #237 `Ops: schedule exhibition ST Forward collection` マージ後。

再開時は必ずcurrent mainを再取得する。

### PR #235 — Exhibition STをcurrent v24へ固定追加したfuture OOS
BASEはcurrent Production PRE v24相当:
- motor2 = 33.0固定
- boat2 = 34.0固定
- PROB_TEMP = 2.20

Exhibition ST側はPR #122の最初のtrain cutoffで固定済み定義を再利用:
- `z(-start_timing_rank)`
- ticket position weight = 1.0 / 0.6 / 0.3
- **beta = -0.02固定**
- coefficient searchなし

future OOS 2026-01-01..2026-08-22 / **34,697R**:
- trifecta Brier delta **-0.00001292**
- actual-ticket LogLoss delta **-0.00041811**
- actual-ticket rank delta **-0.0142**
- LogLoss改善: fixed window **4/4**、month **8/8**

**判断:** historical future OOSでは小さいが一貫したincremental value。race-band差を見て後付けfilterは作らず、同じ固定定義でForwardへ進む。

### PR #236 — 独立Exhibition ST Forward Shadow
新規専用テーブル:
- `v2_exhibition_st_forward_shadow`

固定Forward定義:
- beta **-0.02**
- deadline **8〜15分前**のofficial beforeinfoだけを使用
- lexicographic 120-ticket order固定
- BASE/ST 120確率を凍結
- collectorは**結果・オッズを読まない**
- `snapshot_at < deadline_at`
- `ON CONFLICT (race_id) DO NOTHING` = **first snapshot wins**
- Production consumer / LINEなし

最初のconfirmed collectionはofficial Forward **3R**、invalid/timing/source error 0、結果はpendingで開始。

Issue #42:
- write: `/railway exhibition-st-forward-collect CONFIRM`
- read-only: `/railway exhibition-st-forward-health`

### PR #237 — 5分間隔の自動Forward収集
GitHub Actions schedule:
- `*/5 0-12,23 * * *` UTC
- **08:00〜21:59 JST、5分間隔**

collector自身の8〜15分前windowは変更しない。GitHub Actions側の収集頻度だけを上げ、7分幅windowのdeterministic missを避ける。

初回CIではworkflow自己検査の `send_line` 禁止文字列がassert文自身へ一致するself-matchで専用CIだけ失敗。機能側ではなくCI検査の不具合だったため、禁止語を文字列連結へ変更。修正後:
- Critical Python syntax: PASS
- Critical mojibake guard: PASS
- Production shadow isolation: PASS
- Exhibition ST Forward scheduled collector: PASS
- V21 parser sanity: PASS

その後PR #237をready → squash merge。

### 2026-08-25 17:44 JST runtime再確認
Issue #42 read-only:
- races **156 / deadline_ready 156**
- entries **936 / full6 156R**
- odds races **156**
- upcoming **19R / odds complete 19R**
- night window **65R / odds complete 65R**
- read-only health PASS

PostgreSQL read-only size:
- **3225 MB**（Hobby 5GB reference）

Railway inventory:
- **14 services**
- connection healthy
- Railway Variables/settings/deploy configurationは今回変更していない。

### Opponent Pressure / GUARD05の現在地
Opponent Pressure head-onlyは固定のまま:
- shadow 624R / evaluated 468R / pending 156R
- Brier delta **-0.00006135**
- LogLoss delta **-0.00183905**
- rank delta **+0.284**
- **KEEP_FORWARD_RESEARCH / Production BLOCK**
- R05-08・8/24を見た後の除外filterは作らない。

GUARD05:
- frozen rows **12**
- evaluated 0 / pending 12 / affected evaluated 0
- **BLOCK_MANUAL_REVIEW_ONLY**
- PRIOR_DAY / <=5保護を固定したままaffected Forwardを待つ。

### 現在の通常予想Aの研究優先
1. Opponent Pressure head-only fixed Forwardを継続。
2. GUARD05 actual motor2 fixed Forwardを継続。
3. Exhibition ST beta=-0.02 fixed Forwardを自動蓄積。
4. 3系統とも十分な新規Forward証拠なしにProductionへ入れない。
5. PR #169は唯一のopen PRとしてDraft hold継続。
'''

HISTORY_APPEND = r'''

---

<!-- HISTORY_MILESTONE_20260825_EXHIBITION_ST_FORWARD -->
## 2026-08-25 17:54 JST — Exhibition STをcurrent v24上の固定Forward研究へ昇格

### 仮説
展示ST順位が古いBao market baselineだけでなく、current v24の三連単確率へincremental valueを持つかを、過去に確定した係数を動かさず検証する。

### PR #235: fixed future OOS
BASE=current Production PRE v24相当（motor2=33、boat2=34、PROB_TEMP=2.20）。
ST scoreはPR #122の最初のtraining cutoffで決まった:
- z(-start_timing_rank)
- 1着/2着/3着 weight 1.0/0.6/0.3
- beta **-0.02固定**

2026-01-01..08-22 / 34,697R:
- Brier **-0.00001292**
- LogLoss **-0.00041811**
- rank **-0.0142**
- LogLoss改善 4/4 fixed windows、8/8 months

**Decision:** `PROMISING_FIXED_OOS_REQUIRE_FORWARD`。効果量は小さいが期間一貫性がある。race-band/venue差を見た後のfilterや係数調整はしない。

### PR #236: isolated frozen Forward Shadow
専用 `v2_exhibition_st_forward_shadow` を追加。

Forward integrity:
- official beforeinfoのみ
- deadline 8〜15分前
- results/odds非参照
- beta=-0.02固定
- BASE/ST 120確率を保存
- first snapshot wins
- Production/LINE consumerなし

初回confirmed collectionは3R、invalid/timing/source error 0、all pending。

**Decision:** `KEEP_ISOLATED_FORWARD_SHADOW`。

### PR #237: scheduled collection
8〜15分前の7分幅windowを手動実行だけで取りこぼさないため、GitHub Actionsを08:00〜21:59 JSTに5分間隔で追加。

初回専用CI failureはworkflow内の禁止語assertが自分自身へmatchする検査バグ。Production/collector不具合ではない。self-matchを除去後、主要5 CIが全PASSしsquash merge。

**Decision:** `ADOPT_FORWARD_COLLECTION_ONLY`。

### 同時点の既存研究gate
Opponent Pressure head-only 468RはBrier/LogLoss改善、rank悪化でmixed。
- `KEEP_FORWARD_RESEARCH`
- Production BLOCK
- R05-08/date filterを後付けしない。

GUARD05は12 frozen rowsすべてpending、affected evaluated 0。
- `KEEP_SHADOW`
- manual review only
- PRIOR_DAY / threshold 5固定。

### Production impact
- Production v24 / FINAL: **変更なし**
- LINE / BUY / WATCH / SKIP: **変更なし**
- Railway Variables/settings/service schedules: **変更なし**
- N02/N01/Bao: **変更なし**
- PR #169: **Draft hold継続**

次のgateは、Opponent Pressure / GUARD05 / Exhibition STの各fixed Forwardが新規結果で再現性を示すこと。十分な証拠後も自動昇格せずmanual reviewする。
'''


def update(path_str: str, marker: str, addition: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^更新日時:.*$", f"更新日時: {STAMP}", text, count=1, flags=re.MULTILINE)
    if marker not in text:
        text = text.rstrip() + addition + "\n"
    path.write_text(text, encoding="utf-8")


update("docs/PROJECT_HANDOFF.md", HANDOFF_MARKER, HANDOFF_APPEND)
update("docs/PROJECT_HISTORY.md", HISTORY_MARKER, HISTORY_APPEND)
print("PROJECT_DOCS_MILESTONE_UPDATE=PASS")
