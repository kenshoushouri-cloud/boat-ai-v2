# V5現行引継入口（2026-10-25 朝・実コピー完了）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`のみ。旧資料は履歴扱い、SHA・件数・タイマー実状態は必要時live確認。

**現況（10/25 08:16 JSTユーザーのConoHa journal画面）:** 10/25 02:50:09〜02:53:42に未コピー12系統全て `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。既存venues 24件と併せて `boat_data_stage` **初回物理snapshot 13/13**。12系統行数合計13,129,507、コピー時の各transaction rowcount一致。**初回snapshotだけ・最終delta/CDC・本番writer/read切替未実施、live physical 0/13**。旧collector/13 VIEW維持、BUY OFF。10/24夜にcatchup時刻前倒し00:45/01:30/02:15が実機PASS。独立VPS外restore未証明、Drive書込403 STOP、Railway費用最小。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

**Next ONE task:** ConoHaで `deploy/conoha/v5_stage13_delta_readiness_catalog_readonly_20261025.sql`（commit `be3e5e0db2395ba19f29d5e00c1153bd13180578`）を一度read-only実行。13系統の原表/物理stage/VIEWの型、全列順・型、PK形、FK/trigger/default hazardを13行で確認する。snapshot再コピーはせず、COPY後の追加/更新/削除差分同期を設計/検証。**V5物理本番切替・BUYは禁止**。
