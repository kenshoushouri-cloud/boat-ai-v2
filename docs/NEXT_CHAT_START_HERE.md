# 新チャット最小起点 — 新競艇AI開発No.2（2026-10-25）

@GitHub
@Railway

repo `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md`→指定compact→本書だけ。古いhandoffと長いworkflowは大量参照せず、1作業ずつ短いlive取得。

**目的:** V5主力、2025-07以降の精度/真ROI検証、紙上非購入を早期稼働。ConoHa主・Railway費用最低限（$15–20/月を下回るほど良い）、Railway Agent/AI禁止。BUY OFF。

**最新の実データ状態（10/25 08:16 JSTユーザーConoHa journal）:** 12系統ステージ初回物理snapshotが10/25 02:53:42 JSTに全件 `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。先行会場24行と合わせ `boat_data_stage` **13/13初回コピー済**。12系統13,129,507行。原本 `public.v2_*` と live 13 VIEW `boat_data.*` を変えず旧収集継続。**更新・削除差分/CDC、独立復元、全writer切替・rollbackは未証明、本番切替0/13**。2026-10-24夜にcatchup前倒し00:45/01:30/02:15実機PASS。Drive書込403 STOP、原本削除禁止。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

2026-10-25 08:25 JSTのユーザーConoHa画面で13/13の`relation_shapes`・`copy_column_shape`・`pk_shape`=PASS、PK `id`/`race_id`/複合`race_id,lane`/`venue_code`、source user_triggers=0、source FK_in/out=0、複数表にserial defaultあり。`ROLLBACK`、`V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES`で正常終了。これはメタデータ一致の証拠であって差分=0/CDCではない。

2026-10-25 08:34 JST Termius実機：venues source24/stage24、read-only full outer compare INSERT=0 UPDATE=24 DELETE=0、`VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES`。更新24件は欠損24件ではない。何列が更新されたかは旧previewで未分類。

2026-10-25 08:40 JST: ConoHa Termiusでvenues source/stage各24、`VENUES_STAGE_DELTA_TRANSACTION_PASS upserted=24 deleted=0 bidirectional_equal_in_transaction=YES legacy_source_untouched=YES live_view_untouched=YES continuous_cdc=NO cutover=NO_GO BUY=OFF`、`VENUES_STAGE_ONLY_DELTA_COMMITTED_NOT_CDC_NOT_LIVE`確認。**venues stage差分反映・同一snapshot照合成功**。元public/VIEW unchanged。初回物理stage13/13、live物理切替0/13。

2026-10-25 08:46 JSTユーザーTermiusで12系統すべて `DELTA_PREVIEW_METADATA_PASS`、`PREVIEW_COMPLETE families=12 current_delta_counts=NOT_MEASURED no_table_scan=YES NO_WRITES NO_CUTOVER`。原本/ステージ列・主キー・初回コピーCOMMENT一致（12/12）。これは構造チェックで、12系統の差分適用やCDC、差分0を示さない。

2026-10-25 08:51:38 JSTユーザーのConoHa画面で `races` stage差分反映が成功。`DELTA_VERIFIED races source_rows=74064 stage_rows=74064 insert_update_delete=[168, 0, 0] bounded_windows=19`、`DELTA_TABLE_COMMITTED races`、`STAGE12_DELTA_SNAPSHOT_PASS families=1`、旧原本/VIEW不変更・BUY OFF・CDC=NOを確認。初回コピー13/13、stage差分反映2/13（venues+races）、本番物理切替0/13。

2026-10-25 09:02 JST、ユーザーのConoHa Termius画面で `PASS: STAGE11_DELTA_ONLY_SCHEDULED_NOT_YET_APPLIED`、`NEXT=Mon 2026-10-26 03:05:00 JST`、`STAGE_SCOPE=11_NO_RACES`、`LEGACY_COLLECTION=UNCHANGED LIVE_VIEW=UNCHANGED BUY=OFF CUTOVER=NO_GO` を確認。**予約は成功したが11系統の実差分同期は未実行**。初回snapshot13/13、差分同期済2/13（venues+races）、V5本番物理切替0/13。

2026-10-26 06:07 JSTのTermius画面（03:05:01–03:16:49 JST 実行ログ）で `STAGE12_DELTA_SNAPSHOT_PASS families=11 as_of_per_table_not_CDC=YES` とsystemd `Finished`、11系統各 `DELTA_VERIFIED`→`DELTA_TABLE_COMMITTED` を確認。新規追加は計44,536行（results168, entry_snapshots1938, race_condition323, racer_condition1938, racer_course_stats0, entries1008, exhibition918, weather323, racer_results0, odds_snapshots37920, trifecta_odds0）、更新/削除はいずれも0。初回物理stage13/13、差分反映13/13（venues、races＋11）、本番物理切替0/13。各表の実行時点で整合、連続CDC/最終共通時点の完全同一性を保証しない。旧collector・原本・13 VIEW不変更、BUY OFF。

**Next ONE task:** ConoHaで `deploy/conoha/v5_previous_day_core_row_parity_readonly_20261026.sql`（commit `83191a375bc2848214e9b75238f6509481665465`）を `psql` のREAD ONLYで一度実行し、JST前日(10/25)の `races`/`results`/`entries`/`racer_results` 4系統について同一トランザクション時点の行数・不足・余剰・全列内容差分を確認。**GitHubへコード登録済、ConoHa未実行**。判定は4系統限定。writer/read経路網羅と独立の現行dump復元は引き続き未証明、物理本番切替0/13、BUY OFF、既存収集は維持。
