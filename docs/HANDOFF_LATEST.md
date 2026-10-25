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

**Next ONE task:** GitHub登録済 `deploy/conoha/v5_k_result_entries_recent_gap_readonly_20261026.sql`（commit `c95e87cc8b12dadec7f24605f905448030216372`）をConoHaでREAD ONLY実行し、直近15日(前日まで)の詳細着順について原本・stageの6艇充足、最新race_id、日別欠損を確認する。**実VPSでの検査未実行**。欠損が原本起因ならK補完の実施可否を安全gateで別途設計。旧収集・stage13表維持、連続CDC/オフサイト独立復元/物理切替は未証明、BUY OFF。
