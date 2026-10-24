# V5現行引継入口（2026-10-24 19:06 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/PROJECT_HISTORY/旧長いworkflowを一括読みしない。SHA/稼働状況/件数はliveで必要な箇所だけ再取得。

最新19:38：GitHub psql fallbackの4/4テストPASS＋`railway` READ ONLYで12原表r/12移行先ABSENTを確認。venues既存stage1/13、live0/13。新`deploy/conoha/v5_stage_12_bootstrap_plan_readonly_20261024.sql`（空stage DDL案のみ/未実行）。次はSQLによる12表schema/PK/default/DDL候補のread-only確認。独立復元未完了、03:30未予約、Drive403 STOP、BUY OFF。保存先は固定管理ボード参照。
