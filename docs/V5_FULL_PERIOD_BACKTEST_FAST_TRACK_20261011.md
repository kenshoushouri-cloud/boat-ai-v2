# V5主力・全期間研究バックテスト短期完成ルート（2026-10-11）

**目的**：個別1レースの安全性監査を繰り返すのでなく、2025-07-01以降の全対象レースを保持してV5の仮想3連単券・見送り・返還・収支を一括研究評価する。実BUY/実ROI/締切前原本の証明とは**別系統**。V4/mainは不変更。Railway費用$10〜12理想、$15未満優先、$20上限。

## 今回完成したオフライン接続
- `v5/offline_research_period_batches.py`：`plan_research_period(start,end,7)`で連続日を最大7日ずつの区間に分割。`rollup_research_period`は既存の`WholeDayResearchLedger`を日付順に突合せ、未処理日、NO_BUY、PENDING、VOID/返還情報不明を保持。
- **2025-07-01〜2026-10-10** は467暦日・67窓（最後5日）。これは**処理計画だけ**で、DB全期間処理完了ではない。旧固定評価期間の2026-10-05までと、10-06〜10-10の追加評価は表示上区別する。
- 無選定（0券）・日付欠損・未解決結果・PENDINGを全期間の母集団から消さず、期間ROIをnullにする。全件が届いても算出できるのは `hypothetical_roi_pct` だけ。実V5回収率・実的中実績には昇格しない。
- `tests/test_v5_offline_research_period_batches.py`新規9件＋既存`tests/test_v5_offline_whole_day_research_ledger.py`9件＝**18/18隔離Python PASS**。GitHub blob一致：実装`ee392987`、テスト`43fc4a97`。合成データのみ。

## 次の実務ステップ（優先順）
1. **複数日・read-only保存値入口**：DBのテーブル/列/インデックスを1回限定で確認し、既存データから7日単位でrace ID・entry×6・直近成績・展示・公式結果/払戻/返還を抽出する**読み取り専用・上限付き**の入力契約を作る。初回は少数行smoke、次に複数日。RailwayのCPU/通信/課金を監視し、負荷を上げない。
2. **前日までの学習状態を時系列に再構築**：2025-07-01からの日付境界・学習ウォームアップを明記、当日/未来の結果はその日の予測に流さない。事後展示・最終オッズの情報は別ラベル。欠損行・取得時刻未認証は無理に補完しない。
3. **事前規則に基づく券と収支のバッチ結合**：モデル/券数・金額・日次0〜3候補の評価基準を**結果参照前**に固定、結果で買い目を選ばない。日ごとにNO_BUY/PENDINGを出力。返還欄不明は保留。古いV4券規則の流用禁止。
4. **全期間集計→品質評価→過去データ保存検討**：日次のカバレッジ、適中、仮想収支、データ欠損理由とリーク警告を併記。価格感度分析と真正なForward成績は別表。バックテスト後にのみ安全な保存/容量整理を判断。

**現在の阻害要因**：既存PostgreSQL保存値→汎用7日`ArchivedRaceFactors`/結果への接続は未完成。大村12R専用のone-race SQL/guardを467日に単純再実行しない。公式6艇肯定出走・初取得原本・V5実収益・BUY適格性はHARD HOLD。

**Next ONE task**：DBをまだ起動せず、既存スキーマ/クエリから7日一括の**read-only source adapter最小SQL**と欠損/返還null契約をdevに作成。最初の実DB smokeはSQL/索引/コストを確認後に別途判断。


## 2026-10-11：七日一括のread-only保存値入口設計完了（DB未実行）

追加SQL：`ops/v5_seven_day_archived_research_source_readonly.sql`。**Q1全race inventory / Q2艇番1〜6+直近成績+historical展示 / Q3事後result/3連単払戻**を独立SELECTに分離。アプリから`start_date`・`end_exclusive`をバインドし、1〜7日・2025-07-01以降・JST基準の完了日のみ。3SELECTとも日付範囲制限あり、書込命令なしを**静的検査**。PostgreSQLパーサ/実DBの検証は未実施。

- Q2はLEFT JOINして欠損艇番をNULLとして残し、`DISTINCT`/代表行抽出をせず重複はオフラインHOLD。Q3も全inventory LEFT JOIN、欠損結果・重複結果は後段でPENDING/HOLD。結果・払戻は**予測用Q2に混ぜない**。
- 公式返還欄の原本未確認のため`refund_boats=NULL`、`refund_section_verified=false`、`whole_race_void_verified=false`固定。`NULL`を「返還なし」に変換しない。DBの`official`文字列や保存払戻だけでは実ROIは出せない。
- **稼働前の必須条件**：現DB read-only接続/権限、`pg_indexes`で`v2_races(race_date)`・`v2_race_entries(race_id,lane)`・展示`(race_id,snapshot_label,lane)`・`v2_results(race_id)`の索引実態、必要カラム/型、1日分の想定行数とpayload、`statement_timeout`・件数/通信量上限をチェック。展示複合indexはGitHubにCREATE定義があるが、**現DBで実在は未確認**。索引不足なら停止。重複検出のためSQLの結果`LIMIT`で行を隠さない。
- 初回実データsmokeは**1日のみ・1回read-only**、索引/コスト確認後。問題なければ7日窓に拡張。学習Counterは**各日予測後**にその日の結果で更新し、7日結果を先に学習させない。
