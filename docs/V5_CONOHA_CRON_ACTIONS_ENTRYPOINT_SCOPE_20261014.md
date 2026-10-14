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

## Next ONE task

ConoHaサポート返信をまず確認。復旧なら既存2GB VPSをread-only診断。未復旧なら**上記2workflowの直近GitHub Actions runメタデータだけ**read-only確認し、schedule起動実績の有無・状態を区別する。ログ/Secrets/DB/稼働変更/再実行/課金/BUY禁止。
