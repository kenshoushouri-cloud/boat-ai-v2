# V5現行引継入口（2026-10-24）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_OFFSITE_RECOVERY_COMPACT.md`

新チャットは本ファイル→現行compact→`docs/NEXT_CHAT_START_HERE.md`だけを読む。過去handoffは履歴扱い。トーク容量削減のため、旧ログ・大きなworkflowを一括参照しない。

現況：ConoHaの2 DBローカルdump SHA/bytes/TOC 21:11 PASS、空き67717MB。外部Google Driveに10/19暗号化V5世代が存在（復号・独立復元・現在世代は未検証）。原本13、VIEW13、物理stage venues1/13、live切替0/13 NO-GO。Drive新書込403 STOP、BUY OFF、夜間03:30自動切替未予約。

22:07に暗号化バックアップ合成テスト8/8 PASS（実復号・復元未実施）。最優先は既存VIEWからのV5 read-only研究・バックテストを開始し、日中にstage複製、夜間03:30候補でshadow読取を最終差分後に切替する設計。**原本writerは停止せず並行収集。夜間タイマー未予約。** 現況はcurrent compact末尾参照。
