# 新チャット最小起点 — 新競艇AI開発No.2（2026-10-25）

@GitHub
@Railway

repo `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md`→指定compact→本書だけ。古いhandoffと長いworkflowは大量参照せず、1作業ずつ短いlive取得。

**目的:** V5主力、2025-07以降の精度/真ROI検証、紙上非購入を早期稼働。ConoHa主・Railway費用最低限（$15–20/月を下回るほど良い）、Railway Agent/AI禁止。BUY OFF。

**最新の実データ状態（10/25 08:16 JSTユーザーConoHa journal）:** 12系統ステージ初回物理snapshotが10/25 02:53:42 JSTに全件 `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。先行会場24行と合わせ `boat_data_stage` **13/13初回コピー済**。12系統13,129,507行。原本 `public.v2_*` と live 13 VIEW `boat_data.*` を変えず旧収集継続。**更新・削除差分/CDC、独立復元、全writer切替・rollbackは未証明、本番切替0/13**。2026-10-24夜にcatchup前倒し00:45/01:30/02:15実機PASS。Drive書込403 STOP、原本削除禁止。

2026-10-25 08:21 JSTユーザーTermiusのPGカタログread-only検査にて13 rows、13原本=r、13既存live=VIEW(v)、13 stage=r、12表が`INITIAL_SNAPSHOT_COMMITTED`、venues=`PREVIOUS_VENUES_STAGE_PRESENT`、`ROLLBACK`と`V5_STAGE13_CATALOG_AUDIT_DONE_READ_ONLY_NO_CDC_NO_CUTOVER`を確認。初回物理snapshot13/13証明、現在差分・hash parity・CDC・独立復元・本番切替は未証明（live0/13）。

**Next ONE task:** ConoHaで `deploy/conoha/v5_stage13_delta_readiness_catalog_readonly_20261025.sql`（commit `be3e5e0db2395ba19f29d5e00c1153bd13180578`）を一度read-only実行。13系統の原表/物理stage/VIEWの型、全列順・型、PK形、FK/trigger/default hazardを13行で確認する。snapshot再コピーはせず、COPY後の追加/更新/削除差分同期を設計/検証。**V5物理本番切替・BUYは禁止**。
