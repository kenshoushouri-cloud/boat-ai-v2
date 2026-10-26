# 新チャット起点（2026-10-26、V5優先）

@GitHub
@Railway

Repository `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md` → 指定compact → 本ファイルのみ参照。過去の長文ログは必要箇所だけ。

ConoHaの旧 `public.v2_*` にcollectorが書込中、13 `boat_data` VIEWは旧原本参照、V5 stage13物理表の初回+表別差分追込済み（10/26 03:16の時点、CDCなし）。正式writer cutover0/13、BUY OFF。V5 LIVE VIEW読み取り専用5分shadow monitorが起動したが、実V5予測計算はまだ未稼働。旧collectorは停止不可、odds/展示/気象の再現不可能な時点観測を保護。独立バックアップ復元gateも未完。

10/26朝 collectorは07:34時点200/288実行中、failed=0、丸亀8艇で選手成績解析の13値一括NULL疑い。13項目全部必須は不採用、**正当な未集計は高評価選手を減点せず**、解析失敗と出所不明はHOLD。pure policy `v5/entry_quality_policy.py` と synthetic tests追加済み（実行未検証）。稼働中コードには未反映。`docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`参照。

2026-10-26 07:52 JST、ユーザーのConoHa Termiusで morning.service の朝07:00開始処理が **07:45:54 JST 正常完了**：`progress race/result: 288/288 success=144 no_race=144 failed=0`, `Finished boat-v5-daily@morning.service`, `ActiveState=inactive Result=success ExecMainStatus=0`。`no_race` はHTMLにレース出走表が無い等でスキップした数であり、144中止を意味しない。丸亀（15）の `ENTRY_STATS_PARSE_FAILED` 8艇程度は朝処理全体の成功と別のデータ品質課題として残る。今日のV5 5分読取専用shadowは07:12にActive確認済、07:45以降の稼働状況は未確認。現在もV5実モデル推論/予測保存は未確認、stage writer完全切替0/13、BUY OFF。

2026-10-26 07:56 JST Termius実機：V5 read-only shadow timer=active（次08:00）、07:45/07:50/07:55のログ正常。07:45に元VIEW 138R、07:50と07:55に144R。次の6レースは全てentries=6/racers=6、exhibition=0/odds=0で`WAIT_INPUT`、`structurally_ready=0`。直近締切=08:35（21_01）、次08:47（10_01）。**正常入力監視＝予測モデル稼働ではない**。GitHub`boat-v5-forward-window.timer`は07..23の5分刻み、`v5/conoha_realtime_window_pg.py`は締切9〜24分前のみ処理、毎回最大2Rを公式サイト取得する。08:35の最初の取得候補は予定上08:15頃なので、07:55の展示/oddsゼロだけで障害とは判断できない。収集タイマーがlive稼働した証拠は別途必要。

10/26 10:12:40 JST Termius：V5専用stageの`races`だけ日中guarded差分同期完了。`DELTA_VERIFIED races source_rows=74208 stage_rows=74208 insert_update_delete=[144,0,0] bounded_windows=19`、`DELTA_TABLE_COMMITTED`、stage-only、旧writer/V4原本/13 LIVE VIEW untouched、継続CDCなし、BUY OFF。空き62.41GiB。残り11系統の10/26最新データは夜間同期未実施。V5本番prediction/writer cutoverは未実施。

10/26 10:18 JST、ユーザー実機read-onlyで`TODAY_RACES`原本144/V5 stage144/欠損0=`STAGE_RACE_IDS_MATCH_NOW`。前段10:12のguarded races deltaで全期間74208/74208、追加144、削除0、旧writer untouched。まだ11系統の当日差分未同期、V5 stage→正式writer切替0/13、BUY OFF。新規`deploy/conoha/v5_stage11_delta_schedule_once_20261026.sh`（commit `77a02288896df3fc6b8de6c98458a935420588da`）をGitHub追加。2026-10-27 03:05 JST一回限りstage-only 11系統sync、PG metadata preview/日付・timer・空き容量等のguard付き。**未スケジュール、ConoHa未実行**。当日最新オフサイトバックアップ・独立復元未確認、V4削除禁止。

10/26 10:30 JST stage11 night timer: 11表metadata preview PASS/no writes、実際のNEXT=Tue 2026-10-27 03:05:00 JST。しかし元scheduler末尾が誤って26日03:05を検証したため`HOLD: Unexpected next start, timer stopped`。同期未実施。GitHub元schedulerの誤判定修正 commit `b619fc7727e223b32ba2fe41a615a825433b16d5`。**元schedulerを再実行しない**。既存timer restart または一時unit GC後の別名再予約を安全に分岐する`deploy/conoha/v5_stage11_delta_timer_recover_guarded_20261026.sh` commit `2f53818294e85b5a0674a248f04dfaaf6f3585cb`追加、未実行。既存collector・VIEW不変、BUY OFF、V4削除・stage正式切替禁止。

2026-10-26 10:39 JST ユーザーTermiusにてstage11一回限り復旧タイマー予約のPASSを実機確認：`PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED`、`UNIT=boat-v5-stage11-delta-20261027-recovery.timer`、`NEXT=Tue 2026-10-27 03:05:00 JST`、`STAGE_SCOPE=11_NO_RACES`、`LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO`。データ差分同期はまだ実行されていない。元の停止済みタイマーの再起動・重複予約は絶対にしない。
バックアップ準備：既存Driveバックアップは過去の10/19世代のみ確認履歴、ConoHa同VPSの10/23 railwayと10/24 history dumpは最新10/26データの独立保全を証明しない。Google Driveコネクタの2アカウントをREAD ONLYで`boat-ai-v5`/`main_current_202610`/`dump`検索したが、新しい暗号化バックアップファイルを特定できなかった（検索結果ゼロ≠不在の証明）。既存Pythonインベントリに`/var/backups`と既知の2dumpフォルダを追加したread-only `deploy/conoha/v5_backup_restore_path_inventory_readonly_20261026.py`（commit `b43a725e4dcc20fb460fe200aa001645910fc01c`）をGitHub作成、実機未実行。秘密・ダンプ本文・DBに触れない。BUY OFF。

**Next ONE task:** Termiusでコミット固定の`deploy/conoha/v5_backup_restore_path_inventory_readonly_20261026.py`をrootの`python3`でread-only実行し、既存dumpフォルダ・age/rclone/pg_restore/空き容量などメタデータのみ確認。旧dump削除・Drive upload/rclone変更/DB変更/タイマー追加はしない。夜間stage11実行後は必ず`journalctl -u boat-v5-stage11-delta-20261027-recovery.service --no-pager -n 100`で11系統コミット結果を確認し、結果が確認されるまで本番切替・V4削除はNO-GO。
