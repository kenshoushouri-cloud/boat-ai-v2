# V5現行引継入口（2026-10-25 朝・実コピー完了）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`のみ。旧資料は履歴扱い、SHA・件数・タイマー実状態は必要時live確認。

**現況（10/25 08:16 JSTユーザーのConoHa journal画面）:** 10/25 02:50:09〜02:53:42に未コピー12系統全て `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。既存venues 24件と併せて `boat_data_stage` **初回物理snapshot 13/13**。12系統行数合計13,129,507、コピー時の各transaction rowcount一致。**初回snapshotだけ・最終delta/CDC・本番writer/read切替未実施、live physical 0/13**。旧collector/13 VIEW維持、BUY OFF。10/24夜にcatchup時刻前倒し00:45/01:30/02:15が実機PASS。独立VPS外restore未証明、Drive書込403 STOP、Railway費用最小。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

2026-10-25 08:25 JSTのユーザーConoHa画面で13/13の`relation_shapes`・`copy_column_shape`・`pk_shape`=PASS、PK `id`/`race_id`/複合`race_id,lane`/`venue_code`、source user_triggers=0、source FK_in/out=0、複数表にserial defaultあり。`ROLLBACK`、`V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES`で正常終了。これはメタデータ一致の証拠であって差分=0/CDCではない。

**2026-10-25 08:34 JST実機確認:** venues限定read-only差分PREVIEW成功。source=24/stage=24、INSERT=0、UPDATE=24、DELETE=0、`VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES`。24は削除や欠損ではなく行内容差。まだ実反映なし。旧収集・13 VIEW・BUY変更なし。13系統の物理初回copy13/13とPK/型一致13/13を維持。

**Next ONE task:** venues差分の24更新が`updated_at`のみか他列も変わったか、負荷ごく小さいread-only分類を同runnerで確認し、stage-only applyゲートへ。次いで残12系統のCDC(INSERT/UPDATE/DELETE)差分追従。独立復元/全writer/reader証明なしでは物理本番切替NO-GO。