# V5現行引継入口（2026-10-25 朝・実コピー完了）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_NIGHT_WINDOW_COMPACT.md`

新チャットは本書→current compact→`docs/NEXT_CHAT_START_HERE.md`のみ。旧資料は履歴扱い、SHA・件数・タイマー実状態は必要時live確認。

**現況（10/25 08:16 JSTユーザーのConoHa journal画面）:** 10/25 02:50:09〜02:53:42に未コピー12系統全て `COPY_COMMITTED`、`STAGE12_INITIAL_COPY_PASS families=12 of_12`、systemd正常終了。既存venues 24件と併せて `boat_data_stage` **初回物理snapshot 13/13**。12系統行数合計13,129,507、コピー時の各transaction rowcount一致。**初回snapshotだけ・最終delta/CDC・本番writer/read切替未実施、live physical 0/13**。旧collector/13 VIEW維持、BUY OFF。10/24夜にcatchup時刻前倒し00:45/01:30/02:15が実機PASS。独立VPS外restore未証明、Drive書込403 STOP、Railway費用最小。

**Next ONE task:** ConoHaで `deploy/conoha/v5_stage_13_snapshot_proof_readonly_20261025.sql` のread-only PG catalog監査を1度実施し、13原本が物理表、13 live `boat_data` がVIEW、13 stageが物理表、今回の12表の完了commentが存在することを確認する。12表COPY済なので再実行・再コピーはしない。次にUPDATE/DELETE含む差分同期・独立復元・writer/readerルート・自動rollbackを完成させ、別途全gate PASS時のみ切替。旧収集維持、BUY OFF。
