# V5 新チャット開始（2026-10-26）

GitHub repository: `kenshoushouri-cloud/boat-ai-v2`。

1. `docs/HANDOFF_LATEST.md` を読む。
2. 指定された current compact handoff を一度だけ全文読む。
3. そこでの `Next ONE task` を優先する。古い handoff や長い workflow を大量参照しない。

**現在のユーザー方針:** ConoHa＋GitHubでV5安定稼働・非購入paper→実データモデル→2025-07以降の前向きバックテストを優先。Railwayはデータなしのため不要、バックアップの新規整備は運用安定後へ保留。既存backup削除禁止。既存collector/変動odds/展示/気象の取得保護、BUY OFF、writer切替NO_GO、サーバー再起動や重複収集なし。

10/26 17:17 JST、10/27 03:05 JST実行予定のstage11物理差分同期の`recovery.timer`がactiveだった。**同期成功は未確認**。予約をいじらず10/27 03:05以降の実行ログのみread-only確認。

GitHub-onlyに合成paper quality bridge+testsを追加したがテスト未実行・実予測未達。SHA・実データ件数等は必要なものだけlive取得。
