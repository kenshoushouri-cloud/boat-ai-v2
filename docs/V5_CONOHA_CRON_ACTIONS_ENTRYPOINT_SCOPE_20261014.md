# V5/ConoHa — cron・Actions起動宣言の限定静的照合（2026-10-14 JST）

**結論：V5用の共通ロックを通る、本番承認済みの定期writer入口は今回の抽出範囲で確認できない。V5への流用はHOLD。** この結論は作業branchの一部ファイルを読んだ結果であり、**全workflow・Railway実稼働cron・Actions実行履歴・実環境・VPSに対する網羅性はない**。

- Repository: `kenshoushouri-cloud/boat-ai-v2`、branch: `feature/v5-prior-day-counter-test-20261011`
- 閲覧だけ：`.github/workflows`の一覧345件から関連11件を抽出し全文確認、リポジトリroot（198項目）および`ops/conoha`（9項目）の名前を確認。新たなjob実行/CI/DB接続/通信/VPS起動/Secrets確認は**一切行っていない**。全345件の内容は読んでいない。
- 参照：`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`、`docs/V5_CONOHA_WRITER_LOCK_COVERAGE_GAPS_20261014.md`、`ops/conoha/v5_writer_lock_static_check.py`。

## 起動宣言から分かった入口（今回読んだ11件）

| workflow | 設定されたトリガー・呼出し | V5共通ロック判定 |
|---|---|---|
| `railway-candidate-v4-daily-prepare-catchup-20261006.yml` | owner指定issueコメント→`railway run`→`run_daily_data_prepare_pg.py` | 既存candidate-v4向けの手動補完宣言。ConoHa guard経由でない。**V5移植不可** |
| `railway-candidate-v4-results-catchup-20261006.yml` | owner指定issueコメント→`railway run`→`run_nightly_results_pg.py` | 同上。V5共通ロックの証拠でない |
| `window-refresh-confirmed-run.yml` | PR検査またはowner指定issueコメント→`run_window_refresh_pg.py`（実行時`WINDOW_REFRESH_EXECUTE=1`） | ConoHa guard経由でない。自動schedule宣言は今回のファイルにない |
| `exhibition-st-forward-scheduled-collector.yml` | **schedule `*/5 22,23,0-12 * * *` (UTC)** → `collect_exhibition_st_forward_shadow_pg.py`、`EXH_ST_FORWARD_DRY_RUN=0` | **旧研究向け定期writer宣言**。GitHub concurrency groupはVPSの共通`flock`と別物。V5移植・有効化HOLD |
| `racer-course-top3-forward-scheduled-collector.yml` | **schedule `45 21 * * *` (UTC)** → `collect_racer_course_top3_forward_shadow_pg.py`、`RACER_COURSE_FORWARD_DRY_RUN=0` | **別の旧研究向け定期writer宣言**。checker許可名6件にも含まれない。V5移植HOLD |
| `v5-capture-pipeline-realpg-integration.yml` | owner指定issueコメント→使い捨てPostgresで検証 | V5本番writer/cronではない |
| `v5-first-write-postgres-integration.yml` | owner指定issueコメント→使い捨てPostgresで検証 | 同上 |
| `v5-one-race-official-readonly-observation.yml` | owner指定issueコメント→固定レースの時刻制限付き観測 | 本番の周期収集ではない（名称を安全保証とみなさない） |
| `research-v5-strong-core-entry-form-offline-tests.yml` | owner指定issueコメント→offline unittest | writer cronではない |
| `railway-v5-strong-core-calibration.yml` | owner指定issueコメント→candidate-v4への`railway run`研究読取 | V5本番writerではない |
| `v5-official-capture-to-first-write-offline.yml` | owner指定issueコメント→mock/offline検証 | writer cronではない |

## checkerとの対応・未解決事項

- 既存checker許可名6件のうち**今回2件の手動補完宣言**（`run_daily_data_prepare_pg.py`、`run_nightly_results_pg.py`）と1件の`run_window_refresh_pg.py`を確認。別の1件`collect_exhibition_st_forward_shadow_pg.py`は**scheduleトリガー**だがConoHa guard不使用。残る`run_odds_window_pg.py`、`save_k_day_results_pg.py`は**直接起動宣言を今回の11件からは確認できない**（別の場所には存在し得る）。
- **checkerにない定期writer** `collect_racer_course_top3_forward_shadow_pg.py` を静的に確認。V5採用候補として自動追加しない。旧PRE/旧FINAL経路の完全な無効化や実cronの状態は不明。
- GitHub scheduleはデフォルトbranchでの実行条件が関係する。**feature branchにscheduleがあることだけで現在の稼働を意味しない**。
- `ops/conoha`に新guardはあるが、今回読んだworkflowには`v5_serial_resource_guard.sh --execute --`の起動宣言は見つからない。
- 未読の334 workflow、`.railway/compact-bridge`以下、Railway Dashboard service cron、VPS systemd/cron、別entrypoint、実環境`V5_SERIAL_LOCK_FILE`は未確認。**この結果を「全件安全」「全件不稼働」と解釈禁止**。

## main と作業branchの定期writer宣言照合（10/14）

**2/2 完全一致**（GitHub Contents のblob SHA比較および起動宣言確認）。展示ST workflow SHA `a90d4f88e2fccf8fe4270ac6f4541e78260c2312`: `schedule: */5 22,23,0-12 * * *` (UTC)、`EXH_ST_FORWARD_DRY_RUN: '0'`、`python -u collect_exhibition_st_forward_shadow_pg.py`。選手コース workflow SHA `3ed72123a3230ad5dbe04500731be80efbec3810`: `schedule: 45 21 * * *` (UTC)、`RACER_COURSE_FORWARD_DRY_RUN: '0'`、`python -u collect_racer_course_top3_forward_shadow_pg.py`。**mainに定義は存在**するが、Actionsの有効・無効、直近起動/成功/DB書込状況は未確認。ConoHa共通guard経由の宣言なし。**削除・停止・実行・移行は一切していない**。

## GitHub Actions直近runメタデータ（10/14 JST）

**mainの実schedule起動は2/2確認、直近は双方failure。** 公開GitHub APIの`actions/runs`一覧の先頭100件のみを取得した読取専用確認（全履歴や原因調査ではない）。

- 展示ST: run [`38491689226`](https://github.com/kenshoushouri-cloud/boat-ai-v2/actions/runs/38491689226)、2026-10-14 00:42:32Z（09:42:32 JST）、`event=schedule`, `head_branch=main`, `status=completed`, `conclusion=failure`。
- 選手コース: run [`38491242338`](https://github.com/kenshoushouri-cloud/boat-ai-v2/actions/runs/38491242338)、2026-10-14 00:37:39Z（09:37:39 JST）、同じく`schedule/main/completed/failure`。
- jobs/stepsメタデータを追加確認：展示ST run `38491689226`（collect job `115618118381`）、選手コース run `38491242338`（collect job `115616673072`）とも**Step 6「Load public database URL without publishing it」でfailure**。Step 5 dependenciesはsuccess、Step 7 collection loopはskipped、cleanupはsuccess。`validate` jobは両runでskipped。
- **今回のrunではcollection loop未実行**。失敗の根本原因/DB URL値/実際のDBアクセス/Runner利用料/他のcronは未確認。スケジュールによるCI消費リスクは継続し得るが請求額は推定しない。**ConoHa共通lockの動作証拠ではなく、復旧・再実行・停止を行っていない**。

## 定期Actionsの件数・時間と費用リスク（10/14 JST）

- GitHub REST `actions/runs?event=schedule&created=2026-10-12..2026-10-14&per_page=100` を**1ページread-only**確認。期間はUTC日付。全リポジトリ16件のschedule runのうち、展示ST**7件**・選手コース**3件**、対象計**10件/10件failure**、すべて`main`で1回目の試行。取得範囲内でsuccess=0。
- 対象10件の`run_started_at`→`updated_at`は各**11〜18秒**、合計**144秒（2分24秒）**。これは**メタデータ上の経過時間**でありRunnerの請求時間/作業CPU秒とは異なる。実行を試みた期間全体や今後の起動回数は保証しない。
- Repo APIでは`visibility=public`。確認した2 workflowの`runs-on: ubuntu-24.04`は標準GitHub-hosted runner。GitHub公式docsによると**公開repoの標準runner実行時間は無料**であり、対象runの標準runner分の**追加料金は0**。その他のActions storage/artifacts/cacheや他サービス料金は未監査。料金は推計しない。
- 失敗10件は旧研究系収集障害の証拠に留まる。**V5 writer未配線、Railway原本保護、本番HOLD**を維持し、旧収集の再実行・停止・修復は承認なく行わない。
- 参考（2026-10-14確認）：https://docs.github.com/en/actions/reference/runners/github-hosted-runners 、https://docs.github.com/en/billing/concepts/product-billing/github-actions

## Next ONE task

ConoHaサポート返信をまず確認。復旧なら既存2GB VPSのread-only診断。未復旧なら**既存の4DB暗号化バックアップ・独立復元の実行前提を、既存runbookとスクリプトから少数ファイルでread-only棚卸し**する。DB接続/復元/Secrets/cron実行・変更/課金/BUY禁止。
