from pathlib import Path
import re

STAMP = "2026-08-25 19:01 JST"
TAG = "RACER_COURSE_TOP3_FORWARD_MILESTONE_20260825"

handoff = Path("docs/PROJECT_HANDOFF.md")
history = Path("docs/PROJECT_HISTORY.md")

h = handoff.read_text(encoding="utf-8")
h = re.sub(r"更新日時: .*? JST", f"更新日時: {STAMP}", h, count=1)
section = f'''\n<!-- {TAG} -->\n## 0A. 2026-08-25 選手×コース3連対率 Forward 追加\n\n- PR #241: `v2_racer_course_stats_snapshots` のForward readinessを結果非参照で監査。42日、4,005R full6はあるが timing-safe 97.54%・日別欠損ありのため、無条件のincremental OOSは `INSUFFICIENT_FOR_INCREMENTAL_OOS`。同日snapshotはupsertで後から更新され得るため、可変sourceを結果評価へ直接使わない。\n- PR #242: source integrityを事前固定し、6艇すべてが当日08:15 JSTまで・deadline前のcomplete-caseだけで `course top3 rate` をcurrent v24へ追加するtrain-only expanding OOSを実施。係数grid `0/0.05/0.10/0.20/0.30/0.50`、3つの非重複OOSすべてでtrain選択係数=0.50。全OOS 2,299Rで Brier delta `-0.00608767`、LogLoss delta `-0.21143915`、ticket rank delta `-5.0170`、Top10 `31.62% -> 38.76%`。3/3 splitでBrier/LogLoss/rank改善。0.50はgrid上端のため同じOOSで係数を拡張探索せず、**0.50固定**。\n- PR #243: `v2_racer_course_top3_forward_shadow` を追加。BASE=current Production PRE v24（motor2/boat2 defaults 33/34, PROB_TEMP=2.20）、COURSE=`BASE raw strength + 0.50*z(official course top3 rate)`、lane=course early-PRE proxy。exact-date official source、6艇必須、source `created_at <=08:15 JST`・deadline前、write時3分以上lead、1 race 1 row、`ON CONFLICT (race_id) DO NOTHING` first-write-wins。\n- 自動収集: GitHub Actions 06:45 JST開始、2分間隔・2時間loop。Railway `cron-racer-course-stats` 07:15 JSTの完了遅延を吸収する。Railway service schedule自体は変更していない。\n- 初回confirmed Forward write（2026-08-25 19:00 JST前後）: payload 9R / write 9R / invalid 0 / pending 9。初回healthは evaluated 0、promotion=`BLOCK_MANUAL_REVIEW_ONLY`。\n- 決定: `KEEP_FIXED_FORWARD_SHADOW_RESEARCH_ONLY`。Production v24/FINAL/LINE/BUY-WATCH-SKIPへは未昇格。係数0.50、08:15 cutoff、lane=course proxyをForward中に変更しない。\n\n'''
if TAG not in h:
    marker = "## 1. 新しいチャットで最初に渡す指示"
    if marker not in h:
        raise SystemExit("handoff insertion marker not found")
    h = h.replace(marker, section + marker, 1)
handoff.write_text(h, encoding="utf-8")

x = history.read_text(encoding="utf-8")
x = re.sub(r"更新日時: .*? JST", f"更新日時: {STAMP}", x, count=1)
history_section = f'''\n<!-- {TAG} -->\n## 0A. 2026-08-25 — Racer course top3: fixed OOS support → isolated Forward\n\n- #241 decision: `NOT_READY_FOR_UNFILTERED_OOS`; mutable exact-date snapshot timestamps and uneven daily coverage prevent treating all stored rows as frozen morning evidence.\n- #242 pre-registered complete-case OOS decision: `SUPPORTS_FIXED_FORWARD_SHADOW_RESEARCH_ONLY`. Three non-overlapping Aug windows all improved Brier/LogLoss/rank; aggregate n=2,299, Brier `-0.00608767`, LogLoss `-0.21143915`, rank `-5.0170`. Train-only selected coefficient was 0.50 in all three splits.\n- Because 0.50 was the pre-registered grid ceiling, **do not** search larger coefficients on the same OOS. Freeze 0.50 for Forward.\n- #243 decision: `KEEP_ISOLATED_FORWARD_SHADOW`. Dedicated first-write-wins table freezes BASE/COURSE 120-probability vectors plus all six source timestamps before outcomes. Automatic GitHub collection starts 06:45 JST and polls every 2 minutes for 2 hours; no Railway schedule/settings change.\n- First live Forward capture: 9R written, invalid 0, pending 9. Promotion remains manual-review-only / Production BLOCK.\n- No Production v24/FINAL/LINE/BUY-WATCH-SKIP, N02/N01, Bao, scoring-weight, Railway Variable/service schedule, or PR #169 change.\n\n'''
if TAG not in x:
    marker = "## 0. 長期方針"
    if marker not in x:
        raise SystemExit("history insertion marker not found")
    x = x.replace(marker, history_section + marker, 1)
history.write_text(x, encoding="utf-8")

print("RACER_COURSE_DOCS_UPDATE=PASS")