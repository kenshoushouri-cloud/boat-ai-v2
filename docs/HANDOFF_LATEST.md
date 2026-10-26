# V5 現行引継入口（2026-10-26 17:45 JST）

**Current compact handoff:** `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`

この index → 上記 compact → `docs/NEXT_CHAT_START_HERE.md` だけを初回参照。古い長文引継ぎ・作業ログは履歴とし、必要なときだけ読む。過去のSHA・件数・容量・タイマー実行は固定せず、必要なものだけread-onlyでlive再確認。

## 最優先
- **ConoHa+GitHubでV5の安定稼働・実データ予測・2025-07以降の前向きバックテスト**。Railwayにはデータがない（ユーザー申告）、接続不要。Railway Agent/AI禁止。
- バックアップ新規構築/Google Drive認証/重複整理/削除は**運用安定後へ保留**。既存の復旧資産は残す。
- 既存collector継続、odds/展示/気象のレース前取得保護。BUY=OFF。V5 live writer切替=NO_GO。収集中の再起動/収集停止/二重起動なし。
- 10/26 17:17 JST、stage11一回限り同期タイマー `boat-v5-stage11-delta-20261027-recovery.timer` = active、予定 **2026-10-27 03:05 JST**。再予約/タイマー変更禁止。実行結果未確認。
- GitHub synthetic-only paper quality bridgeと回帰テストは登録済み（詳細はcompact）。**synthetic-only品質単体テスト18件PASS。実データ推論/ROI/バックテスト成功の証明ではない**。

## Next ONE task
10/26のVIEWスキーマ確認が終わり、純粋な実データ形状アダプタと13件のテストをGitHubへ追加した。次にConoHaで**一時フォルダー内の合成テストのみ**実行し結果を確認。10/27 03:05以降は予定済みstage11差分同期の結果をread-onlyで確認。現行writer/collector/タイマーは操作しない。
