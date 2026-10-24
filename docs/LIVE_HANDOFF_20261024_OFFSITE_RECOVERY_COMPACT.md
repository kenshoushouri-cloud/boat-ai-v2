# 新競艇AI開発プロジェクトNo.2：現行引継（2026-10-24、外部復元準備）

本書を現行compact正本とし、以前の長い`LIVE_HANDOFF_20261024_1906_COMPACT.md`は履歴扱い。GitHub repo `kenshoushouri-cloud/boat-ai-v2`。新チャットは`docs/HANDOFF_LATEST.md`→本書→`docs/NEXT_CHAT_START_HERE.md`だけ読む。SHA、DB現況、額、タイマーを固定値と扱わない。Termiusは短い1回コピペ、GitHub側実装を優先。

## 目的・制約
- V5主力競艇AI。2025年7月以降の保有データで精度向上、日次紙上予測と締切前の真正な初観測を重視。10月末は**限定非購入運用を目標**（保証ではない）。旧V4研究、V5 6艇確率/120券・as-of gate・shadow scorer等の既存資産を再利用。自動購入は別承認までOFF。Railway CPU/RAM/Networkと料金は低く（希望月$15〜20以下）、Railway Agent/AI使用禁止。
- ConoHa VPSの既存collector/4 V5 systemd timerは維持し、稼働中の収集・原本を変更しない。夜間ユーザー手動不可→将来03:30〜04:00 JST自動切替候補だが**タイマー未設置／切替未予約**。自動停止・rollback・復帰はまだ未完成。Drive rclone新規書込403 `RATE_LIMIT`につきSTOP。

## 確定保存先
- 原本DB `railway`の13物理`public.v2_*`、現行参照先`boat_data.*`13件はVIEW。物理stageは`boat_data_stage.venues`（24行）**だけ作成済み**。他`boat_data_stage.*`12個はABSENT。旧提案名`v5_data.raw_*`へ本コピーしない。**隔離stage1/13、本番切替0/13 NO-GO**。
- 履歴DB `boat_history_archive`が別に存在。固定保存先表`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`、13契約`boat_shared_storage_contract.py`。旧V3/V4/Drive世代を削除・上書きしない。

## 直近の実証
- 18:41 一括read-only準備PASS、レポート`/var/backups/v5_prepare_wLz5IWY7`。19:06まで合成29/29、19:30以降ステージ17+storage7/24 PASS、19:38 psql fallback4/4 PASS、19:58空stage原子DDL6/6 PASS、20:13実PG内CREATE12＋ROLLBACKリハーサルPASS（**永続作成ゼロ**）。過去合成テスト総数は重複があるので単純累積禁止。
- 21:11 ConoHaローカル`railway.dump`2026-10-23 393138215B、`boat_history_archive.dump`2026-10-24 81865791B のサイズ+SHA256+TOC両PASS（**同一VPSのみ**）。`railway`3482MB、history1069MB、WAL816MB、空き67717MB。同一FSに余裕はあるが独立復元未達。archive実パスはread-onlyでサイズ/SHA一致により特定済み。繰り返し探索不要。
- Google Drive二接続をread-only調査、V5外部`.age`旧世代を確認。主なV5専用フォルダーに10/19 main 297756932B、archive 52130144B。別アカウントに類似バックアップ、両アカウントの鍵復旧関連`.age`371Bも存在。**鍵未確認・復号未実施・全SHA/別環境復元/現在世代未証明**。記録`docs/V5_EXTERNAL_BACKUP_INVENTORY_20261024.md`。
- 10/19のバックアップは10/24に取得したデータと同一でないため、復号・目録PASSだけで当日バックアップゲートを満たさない。

## 新規GitHub成果（まだ新コード未実行）
- `v5/offsite_encrypted_dump_verify.py`：別マシン上に**既に取得済み**の暗号化10/19 main+archiveファイルについて、名前/byte数/ageヘッダ/SHA256を照合。明示`--decrypt-toc`を指定した場合のみ非公開のローカル鍵を使いtemp復号・`pg_restore -l`。**本番ConoHaでは実復号禁止**。PG実復元は行わない。
- `tests/test_v5_offsite_encrypted_dump_verify.py`：8件の合成テスト、**実行未確認**。
- `docs/V5_INDEPENDENT_RESTORE_EXECUTION_RUNBOOK_20261024.md`：独立復元の具体手順。Driveの旧世代データや秘密鍵の内容はChatGPT/GitHubに出さない。現在10/23-24のデータを別名で外部保存するにはDrive 403の解消・no-overwrite・別承認が必要。
- 実装済みだが永続実行前の`deploy/conoha/v5_stage_12_bootstrap_guarded.py`、`deploy/conoha/v5_online_stage_batch_copy.py`、`deploy/conoha/boat_shared_staging_delta_plan_offline.py`を再利用。12表を空で一括生成するSQLはリハーサルPASS済み。オンラインCOPY/DELETE含む最終差分・自動切戻し未完了。

## Next ONE task
新しい**8件のoffsite暗号化ファイル検証コード合成テストをオフライン/tmpで一度実行**（ConoHa上ではファイルや秘密鍵を触らず、DB/Driveアクセスも行わない）。同時に独立復元に必要な秘密鍵管理と「別環境」準備を明確にし、現行10/23-24世代をno-overwriteで外部保全する次の安全工程を進める。データ収集は止めず、永続12stage DDL／大量COPY／本番VIEW切替／03:30タイマー／BUYは禁止のまま。
