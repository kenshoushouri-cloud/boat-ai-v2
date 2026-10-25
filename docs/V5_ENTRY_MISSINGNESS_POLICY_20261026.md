# V5 欠損13項目と実力評価の分離 (2026-10-26)

## 運用判断
高評価の選手が一部の項目で公式未集計でも、**実力評価を下げず**、予測入力の信頼度だけを別に扱う。13項目すべてが常に必須ではない。未集計を0に置き換えない。予測用の欠損代替値・信頼度補正の大きさは未確定で、2025-07以降の前向き時点に沿ったバックテストで測定する。

- **COMPLETE_STATS_RESEARCH_ONLY**：13項目の形・数値範囲に問題なし。非購入モデル研究の候補。ただし「入力品質OK」は正式な予測/ROI検証済みを意味しない。
- **OFFICIAL_UNREPORTED_RESEARCH_ONLY**：公式出走表から未集計を証明した項目だけNULLを認め、既存の高い実力スコアはそのまま保持。欠測を扱えるモデルの研究候補に残す。
- **UNVERIFIED_MISSING_HOLD**：DBのNULLだけでは公式未集計か解析失敗か分からない。予測投入保留。証拠取得後に再分類。
- **PARSER_FAILURE_HOLD / ALL_STATS_MISSING_HOLD**：現行 `ENTRY_STATS_PARSE_FAILED` や一括13項目NULLはデータ品質障害として保留。存在する艇の能力が低いと評価してはならない。
- **INVALID_OR_CONFLICTING_INPUT_HOLD**：数値範囲/根拠と値の矛盾/識別子異常を保留。6艇構成や重複登録番号もレース単位でHOLD。

## 実装
- `v5/entry_quality_policy.py`：pure関数 `inspect_lane`, `inspect_race`。高評価値をそのまま引き継ぎ、判断は別の `LaneQuality` として出す。全て `buy_eligible=False` の安全既定。公式未集計には**信頼できる現物の根拠**を要し、SQLのNULLだけで `OFFICIAL_UNREPORTED` にしない。
- `tests/test_v5_entry_quality_policy.py`：高評価維持、公式未集計、無根拠NULL、一括NULL、パーサ警告、数値範囲、6艇整合、購入OFFの回帰テスト（syntheticのみ）。
- これらは **GitHubに追加したモジュールとテストの段階**。ConoHaの稼働中collectorや5分shadow watcherは未変更、実DBに展開・接続していない。新しいV5本番予測モデルの稼働を証明しない。

## 残る作業
1. `boat-v5-daily@morning.service` の 288/288 完走とfailed確認（07:32は200/288, 108 success, 92 no_race, 0 failed）。
2. 丸亀(15)の8艇を1レース最小限のread-only HTML診断で「公式未集計」と「解析器不一致」に区分。13項目一括NULL化の修正は**解析根拠を確認後**に限定し、収集中の本番スクリプトは差替えない。
3. 13項目の出所を保存可能なデータ契約にしてからREAD ONLY paper scoringへつなぐ。選手実力の高低と欠測を混同しない。未検証の補完・後日成績混入を防ぐ。
4. V5の正式writer切替は当日バックアップの独立復元・全writer経路・最終差分検証が済むまでNO-GO。BUY OFF、旧収集継続。
