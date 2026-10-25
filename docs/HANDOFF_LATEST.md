# V5現行引継入口（2026-10-25 朝・実コピー完了）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`のみ。旧資料は履歴扱い、SHA・件数・タイマー実状態は必要時live確認。

**現況（10/25 08:16 JSTユーザーのConoHa journal画面）:** 10/25 02:50:09〜02:53:42に未コピー12系統全て `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。既存venues 24件と併せて `boat_data_stage` **初回物理snapshot 13/13**。12系統行数合計13,129,507、コピー時の各transaction rowcount一致。**初回snapshotだけ・最終delta/CDC・本番writer/read切替未実施、live physical 0/13**。旧collector/13 VIEW維持、BUY OFF。10/24夜にcatchup時刻前倒し00:45/01:30/02:15が実機PASS。独立VPS外restore未証明、Drive書込403 STOP、Railway費用最小。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

2026-10-25 08:25 JSTのユーザーConoHa画面で13/13の`relation_shapes`・`copy_column_shape`・`pk_shape`=PASS、PK `id`/`race_id`/複合`race_id,lane`/`venue_code`、source user_triggers=0、source FK_in/out=0、複数表にserial defaultあり。`ROLLBACK`、`V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES`で正常終了。これはメタデータ一致の証拠であって差分=0/CDCではない。

**2026-10-25 08:34 JST実機確認:** venues限定read-only差分PREVIEW成功。source=24/stage=24、INSERT=0、UPDATE=24、DELETE=0、`VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES`。24は削除や欠損ではなく行内容差。まだ実反映なし。旧収集・13 VIEW・BUY変更なし。13系統の物理初回copy13/13とPK/型一致13/13を維持。

2026-10-25 08:34 JST Termius実機：venues source24/stage24、read-only full outer compare INSERT=0 UPDATE=24 DELETE=0、`VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES`。更新24件は欠損24件ではない。何列が更新されたかは旧previewで未分類。

2026-10-25 08:40 JST: ConoHa Termiusでvenues source/stage各24、`VENUES_STAGE_DELTA_TRANSACTION_PASS upserted=24 deleted=0 bidirectional_equal_in_transaction=YES legacy_source_untouched=YES live_view_untouched=YES continuous_cdc=NO cutover=NO_GO BUY=OFF`、`VENUES_STAGE_ONLY_DELTA_COMMITTED_NOT_CDC_NOT_LIVE`確認。**venues stage差分反映・同一snapshot照合成功**。元public/VIEW unchanged。初回物理stage13/13、live物理切替0/13。

2026-10-25 08:46 JSTユーザーTermiusで12系統すべて `DELTA_PREVIEW_METADATA_PASS`、`PREVIEW_COMPLETE families=12 current_delta_counts=NOT_MEASURED no_table_scan=YES NO_WRITES NO_CUTOVER`。原本/ステージ列・主キー・初回コピーCOMMENT一致（12/12）。これは構造チェックで、12系統の差分適用やCDC、差分0を示さない。

2026-10-25 08:51:38 JSTユーザーのConoHa画面で `races` stage差分反映が成功。`DELTA_VERIFIED races source_rows=74064 stage_rows=74064 insert_update_delete=[168, 0, 0] bounded_windows=19`、`DELTA_TABLE_COMMITTED races`、`STAGE12_DELTA_SNAPSHOT_PASS families=1`、旧原本/VIEW不変更・BUY OFF・CDC=NOを確認。初回コピー13/13、stage差分反映2/13（venues+races）、本番物理切替0/13。

2026-10-25 09:02 JST、ユーザーのConoHa Termius画面で `PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED`、`NEXT=Mon 2026-10-26 03:05:00 JST`、`STAGE_SCOPE=11_NO_RACES`、`LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO` を確認。**予約は成功したが11系統の実差分同期は未実行**。初回snapshot13/13、差分同期済2/13（venues+races）、V5本番物理切替0/13。

2026-10-26 06:07 JSTのTermius画面（03:05:01–03:16:49 JST 実行ログ）で `STAGE12_DELTA_SNAPSHOT_PASS families=11 as_of_per_table_not_CDC=YES` とsystemd `Finished`、11系統各 `DELTA_VERIFIED`→`DELTA_TABLE_COMMITTED` を確認。新規追加は計44,536行（results168, entry_snapshots1938, race_condition323, racer_condition1938, racer_course_stats0, entries1008, exhibition918, weather323, racer_results0, odds_snapshots37920, trifecta_odds0）、更新/削除はいずれも0。初回物理stage13/13、差分反映13/13（venues、races＋11）、本番物理切替0/13。各表の実行時点で整合、連続CDC/最終共通時点の完全同一性を保証しない。旧collector・原本・13 VIEW不変更、BUY OFF。

2026-10-26 06:17 JST Termius実機：前日10/25の `races`168/168・`results`168/168・`entries`1008/1008 は全列・キー同一snapshot PASS。不足/余剰/異値0。`racer_results` は原本0/ステージ0で `HOLD_GAP_OR_NO_SOURCE`。**転送漏れとは言えないが、公式K-file詳細6艇の原本収集不足の可能性**。ソース `v5/conoha_midnight_results_pg.py` は通常のレース単位 `v2_results` のみ補完し、6艇詳細 `v2_result_entries` は別 `save_k_day_results_pg.py` がK-fileから保存（明示CONFIRM要）。`v5_data_views_v1.sql`にも10/7以降のK詳細欠損の既知注記。勝手にKデータ補完/外部取得を実行しない。

2026-10-26 06:24 JST ユーザーTermiusの15日K詳細監査で原本とstageの最新race_idは双方 `20261020_23_12`。10/11–14,10/18–20の7日間は日別全レース6艇分が両方で一致、10/15–17および10/21–25の8日間は両方とも選手別K詳細0行（計1,308既知レース、6艇想定7,848行相当）。`coverage_diff=0`で移設漏れではなく旧原本へのK結果取込未完。10/25のraces/results/entriesの全列照合はPASS、racer_resultsは原本0/先0のためHOLD。既存夜間collectorは3連単の通常確定結果のみ、公式K詳細保存は別job。

2026-10-26 06:32 JST ユーザーの公式K-file8日preview結果：8/8 HTTP200、6日(10/15,16,17,22,23,24)はDB既知race_idとKの解析race_idが全一致、全レース6艇、parser失敗0・重複0 → 984レース=5,904艇の書込前品質PASS（**まだDB補完・stage再追込は未実施**）。残2日：10/21 DB156 vs K144（12 race_id不足）、10/25 DB168 vs K167（1不足）。DB原本には近15日中8日で詳細行が存在せず、旧コピー漏れではない。差の13race_idが開催中止/欠測/公式K未掲載なのか未確定。データ登録を強行しない。

**Next ONE task:** GitHubに `deploy/conoha/v5_k_two_day_missing_ids_readonly_20261026.py`（commit `00aaf7226ed70415dba1d4cefa74d6efd025dd3e`）を追加、**VPS未実行**。10/21・10/25だけ公式Kを最大2 HTTP GETして、DB側にのみある13 race_idと`v2_results.result_status`、ticket/payoutをREAD ONLY表示し、未開催等とK欠落を分類する。許可済み解析6日分は再取得/自動保存せず、バックアップの独立復元gate未合格でDB書込禁止。既存収集稼働継続、stage13/13各表10/26 03:16時点までの差分反映、連続CDC未実装、実物理切替0/13、BUY OFF。
