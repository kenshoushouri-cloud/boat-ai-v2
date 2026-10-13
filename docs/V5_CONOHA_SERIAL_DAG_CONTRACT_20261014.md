# ConoHa 2GB / V5 直列DAG — 安全な実行契約（2026-10-14）

**状態：計画・オフラインテストのみ。ConoHa / Railway / 本番 / GitHub Actionsには接続・実行していない。**

- 実装: `ops/conoha/v5_offline_dag.py`。Python標準ライブラリのみ、`--race-date YYYY-MM-DD` 必須。デフォルトはプランを表示するだけで、ジョブ・DB・ネットワーク・秘密変数に一切触れない。`--format json`は監査用。実行可能なDAG/schedulerでは**ない**。
- テスト: `ops/conoha/test_v5_offline_dag.py`。独立したローカルLinux/Pythonで**20/20 PASS**。失敗した初期の並べ替え順序を修正してから再実行。GitHubの2ファイルのblob SHAはローカルテスト済ファイルと一致。**実機試験、過去67週バックテスト、ROI検証はしていない**。

## 論理的な順序
1. `roster_prepare` — 出走表と選手/モーター情報の準備。未取得は再試行してもよいが、締切を越えて当時の予想資料にしない。
2. `beforeinfo_capture` と `odds_capture` — 展示・気象などの直前情報と公式オッズを**別段階で収集**。実際はレース単位の締切/公開時刻を確認し、収集の最終時刻を守る。順番の固定だけで遅延させないこと。
3. `evidence_gate` — 出走表、直前情報、オッズの完全性、締切前撮影時刻と**撮影/凍結の真正な証拠**を確認。いずれか欠けたら**予測見送り（NO_PREDICTION）**。過去日の再取得・日付だけ一致する情報を締切前のForward証拠としない。
4. `v5_shadow_predict` — 現状は**disabled**、将来も初期はshadow限定。BUY HARD HOLD（V4の購買処理を流用しない）。
5. `result_capture` — **競走後**の公式確定結果は予測と独立して取得。欠測/NO_PREDICTIONでも結果収集を止めない。
6. `result_audit` — 結果・返還・未確定・取り消し・欠測を保持し、母数から勝手に除外しない。
7. `weekly_backtest` — 必要データ保全・照合後の**手動のみ**。2025-07-01以降、事前情報の証明不十分な期間はForward実績と区別。67週の実行は未着手（0/67）。

## 直列化・リトライ契約（将来の実装で必須）
- `ops/conoha/v5_serial_resource_guard.sh`をすべての**書込ジョブ**に共通のロックで通す。独立cron/手動起動がガードを迂回できない仕組み（専用ユーザー・systemd・権限/DB側一意制約）が必要。現在は**未結線**。
- 再試行はレース単位の時刻窓内・回数と間隔に上限。時刻窓を越えたらmissingを残し、再試行しても過去の締切前snapshotを作らない。結果取得は公式確定まで別ポリシーで再試行。
- 重複は `(race_id, deadline_at, stage, snapshot_version)` を論理キーにし、**凍結済みsnapshotは書換え禁止**。`ON CONFLICT DO NOTHING` 等のDBの一意制約は将来の対象DBスキーマを確認してから設計。途中失敗は何を更新できたか検査し、盲目的に同一writeを繰り返さない。
- RAM閾値と最大ジョブ時間は**暫定**。実機メモリ/ディスク/WAL/CPUを診断・実測後に調整。バックテストとリアルタイム収集を同時実行しない。
- `run_final_pg.py`は既存V4/v25系経路なので、**V5本番の自動起動先として安易に指定しない**。`TEST_MODE=1`等は購入機能OFFの代替安全証明にならない。

## 移行/バックアップとの関係
- 先に旧V3/履歴archive/V4/V5の**暗号化外部コピーと独立復元**。ConoHaの管理画面問題が解決するまで、接続/デプロイ/DB移設なし。Railway本番と元4DB、復元鍵、旧CMS artifactを保持。
- 次 ONE task は`ops/backup/test_railway_pg_to_drive_stream_offline.sh`の**作成済み14ケースを非課金・ローカルLinuxで実行し、必要なら安全なガードだけ修正**。実DBアクセス/課金/Secrets/Keys/BUYは禁止。
