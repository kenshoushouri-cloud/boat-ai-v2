# V5現行引継入口（2026-10-24 19:06 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261024_1906_COMPACT.md`

新チャットは本ファイル→current compact→`docs/NEXT_CHAT_START_HERE.md`だけ読む。古いhandoff/PROJECT_HISTORY/旧長いworkflowを一括読みしない。SHA/稼働状況/件数はliveで必要な箇所だけ再取得。

19:06 Termius 6/6 PASS、合成検査累計29/29 PASS（旧stage route）。これを受けGitHubコードのstage先を**既存`boat_data_stage`に統一**し、default READ ONLY・12表一括preview・別ゲート式単表COPY実行器を追加。**最新版の合成テストと実DBプレビューはまだ未実行。** 今の段階で物理移行を実行していない（stage1/13, live0/13 NO-GO）。03:30自動切替未予約、Drive書込403 STOP、BUY OFF。保存先固定`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`。Next ONE taskはcompact末尾参照。
