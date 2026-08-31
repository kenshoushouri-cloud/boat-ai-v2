# boat-ai-v2 — ChatGPT New Project Migration Handoff

更新日時: 2026-08-31 JST

この文書は、ChatGPT内の「競艇AI開発プロジェクト No.1〜No.5」およびその後の継続チャットで蓄積した開発経過を、新しいChatGPTプロジェクトへ安全に引き継ぐための**起動用マスター文書**である。

この文書だけを過去チャット全文の代替とみなさず、再開時は必ず次も読む。

- `docs/PROJECT_HANDOFF.md` — 現在地・安全方針
- `docs/PROJECT_HISTORY.md` — 判断・採用/却下理由の時系列
- `docs/DEVELOPMENT_STATUS.md` — 詳細な技術検証ログ
- GitHub Issue #42 — Railway Bridge control / audit log

**重要:** この文書に書かれたSHA、件数、healthは「2026-08-31時点の引き継ぎ基準」であり、再開時のcurrent値だと仮定しない。

---

## 1. 新しいChatGPTプロジェクトで最初に実行する指示

新規プロジェクトの最初のチャットでは、次の指示を使う。

> GitHub `kenshoushouri-cloud/boat-ai-v2` の開発を、過去の「競艇AI開発プロジェクト No.1〜No.5」とその後の継続作業から引き継いでください。最初に `docs/CHATGPT_PROJECT_MIGRATION.md`、`docs/PROJECT_HANDOFF.md`、`docs/PROJECT_HISTORY.md` を読み、current main、open PR、Issue #42、Railway read-only healthを最新状態で確認してください。GitHub mainをコードのSource of Truth、Railway PostgreSQLを本番データのSource of Truthとして扱ってください。古いチャット内のSHA・件数・Railway service構成を現在値として使わないでください。mainへ直接書かず、branch → Draft PR → CI → review → ready → mergeを守ってください。Production変更前には理由・対象ファイル・影響範囲・Shadow/Production区分を確認し、OOS/walk-forward/Forward/live証拠なしに研究機能をProductionへ昇格しないでください。

---

## 2. Source of Truth

### GitHub
- Repository: `kenshoushouri-cloud/boat-ai-v2`
- code Source of Truth: **GitHub main**
- main直書き禁止
- 原則: **branch → Draft PR → CI → review → ready → merge**

### Railway
- Project: `boat-v2-postgres`
- data Source of Truth: **Railway PostgreSQL**
- Supabase: 削除済み。今後使用しない。
- secret / token / passwordはIssue、文書、チャットへ表示しない。

### 2026-08-31 Postgres復旧後の重要な現在構成
過去チャットでは `postgres` がDB実体だったが、2026-08-31 Stage 2復旧後は構成が変わった。

- **DB実体:** `postgres-recovery`
  - PostgreSQL 18.6
  - preserved `postgres-volume` を所有
  - deleted deploymentのpinned image digestで稼働
- **compatibility namespace:** `postgres`
  - Volumeを持たない
  - 旧 `${{postgres.DATABASE_URL}}` 互換用
- consumer 13 servicesの `DATABASE_URL` は `postgres-recovery.DATABASE_URL` Railway Referenceへrelink済み
- この二層構成を明確なmigration planなしにrename/delete/統合しない。

この構成は、No.1〜No.5時代の「Postgres service = postgres」という古い前提より優先する。

---

## 3. 絶対に維持する安全方針

1. Production変更前に理由、変更ファイル、影響、Shadow/Productionを確認する。
2. DRY_RUN / TEST_MODEを優先し、検証中にLINE送信や購入相当のProduction挙動を起こさない。
3. Shadow研究は、OOS / walk-forward / Forward / live証拠を確認するまでProductionへ昇格しない。
4. 同じOOSを見ながら条件を後付け調整し、良く見えるまで最適化しない。
5. Railway Variables / schedules / DB topologyは、目的と影響を明確にしてから変更する。
6. Volume / backupをwipe/deleteしない。
7. `postgres-recovery` / compatibility `postgres` の復旧後二層構成を不用意に変更しない。
8. PR #169は明確なprediction/learning valueが出るまでDraft hold。
9. secret値はGitHub Issue / docs / ChatGPTへ出さない。
10. 長い作業は一度に詰め込まず、タイムアウトを避けるため安全な単位で順番に進める。

---

## 4. No.1〜No.5で積み上げた大きな開発経過

### Phase A — SupabaseからRailway PostgreSQLへ
元構成はSupabaseだったが、容量・運用上の問題からRailway PostgreSQLへ移行した。

確定事項:
- Supabaseは削除済み。
- 本番データはRailway PostgreSQLを正とする。
- 正しい出走表テーブルは **`v2_race_entries`**。 `v2_entries` は誤り。
- 主要テーブル:
  - `v2_races`
  - `v2_race_entries`
  - `v2_results`
  - `v2_odds_trifecta`
  - `v2_exhibition`
  - `v2_race_weather`
  - `v2_feature_snapshots`
  - `v2_realtime_odds_snapshots`

主な修正:
- `v2_races.deadline_time` / `deadline_at` 対応
- race_noを無視して最初の締切時刻を拾うparser不具合を修正
- BOAT RACE場コード辞書修正
- `v21_realtime_collector_pg.py` の三連単ticket validation修正
- 月次補修 / nightly results / daily data prepareをPostgreSQL版へ移行

### Phase B — PRE / FINAL / LINEの運用チェーン整理
時間帯を重複windowで運用。

- morning: 08:30〜10:15程度
- day: 09:45〜15:00程度
- night: 14:45以降

基本処理:
**オッズ取得 → PRE判定 → 通知**

FINAL chain:
`run_final_pg.py`
→ `v25_final_realtime_pipeline_pg.py`
→ `v21_realtime_collector_pg.py`
→ `run_v22_targeted_pg.py`
→ `v22_exhibition_shadow_pg.py`
→ `v23_line_notifier_batch_pg.py`

### Phase C — Railway Bridge
手作業でRailway UIとChatGPTを往復する負担を減らすため、GitHub Issue #42をowner-only control/audit hubとしてRailway Bridgeを構築。

概念:
ChatGPT → Issue #42 command → GitHub Actions → Railway CLI/API → Railway → Issue結果

read-only確認を優先し、write commandはexact CONFIRM gateを持つ。

### Phase D — Production予想と研究系を分離
システムを混同しない。

**A. Production予想系**
- current v24 PRE
- FINAL realtime
- LINE
- BUY / WATCH / SKIP

**B. Shadow / research**
- Bao
- candidate N01/N02
- Opponent Pressure
- motor actual / GUARD05
- Exhibition ST
- racer-course top3
- 馬王型value研究

研究結果が良く見えても、自動でAへ昇格しない。

---

## 5. 主要研究ラインの引き継ぎ

### 5.1 PRE low-core / N02
現行v24 low-coreは非常に希少。

確認済みlow-core:
- prob rank 11–20
- market rank 1
- odds 3〜5

7日診断では ready 1049に対しlow_core 4程度。
候補不足を理由にProduction閾値を緩めない。

N02固定:
- prob rank 11–20
- market rank 2–5
- odds 3–6
- R07–R10
- any venue/event
- select mode EV

N01拡張は再現性不足のためinactive。
N02条件をForward途中で後付け変更しない。

### 5.2 Bao / Motor2 / Exhibition Forward
Baoはresearch only。

固定:
- Motor2 beta = 0.06
- Exhibition beta = 0.06

formal evidenceはcomplete frozen evidenceのみ使用。
realized gates達成後も自動Production昇格せず、`READY_FOR_MANUAL_REVIEW`止まり。

### 5.3 Opponent Pressure
選手×相手コース/級別構成の影響を研究。

historical OOSでは複数splitで改善。
daily Shadow:
- `v2_opponent_pressure_shadow_v2`

現在の本命研究方式:
- **head-only mapping**
- Opponent Pressureは1着確率だけへ反映
- coefficient = 1.0固定
- 2着/3着conditionalはcurrent v24維持

historical OOSは強いが、初期realized Forwardはmixed。
**KEEP_FORWARD_RESEARCH / Production BLOCK**。
R05-08や特定日を見た後に除外filterを作らない。

### 5.4 Motor actual / GUARD05
実測motor 2-place rateは長期OOSで改善傾向。
ただし交換直後・場別変動を考慮。

公式motor generation startを一次情報とし、DB first-seenを公式開始日扱いしない。

GUARD05固定:
- COUNT_MODE = `PRIOR_DAY`
- prior-day appearances <=5 → motor2 = 33.0
- >=6 → actual motor2
- threshold 5をForward開始後に動かさない

専用table:
- `v2_motor_guard05_forward_shadow`

**KEEP_SHADOW / Production BLOCK**。
affected Forward rowsが十分集まるまで評価確定しない。

### 5.5 Exhibition ST
current v24へexhibition start timingを追加する固定OOSで小さいが一貫改善。

固定:
- beta = **-0.02**
- official beforeinfo only
- deadline 8〜15分前
- BASE/ST 120確率をfirst snapshotとしてfreeze
- result / odds非参照
- first snapshot wins

専用table:
- `v2_exhibition_st_forward_shadow`

GitHub Actionsはscheduled delay対策として2分間隔loop方式へ改善済み。
**Production BLOCK**。

### 5.6 選手×コース3連対率 Forward
2026-08-25追加。

fixed OOS:
- complete-case
- source created_at <=08:15 JST
- deadline前
- coefficient gridで3/3 OOSが0.50を選択
- 0.50がgrid上端でも同じOOSで追加探索せず固定

Forward:
- `v2_racer_course_top3_forward_shadow`
- coefficient = **0.50固定**
- first-write-wins
- research only

**KEEP_FIXED_FORWARD_SHADOW_RESEARCH_ONLY**。

### 5.7 馬王型 / value研究
通常予想の代替にしない。
v24 raw probabilityをそのまま理論オッズ/EVへ変換しない。
calibrationが不十分で、value ratioが高いほどROI改善という関係も確認できていない。
通常予想Aの補助研究として扱う。

---

## 6. PR #169
Open Draft:
- `Draft: temporary 10-minute base-odds refresh`

base oddsの完全性改善案だが、PRE候補・予測価値改善の証拠が不足。

**DO NOT MERGE BY DEFAULT.**
DB復旧作業とも無関係。
明確なprediction / learning valueが確認されるまでhold。

---

## 7. 2026-08-28〜31 Railway Postgres障害と復旧

### 障害
Railwayの元 `postgres` serviceが消失。
一方で:
- `postgres-volume` は残存
- 約3.76 GB使用
- existing `Pre-Security-Patch Backup` 残存

consumer側 `DATABASE_URL` が空になりDB依存cronがCRASHED。

### Stage 1
元deploymentからexact runtimeをread-only復元:
- PostgreSQL major 18
- original image digestを特定
- PGDATA / mount / variables topologyを特定

mutable tag `:18` のdigest driftを検出したため、deleted deploymentのdigestへpin。

isolated `postgres-recovery` を作成しpreserved volumeをattach。
temporary TCP proxy経由のread-only integrity audit PASS。

確認:
- PostgreSQL 18.6
- database size 約3.47 GB
- `v2_races` 65,046
- `v2_race_entries` 390,276
- `v2_results` 64,902
- `v2_odds_trifecta` estimated 7,401,959

### Stage 2
rename権限問題のため、DB本体を動かさずcompatibility namespace方式を採用。

- DB actual: `postgres-recovery`
- compatibility: `postgres`
- public TCP proxy復元
- consumer 13 services `DATABASE_URL` relink
- DB依存10 services redeploy accepted 10/10
- latest inventory: **15 services**
- DB references: resolved_url
- application / cron: SUCCESS

2026-08-31 fixed-date catch-up:
- races 144
- entries 864
- odds 1,399 rows / 65 races
- results 0
- success 144
- 07:55 JST today-health = `PASS_READ_ONLY`

**Current decision: POSTGRES_RECOVERY_STAGE2_COMPLETE_PRODUCTION_DB_REFERENCES_RESTORED**

---

## 8. 2026-08-31 新規プロジェクト移行時のcurrent基準

この移行文書作成時に確認したGitHub:
- latest main commit: `f48343079585886fc5c996a6144181dfee1af138`
- message: `Docs: record completed Postgres Stage 2 recovery (#297)`
- open PR: **#169のみ**
- #169はDraft hold

再開時には必ずcurrent値を再取得する。

---

## 9. 次に再開する作業

まずPrediction研究へ戻る前に、復旧後の通常運転をread-only確認する。

順番:
1. current main / open PR再確認
2. Issue #42 Bridge health
3. Railway inventory
4. morning window後の `/railway today-health`
5. morning odds / PRE / FINALの通常pipelineが復旧後DBで正常か確認
6. 異常がなければPostgres障害復旧フェーズを完了扱い
7. 元の精度改善へ戻る

精度改善へ戻った後の優先:
1. Opponent Pressure head-only fixed Forward
2. GUARD05 affected Forward
3. Exhibition ST fixed Forward
4. racer-course top3 fixed Forward
5. Bao formal gate read-only audit
6. 新しい証拠が十分な機能だけmanual promotion review

Production v24 / FINAL / LINE / BUY-WATCH-SKIP / thresholds / coefficientsは、上記確認だけを理由に変更しない。

---

## 10. 新しいChatGPT側の作業スタイル

- 過去チャット全文を毎回読み直すのではなくGitHub docsをSourceとして使う。
- 変更前に必ずcurrent stateをread-onlyで再取得する。
- 過去に却下した案を理由確認なしに再実装しない。
- 既存Shadow/Forwardを重複実装しない。
- 調査結果は重要判断ごとに:
  - `PROJECT_HANDOFF.md` = 現在地
  - `PROJECT_HISTORY.md` = 判断経緯
  - 詳細ログ = `DEVELOPMENT_STATUS.md` / PR / Issue #42
  へ残す。
- ユーザー報告は原則「実施内容」「結果」を簡潔にする。
- タイムアウトしやすい連続操作は、一つずつ安全に進める。

---

## 11. 引き継ぎ完了条件

新しいChatGPTプロジェクトが以下を認識できれば移行完了。

- GitHub / RailwayのSource of Truth
- Supabaseは削除済み
- `v2_race_entries` が正しい
- Issue #42 Railway Bridge
- ProductionとShadow/researchの分離
- PR #169 hold
- Opponent Pressure / GUARD05 / Exhibition ST / racer-course / Baoの現在地
- Postgres Stage 2復旧完了
- DB actual `postgres-recovery` + compatibility `postgres`
- 次は復旧後morning通常運転のread-only確認
- 安全なPRフローとProduction promotion gate

この条件を満たした後は、古いNo.1〜No.5チャットを新規プロジェクトへ丸ごと移動しなくても、GitHubを基準に継続可能。


---

## 12. 2026-08-31 11:07 JST current checkpoint

トーク容量上限による次チャット移行用の最新差分。

- handoff作成直前 main: `3445fad33dcceeceec1b529aa9c00aff1201ec74`
- open PR: #169のみ（Draft hold）
- Postgres Stage 2: 完了
- DB actual: `postgres-recovery`
- compatibility: `postgres`
- 15 services、consumer DB references resolved
- 11:07 JST today-health: PASS_READ_ONLY、144 races / 864 entries / odds 9,841 rows・106 races
- outage-gap repair:
  - 8/28 complete
  - 8/29 complete
  - 8/30 pending review
- 次の最優先: 8/30 read-only audit → 必要ならguarded repair → 再audit → 当日通常pipeline health
- Parallel TOTO repo `kenshoushouri-cloud/toto-ai-v1`: bootstrap済み、Railway未作成、boatと完全分離

詳細は `docs/PROJECT_HANDOFF.md` の `CONTEXT_LIMIT_HANDOFF_20260831_1107` と `docs/PROJECT_HISTORY.md` の同日checkpointを参照。
