# V5・Railway DB read-onlyプリフライト（2026-10-11更新）

## 現在の確定事項
- 研究用レースDB: `boat-v2-postgres / production / postgres-hobby-fullhistory-candidate-v4`。別の`postgres-history-archive`はコンディション・直近成績の保存用で、race/entries/exhibition/resultsの4表はありません。両DBを混同しない。
- ユーザーがcandidate-v4のRailway Data > Queryで実測: 当初20列中19列/索引4/権限4が適合。別の単一SELECTで`public.v2_race_entries.racer_class = int4`、`racer_class_text = text`、`racer_number = int4`と確認。文字級別として採用するのは`racer_class_text`のみ。値のA1/A2/B1/B2充足は未確認で、欠損や不正はNULL→HOLD。
- 改訂した検査SQL: `ops/v5_archive_catalog_railway_data_query_readonly_20261011.sql`（20列中の当該期待値を`racer_class_text:text/varchar`に変更）。取得元DBでこの改訂版を再実行しての`SHAPE_OK`表示は**未確認**。
- 初回1日抽出SQL: `ops/v5_one_day_archived_size_guarded_readonly.sql`。7日用: `ops/v5_seven_day_archived_research_source_readonly.sql`。両方のQ2は`e.racer_class_text`だけを`racer_class`に投影、NULLを推測補完せず、結果Q3は分離する。
- 初回1日制限: Q1<=400, Q2<=2400, Q3<=400, client復号データ<=4MB。サイズ制限はサーバ側のCPU/通信量の完全な上限を保証しない。

## 手動プリフライトの制約
Railway Data > Queryに貼るのは**GitHubで確認済みの単一SELECTだけ**。DB Variables/接続URL/パスワードをチャットへ貼らない。schema/権限変更、Index作成、全期間の大規模SELECT、Railway Agent/AI、Actions起動は禁止。

旧`ops/v5_archive_preflight_manual.py`は接続OFFが初期値で、ローカルpsqlを使う**レガシー代替経路**（history-archive向け）。candidate-v4の検証にはこのスクリプトを流用しない。新しい検査SQLの構文・プランは実PostgreSQLで未検証のため、異常時は停止する。

Data > Queryで型・索引が整合しても、公式の締切前観測、6艇の実出走、確定払戻/返還、実際のROI、Forward/BUYは別証拠。**実データ処理は0/67窓、BUYはHARD HOLD**。
