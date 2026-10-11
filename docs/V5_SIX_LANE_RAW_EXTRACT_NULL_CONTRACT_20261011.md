# V5 大村12R・6艇生値のread-only抽出／NULL保留契約（2026-10-11）

**対象**：`20260501_24_12`、2026-05-01 大村12R。既存集計SQLは残す。新SQLは `ops/v5_oomura12_six_lane_values_readonly_20260501.sql`、検査コードは `v5/offline_six_lane_raw_extract_guard.py`、単体テストは `tests/test_v5_offline_six_lane_raw_extract_guard.py`。**これらはGitHub開発ブランチ保存済みで、今回のSQL実行・11テスト実行は未実施。** Railway Agent/AI・本番操作なし。

## なぜ既存SQLだけでは不足するか

従来の `ops/v5_one_race_six_lane_feature_lineage_readonly_20260501.sql` は `racer_number_present`、`racer_class_present` と履歴件数/日付の状態を返すため、**選手番号・級別・5走の原データを実際に6行で組み立てるには情報が足りない**。パース失敗時の `ELSE '[]'::jsonb` は「取得・パースできない」と「空の履歴」を分けにくい。元SQLは監査用に残し、改変・上書きしない。

## 提案SQLの範囲（今は実行しない）

- `public.v2_races.race_id='20260501_24_12'` の1レースのみ。1～6艇番を `generate_series(1,6)` で保持し、`v2_race_entries`、`v2_realtime_exhibition_snapshots`の同race_id・`snapshot_label='historical'`に `LEFT JOIN`。全期間走査・最終オッズ・払戻・結果の参照なし。
- 生値：`racer_number`、`racer_class`、`parsed_history`のJSON配列（最大5走という**モデル側の要件**は検査で判定）、`exhibition_time_rank`、`source`、`snapshot_at`、`source_snapshot_at_text`等の由来、対象日の`deadline_at`。SQLでは変換不能な履歴を`NULL`として残し、勝手な補完なし。
- **SQL側で `DISTINCT`/対象行`LIMIT`/ランダム代表行選択は禁止**。重複したentry/exhibitionがあれば行数が6を超え、検査で**HOLD**。欠損laneもLEFT JOINでNULLの行として残す。レース行ゼロなら空結果→HOLD。
- 実行する場合は別途インデックス/カラム型・read-only接続を確認し、ユーザーの承認のもと**必要最小限**に限定。現DB列のタイムゾーンは今回未再検証。

## オフラインNULL検査（純粋関数、今回未実行）

`inspect_six_lane_raw_extract(rows)` は以下を保持し、いずれか破れれば `HOLD_INCOMPLETE_SIX_LANE_VALUES`：

| 項目 | 許容条件・不許可 |
|---|---|
| 件数・識別 | **正確に6行**、lane1～6各1、登録番号6件すべて異なる正整数、race_id/日付が対象レースと一致 |
| 選手級別 | `A1/A2/B1/B2` の実値必須。NULLや型違いは拒否 |
| 直近成績 | `parsed_history`は配列型で1～5走。各 `race_date` が正しい日付文字列・**前日以前**。NULL/空・当日/後日の混入を拒否 |
| 展示 | 6艇の時間順位が整数1～6の順列、`exhibition_source`が非空、snapshot日時が**タイムゾーン付き**。欠損/重複は拒否 |
| 締切 | `deadline_at`がタイムゾーン付きで対象レース日と一致し、全6艇に同じ値。タイムゾーンなしなら補完せず拒否 |
| 肯定証拠フラグ | SQLの`independent_official_six_active_verified`/`original_first_observation_verified`/`forward_eligible`/`buy_eligible`はいずれも**FALSE固定**。欠損や勝手なTRUEなら拒否 |

研究用形式が揃うケースでも、後日`official_beforeinfo_historical`取得と`snapshot_at >= deadline_at`を**警告として保持**し、出力`ARCHIVED_VALUE_SHAPE_ONLY`。この場合でも `retrospective_only=True`、`official_six_active_verified=False`、`original_first_observation_verified=False`、`v5_real_roi_verified=False`、`forward_eligible=False`、`buy_eligible=False`。**完成した `ArchivedRaceFactors` や買い目・収支をこの関数は生成しない**。

## 未取得のまま保護する領域

当日以前で凍結した基本確率/5因子×6、モデルの学習上限と元証拠、実`decision_cutoff_at`、V5買い目・点数・単価、全日台帳、結果/返還の公式原本は今回の6艇SQLでは解決しない。後日の展示順位・最終オッズ・的中券 `2-1-5` を、当時購入できたV5予測に変換しない。

**Next ONE task**：GitHubの新モジュール／11テストについて、コードハッシュを照合した隔離Pythonで構文・単体テストを実行し、実際のPASS/FAILを確定。失敗時はdevだけ最小修正。DB/本番/BUYには触れない。
