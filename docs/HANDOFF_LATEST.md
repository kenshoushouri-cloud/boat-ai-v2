# V5現行引継入口（2026-10-24 19:06 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/PROJECT_HISTORY/旧長いworkflowを一括読みしない。SHA/稼働状況/件数はliveで必要な箇所だけ再取得。

最新19:45：12表empty-stage CREATE候補のREAD ONLY/ROLLBACK成功、venues保持。GitHub `deploy/conoha/v5_stage_12_bootstrap_guarded.py` に12表一括原子DDLのデフォルト`--plan`実装＋オフライン新テスト6件追加（未実行）。stage本番作成は独立外部復元未達でNO-GO、コピー/切替未実行、03:30未予約、Drive403 STOP、BUY OFF。次は6件隔離テスト＋offline plan。保存先は固定board参照。
