# V5現行引継入口（2026-10-24 19:06 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/PROJECT_HISTORY/旧長いworkflowを一括読みしない。SHA/稼働状況/件数はliveで必要な箇所だけ再取得。

最新20:13：12空stageの原子CREATE+ROLLBACKリハーサルPASS、永続テーブル0。GitHub `deploy/conoha/v5_stage_backup_capacity_gate_readonly_20261024.sh`を追加（2既存dump整合/WAL/容量のread-only監査、未実行）。外部独立復元未確認につき永続DDL・COPY・03:30切替NO-GO。stage1/13・live0/13、Drive403 STOP、BUY OFF。詳しくはcurrent compact末尾。
