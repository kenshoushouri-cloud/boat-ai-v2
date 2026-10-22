# V5 実データ予想・共通保存先：次回作業優先順位（2026-10-23）
状態: **GitHub作業のみ / ConoHaは変更していない**。目的は10月末までに非購入のV5試験運用を優先しつつ、未来情報漏洩と取得停止を防ぐこと。

## この時点で現物確認済み
- 2026-10-23 00:43 Termiusユーザー画面により、`boat_data` schema配下に共通参照 **13個の非更新VIEW**、`unexpectedly_updatable=0`、`COMMIT`、`BOAT_SHARED_THIRTEEN_LIVE_SOURCE_VIEWS_READY_NO_DATA_COPIED_NO_WRITERS_CHANGED` を確認。
- これらは既存`public.v2_*`のデータをその場で参照する。**物理テーブル移動/コピー完了ではない**。旧収集サービス/DB writerは従来のまま。別履歴DBもそのまま。
- 2026-10-23 00:03の収集4 timerはactive/enabled。次は01:20結果追補と07:00 morning/forward。過去の時刻は参照値であり次回実行の生存確認ではない。
- 既存`v5.offline_mainline_inference`は研究用 **合成入力の1着確率**を出すだけで、実際の出走6人/締切前の原本認証/3連単の買目予想・回収率を証明しない。BUY/本番切替はHARD HOLD。
- `v5_data.venues`に24件ステージ、原本差異ゼロ。共通`boat_data.venues`は現在 **VIEW** なので、`V5_DAILY_WRITE_ROUTE_PROFILE=shared_venues_v1`を有効にしないこと。

## 重複・競合を防ぐ
- `deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh`および`boat_shared_bulk_stage_20261023.py --apply`を**実行しない**。既に13個の同名VIEWが存在し、物理COPYターゲットと競合する。過去に02:00タイマーが予約されていれば、実行結果をread-onlyで照会してから次を判断する。
- 大量COPYを使わずに共有先の物理正本へ移すときは、現在の全writer/reader/systemd/依存をまず台帳化し、`ALTER TABLE SET SCHEMA`や同等の一括名前切替を安全な停止窓で行う。非更新VIEWと同名の実表を同時に置けないので先に依存/rollbackを設計。旧表DROPは最後。公開サイトの遡及データを締切前取得証明として使わない。
- 10/19 backup単独ではその後の当日展示・オッズ原本を復元できない可能性があり、外部保存/復元試験前の破棄は禁止。

## 次の ONE task（作業再開が23:00以降の場合）
Termiusで次の **DB catalog read-only** を実行する。DB本体3GBのCOUNT走査はせず、13の参照元依存/非更新性/共通schemaの物理テーブル状態を一括検査。
```bash
git -C /opt/boat-ai-v5 pull --ff-only &&
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -d railway -f /opt/boat-ai-v5/deploy/conoha/v5_shared_views_cutover_readiness_readonly_20261023.sql
```
成功予定の末尾：`V5_SHARED_VIEWS_READONLY_GATE_PASS_NOT_PHYSICAL_NOT_ENGINE_CUTOVER`。未実行・失敗は完了としない。

## ゲート通過後に進める内容（順番）
1. **実データで非購入試験**：出走6人・選手/モーター/直近5走・展示・風/水面・公式Kの時点根拠の有無をレースID単位で表示し、不足ならSKIP。正しい配当や結果情報は予想計算から除外。
2. **V5予測出力**：現行オフライン合成計算と、本当の原本に紐づくV5スコア/3連単順位・賭金の処理を分離。現時点では前者だけが存在を確認できる。後者は作成・検証が必要。
3. **2025-07以降の欠損確認・バックテスト**：出走/結果、選手/モーター/当地成績、過去の展示・オッズの収集時刻を区別し、事後取得を先読み入力に混ぜない。全数100%を待たず、対象レースの不足は明示してスキップ。ROIは元オッズ/意思決定凍結/結果/返還照合が必要。
4. **共通物理ストレージの移行**：先にwriter/reader/期限時点証拠/復元確認を済ませる。サービスを止めるのは個別の短時間停止窓の時のみ。旧表削除を自動化しない。
5. 費用増ゼロ優先、ConoHa集中、Railway Hobby解約済（11/03終了）、LINE送信やBUYの新規認可なし。

この計画は期限や完成を保証しない。作業の真偽はTermiusの実ログで再確認する。

## 2026-10-23 06:45 — 13/13 shared-view PASSとV5実入力スモークの準備
- ユーザーTermius 06:45画面：`SHARED_VIEWS_VERIFIED=13 NON_UPDATABLE=13 SOURCE_DEPENDENCIES=13`、relation types v=13、COMMIT、`V5_SHARED_VIEWS_READONLY_GATE_PASS_NOT_PHYSICAL_NOT_ENGINE_CUTOVER`。このgateは**完了**、再実行不要。
- 新SQL `deploy/conoha/v5_live_prediction_inputs_sample_readonly_20261023.sql`：当日JSTで締切前の最大6レースについて、実`boat_data.races/entries/exhibition_snapshots/odds_snapshots` から登録6艇、選手番号/級/モーター/ボート/直近成績の形、同一ラベルの締切前展示6艇、3連単120オッズを読む。**見かけの保存時刻だけでは当時の凍結証拠ではない**。結果/払戻/賭金は参照しない。HOLD原因の一覧表示だけで、予想処理やBUYは起動しない。
- **Next ONE task (ConoHa termius, morning/forward collector起動が終了してから)**: `git -C /opt/boat-ai-v5 pull --ff-only && runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -d railway -f /opt/boat-ai-v5/deploy/conoha/v5_live_prediction_inputs_sample_readonly_20261023.sql`。完了マーカー `V5_LIVE_INPUT_SAMPLE_READONLY_DONE_NO_FORECAST_NO_BUY`。当日開催データがなければ0 rowsでも正常終了、欠損があれば補完/開発の判断材料。最大6レース限定、read-only。実行結果は未確認。
- 目標は次にモデル用「実データの因子ベクトル」のas-of evidenceと予想出力を整備することであり、6艇と120票の存在だけでは予想・収益率の保証にならない。V5本番切替、物理データ移動、旧表DROPはこのSQLで許可されない。
