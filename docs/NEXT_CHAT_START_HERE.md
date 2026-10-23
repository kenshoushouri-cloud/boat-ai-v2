# 新チャット貼り付け案内（2026-10-23 19:52 JST）

@GitHub

新競艇AI開発プロジェクトNo.2 続き。Repository: kenshoushouri-cloud/boat-ai-v2

最初に3点だけ：1. docs/HANDOFF_LATEST.md、2. そこが指定する最新compact handoff全文、3. docs/NEXT_CHAT_START_HERE.md。古いhandoff/PROJECT_HISTORY/長いチャットは大量参照禁止。

10/23 19:52実績（ConoHa Termius画面で確認）：
- オフライン：共有13系統8/8 PASS、venues個別7/7 PASS。
- ConoHa `railway`の新世代ローカルdump375MBを作成し、venues24行の隔離限定復元に成功。一時DB残存0。DB全体/別DB履歴復元や外部独立保全の完了ではない。
- **承認を得て`boat_data_stage.venues`を新規作成し、旧`public.v2_venues`から24行初回物理複製済み。** 19:50 COMMIT、双方向全列差分0。19:51再監査も24/24/24・差分0、19:52 read-only INSERT0/UPDATE0/DELETE0/SAME24。これは一時点の一致のみ。**stageを再作成・二重複製しないこと。**
- `boat_data.venues`は従来どおりVIEW。残り12表も同様に非更新VIEW。**本番共通物理正本への切替は0/13、初回隔離複製のみ1/13。** 現行collectorはlegacyのまま、削除・VIEW切替・writer変更・BUY・cron変更なし。
- 自動差分同期・CDC・深夜切替予約・外部独立バックアップ・全writer認証・V5実予測/ROIは未実施/HOLD。

**最新compact末尾の Next ONE task**：ConoHa旧entry原本の残りの列defaultと外部キー依存をread-onlyで確認。23:05画像で`id`のdefaultが旧`public.v2_realtime_entry_snapshots_id_seq`を参照することを確認。無修正`LIKE INCLUDING ALL`はsequence共有リスクがあるため禁止。entryの新stage CREATE/COPYは未承認。23:03画像で原本=r、共有先VIEW=v、新stage=absent、owner postgres、ROLLBACK確認済み。entry原本の21列・PK=id・UNIQUE(race_id,snapshot_label,lane)・trigger0・ROLLBACKのみ確認済み。21:52の旧6表総容量約1,133MB（odds653MB）、推定約335万行は统计値で実件数ではない。原本6表は物理、`v5_data.raw_*`6名は未作成。実コピー/切替/STOPは禁止、stage venues24行再コピー禁止、独立外部保全/全writer確認未完了につきNO-GO。

GitHubには差分計画専用Python（17件テスト定義・ConoHa隔離実行17/17 PASS）とマニフェストのstage複製済み記録を追加済み。`repair_month_all_pg.py`の`ensure_venues`は起動時24会場を`venue_id` UNIQUEキーでUPSERTし`updated_at`更新。PKは`venue_code`で両方の整合性が必要。`shared_venues_v1`は非更新VIEWに向くため有効化禁止。差分反映fail-closed専用24件は21:17実行PASS、累計8+7+17+24=56/56合成検査PASS。実DB同期/ロールバックは未実証。本番同期SQL/DML・CDCは未実装。再複製禁止。

一度に1作業、必要最小のツール、短い日本語報告。ConoHa操作が要る場合はTermiusコマンド1個ずつ、GitHub更新とDB実行を厳密に区別。低CPU/RAM/通信・無断追加課金なし、Railway Agent/AI禁止。
