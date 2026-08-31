# boat-ai-v2 — ChatGPT Lightweight Bootstrap

更新日時: 2026-08-31 JST

このファイルは、新しいChatGPTプロジェクト／新しいチャットが**最初に読む唯一の常設入口**。
過去チャット No.1〜No.6 の全文を引き継がず、GitHubに圧縮した「現在状態」から再開する。

## 0. 最重要ルール

- 開始時に読むのは原則このファイルだけ。
- `PROJECT_HANDOFF.md` / `PROJECT_HISTORY.md` / `DEVELOPMENT_STATUS.md` を開始時に全文取得しない。
- GitHub Issue #42 のコメント全件を取得しない。
- 必要な過去情報は、対象機能名・PR番号・日付・エラー名で**部分検索**する。
- 新しいチャットへ「前のチャットを引き継いで」と依頼しない。
- No.1〜No.6 はArchive扱い。通常運用では読み込まない。
- このファイルに書かれたSHA・件数はcheckpoint。再開時にはcurrent値を再取得する。
- 安全なmaintenance writeは、ChatGPTが直前に対象・範囲・影響を1件に限定して明示した場合、ユーザーの「続けて」「進めて」「実行して」等の明確な自然言語承認を、その1件に限る明示承認として扱ってよい。ChatGPTは既存workflowが要求する完全一致commandへ変換してIssue #42へ投稿する。
- 上記の承認は**単発・非再利用**。別の日付・別operation・追加writeには自動継承しない。
- destructive/high-impact操作（service/volume/backupのdelete・restore・rename、Railway Variables/schedules変更、schema destructive migration、Production model/LINE/BUY-WATCH-SKIP/thresholds/coefficients変更、PR #169 activation、main merge）は自然言語の「続けて」へ自動変換せず、対象操作を明示した個別承認を必要とする。

## 1. Source of Truth

### Code
- Repository: `kenshoushouri-cloud/boat-ai-v2`
- code Source of Truth: **GitHub main**
- mainへ直接書かない。
- 原則: branch → Draft PR → CI → review → ready → merge。

### Production data
- Railway project: `boat-v2-postgres`
- data Source of Truth: **Railway PostgreSQL**
- Supabaseは削除済み。使用しない。
- 正しい出走表テーブル: **`v2_race_entries`**

## 2. Current checkpoint

このBootstrap作成直前のmain:
- `90dd96872c1006e4293c817f08315898abc2571f`
- PR #307: `Ops: add fixed outage official-source audit`

Open PR:
- **#169** `Draft: temporary 10-minute base-odds refresh`
- HOLD。明確なprediction / learning valueなしにmergeしない。

## 3. Railway / PostgreSQL current topology

2026-08-31 Stage 2復旧後:
- DB実体: **`postgres-recovery`**
- compatibility namespace: **`postgres`**
- preserved volume: **`postgres-volume`** → `postgres-recovery` に接続
- PostgreSQL: **18.6**
- deleted deploymentのpinned image digestを使用
- consumer DATABASE_URLは `postgres-recovery` へのRailway Referenceへrelink済み
- checkpointでは15 services / DB references resolved / application・cron SUCCESS

**この二層構成を、明確なmigration planなしにrename/delete/統合しない。**
Volume / backupをwipe/delete/restoreしない。

運用詳細が必要な時だけ `docs/OPS_STATE.md` を読む。

## 4. Production prediction invariants

Production本線:
- v24 PRE
- FINAL realtime
- LINE
- BUY / WATCH / SKIP

研究機能はProductionと分離。
OOS / walk-forward / Forward / live evidenceなしに昇格しない。

このBootstrap作成時点で、以下は勝手に変更しない:
- v24 / FINAL logic
- LINE
- BUY / WATCH / SKIP
- thresholds / coefficients
- N01 / N02
- Bao
- PR #169
- Railway Variables / schedules

## 5. Active operational checkpoint

2026-08-28〜30のDB障害期間のgap補修:
- 8/28: repair済み
- 8/29: repair済み
- 8/30: official-source read-only auditはPASS。ただしDB exhibition 984行に対し公式K sourceは1004/1008行で、復元可能な20行不足を確認。guarded repair待ち。
- PR #307で、8/28〜30をBOAT RACE公式K sourceで確認する**read-only audit**を追加
- Issue #42 command: `/railway outage-source-audit`

重要:
- Issue #42を全文取得しない。
- このcommandが必要なら、command実行とその**新しい結果だけ**を扱う。
- LINE / model / Shadow / Forward evidenceを障害補修で再生成しない。

次の安全な運用順:
1. current main / open PRを短く確認
2. 必要なら `OPS_STATE.md` を読む
3. 8/30 outage-gapをread-onlyで確認
4. 当日 `today-health` と通常pipelineの継続正常性をread-only確認
5. DB障害復旧フェーズを終了できたら研究ラインへ戻る

## 6. Research current summary

詳細が必要な時だけ `docs/RESEARCH_STATE.md` を読む。

- Opponent Pressure head-only: research only / Production BLOCK
- GUARD05: Forward Shadow / Production BLOCK
- Exhibition ST beta=-0.02: Forward Shadow / Production BLOCK
- Racer Course Top3 coefficient=0.50: Forward Shadow / Production BLOCK
- Bao: formal gate待ち / automatic promotion禁止
- N02: fixed rule維持 / 後付け条件変更禁止
- 馬王型: 補助研究。v24 raw probabilityをそのままEVへ使わない

## 7. Archive / deep-history usage

必要な場合のみ:
- `docs/PROJECT_HANDOFF.md`: 詳細な現在地・過去マイルストーン
- `docs/PROJECT_HISTORY.md`: 採用/却下理由
- `docs/DEVELOPMENT_STATUS.md`: 実験詳細
- `docs/archive/CHATGPT_PROJECT_MIGRATION_LEGACY_20260831.md`: 旧ChatGPT移行文書
- GitHub PR / commit / Issue #42: 必要な対象だけ

**全文を一括で読まず、検索語・section・line rangeを限定する。**

## 8. New chat startup sequence

新しいチャットでは:
1. この `CHATGPT_BOOTSTRAP.md` を読む。
2. current main SHAとopen PRだけ確認。
3. 今回のタスクがOpsなら `OPS_STATE.md`、研究なら `RESEARCH_STATE.md` だけ追加で読む。
4. 過去判断が必要な場合だけHISTORY/HANDOFFを部分検索。
5. Issue #42は必要なcommandの最新結果だけ扱う。
6. 作業後、現在状態が変わった場合だけこのBootstrapを**上書き更新**する。

## 9. Context budget maintenance

このファイルは履歴ログではない。
- 目安: 150行以内
- 過去経緯を追記し続けない
- CURRENT / HOLD / NEXTだけ残す
- 古くなった数値・checkpointは置換する
- 詳細な経緯はHISTORYへ移す

目的は「No.7、No.8、No.20になっても、新しいチャットを軽い状態から開始できること」。

## 10. Parallel project note

別repo `kenshoushouri-cloud/toto-ai-v1` は別プロジェクト。
boat-ai-v2とDB / Variables / servicesを共有しない。
boat作業のBootstrapへTOTOの詳細を混ぜ込まない。
