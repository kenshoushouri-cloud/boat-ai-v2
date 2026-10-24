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
## 2026-10-24 22:07 JST：合成テストと優先順位変更
- User Termius`tests/test_v5_offsite_encrypted_dump_verify.py`: **8/8 PASS**（`Ran 8 tests` / `OK`）。暗号化本物のファイル受信/復号/復元は未実施。独立復元NO-GO維持。
- ユーザーの方針：データを共通`boat_data_stage`へ複製し、**既存収集を動かし続けながらV5をpaper-only並行稼働**、同期による欠損は後追いで補完し、整理データによるbacktestと直前入力の実戦評価を優先する。ChatGPT設計`docs/V5_DUAL_RUN_SHADOW_SYNC_PLAN_20261024.md`。
- **区別**：ユーザー言う「複製元の稼働」は現在の`railway.public.v2_*`原本側writer/collector継続のことであり、停止済みV3/V4の別collectorを再起動する意味ではない。二重に外部サイトへ取りにいかない。source → stage一方向copy/sync＋V5読むだけ。段階コピー中の更新/削除は完全PK再照合で追込。後日公式結果は補完可だが変動オッズ/展示初回観測は事前証明扱いしない。
- 実Stage状態は21:11でvenues1/13、残り12 ABSENT、物理本番切替0/13。独立復元・全writer/完全差分/rollback未完了、今夜03:30未予約・BUY OFF。既存13 VIEWはread-only researchに今すぐ使用可能。**元DB writer停止・本番VIEW切替は不要のV5 shadow開始と、将来の物理原本切替を分ける。**
## 2026-10-24 夜間切替へのユーザー指摘に基づく修正
- 直前オッズ/展示/気象は旧原本collectorが既に稼働していれば原則継続収集。夜間03:30には通常レースがないため露出が小さいが、5分間隔forward timerや01:20 catchup等は常に考慮。
- **第1段階は物理原本や収集writerを切り替えず、V5 shadowの読み取り参照先だけ複製stageへ**。日中にCOPYして夜間に完全PK差分と鮮度を検査し、問題があれば既存VIEW読取に戻す。これなら既存収集を止める理由が少ない。第2段階のwriter移転は別承認・独立復元等が必要。
- そのため外部バックアップ試験に全開発をブロックされず、VIEWに基づくV5の前向き非購入研究/少量バックテストを並行開発する。`docs/V5_DUAL_RUN_SHADOW_SYNC_PLAN_20261024.md`の節参照。夜間cutoverはまだ実装・予約なし。
## 2026-10-24：forward-windowタイマーの深夜起動に関する訂正
- 実GitHub source `deploy/conoha/boat-v5-forward-window.timer`: `OnCalendar=*-*-* 07..23:0/5:00 Asia/Tokyo`、`Persistent=false`。5分刻みの直前レース情報（exhibition/odds）収集は07:00〜23:55 JSTだけに設定。**03:30には発火しない。** 直前collector`v5/conoha_realtime_window_pg.py`は当日締切9〜24分前(オプションlate-retry5〜24分)かつ展示6艇/オッズ120券未満だけ候補にする。
- 先の「5分タイマーは03:30に起動し得る」は**誤り**。修正済`docs/V5_DUAL_RUN_SHADOW_SYNC_PLAN_20261024.md`。実VPS unitの一致をread-only確認すれば、それ以上タイマーを変更する必要はない。01:20 catchup、その他不明writer、07:00 morningが終了/待機しているかのgateは別。
- **夜間の実切替はなお未スケジュール**。stage1/13、live0/13、Drive403 STOP/BUY OFF。

## 2026-10-24 catchup schedule review
- GitHub current catchup timer 01:20,02:20,03:20 JST (three runs), service max1800sec per run and flock shared with 23:00 night job (night max90min). Earlier proposed times **00:45,01:30,02:15 JST**. Last run can end ~02:45 -> ~45min margin before future 03:30 reader-only switch. On unresolved official PENDING/worker still active, fail-closed hold switch.
- Provisional config `deploy/conoha/boat-v5-midnight-catchup.timer.proposed-early-20261024` GitHub commit only; **not installed nor activated on ConoHa**. 5min realtime forward timer only 07..23. Verify installed unit + recent journal read-only before any live timer change. No BUY, no physical cutover.

## Next ONE task
既存V5 scorer/inferenceが`boat_data.*` VIEWを**read-onlyでそのまま消費して非購入の実データbacktest/pilotを開始できるかを確認**し、必要なアダプタをGitHubで実装。stage物理COPY/reader switchの自動ゲートも開発するが未準備でのタイマー登録禁止。
