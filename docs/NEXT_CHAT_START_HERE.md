# 新チャット最小起点 — 新競艇AI開発No.2（2026-10-25）

@GitHub
@Railway

repo `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md`→指定compact→本書だけ。古いhandoffと長いworkflowは大量参照せず、1作業ずつ短いlive取得。

**目的:** V5主力、2025-07以降の精度/真ROI検証、紙上非購入を早期稼働。ConoHa主・Railway費用最低限（$15–20/月を下回るほど良い）、Railway Agent/AI禁止。BUY OFF。

**最新の実データ状態（10/25 08:16 JSTユーザーConoHa journal）:** 12系統ステージ初回物理snapshotが10/25 02:53:42 JSTに全件 `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。先行会場24行と合わせ `boat_data_stage` **13/13初回コピー済**。12系統13,129,507行。原本 `public.v2_*` と live 13 VIEW `boat_data.*` を変えず旧収集継続。**更新・削除差分/CDC、独立復元、全writer切替・rollbackは未証明、本番切替0/13**。2026-10-24夜にcatchup前倒し00:45/01:30/02:15実機PASS。Drive書込403 STOP、原本削除禁止。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

2026-10-25 08:25 JSTのユーザーConoHa画面で13/13の`relation_shapes`・`copy_column_shape`・`pk_shape`=PASS、PK `id`/`race_id`/複合`race_id,lane`/`venue_code`、source user_triggers=0、source FK_in/out=0、複数表にserial defaultあり。`ROLLBACK`、`V5_STAGE13_DELTA_CATALOG_READONLY_DONE_NO_TABLE_SCAN_NO_WRITES`で正常終了。これはメタデータ一致の証拠であって差分=0/CDCではない。

**Next ONE task:** 24行の`venues`限定stage差分runner `deploy/conoha/v5_stage_delta_venues_guarded_20261025.py`（commit `39c17fa530d06e33b8ac1ea695e2a25cce32bee3`）をTermiusで`--apply`なしPREVIEW実行、実schemaとPK・源/先24行・trigger/FKを確認する。GitHub追加のみで未実機実行・未テスト。実stage APPLYは別承認＆03:00–05:59 JSTゲート、対象表以外や原本/VIEWは変更しない。pilot後13系統upsert/delete全差分と独立復元を準備。BUY OFF、writer/read route本番切替NO-GO。
