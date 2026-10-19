# 新チャット開始文（短縮・2026-10-19更新）

新しいチャットで以下をそのまま送信：

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。
Repository: kenshoushouri-cloud/boat-ai-v2

最初に docs/HANDOFF_LATEST.md と、そこが指定する current compact handoff **だけ**を読んでください。**直前1チャットのみ、必要な判断や実行結果について参照可能な範囲で補助参照を許可します。** 古い会話・過去handoff・PROJECT_HISTORY・長いworkflowの全文大量読み込みは禁止。正式な進捗記録は最新compact handoffです。

2026-10-19現在：TermiusのTailscale接続（Wi-Fi/4G/5G）成功。ConoHaにメイン/履歴DB・V3/V4保全済み。RailwayにはPostgres DB2+Volume2を保護して残し、cron6件を長期休止。RailwayとConoHaのread-only件数/最新日照合済みだが、全レコード包含・全表差分は未証明。10/19 12:45のConoHaメインDB新規dumpは作成・目録確認済みで、**暗号化とDrive転送は未了**。Google Drive無料15GBを当面利用し、100GB契約は開発落ち着くまで延期（未契約）。月1回自宅HDDへの手動退避を予定。

**直ちにcurrent compact末尾のNext ONE taskから、1回に1作業、所要時間目安を付けて進める。** 完了済み作業は繰り返さず、必要な情報だけlive確認。タイムアウト後の重複操作は禁止。DB/Volume削除、課金、本番変更、LINE送信、自動BUYは別途明示承認。Railway Agent/AI禁止。

目標：Railway完全撤退→ConoHa独立収集・安全な外部バックアップ→V5主力開発/実3連単収益検証（純利益+5万円/月は未実証）。自動購入は最後に別承認。
