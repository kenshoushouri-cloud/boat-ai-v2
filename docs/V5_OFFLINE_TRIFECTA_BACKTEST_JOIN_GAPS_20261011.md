# V5 研究用3連単バックテスト接続点の限定監査（2026-10-11）

**状態：GitHub実装のread-only確認のみ。実DBのバックテスト・実利益/実ROI・締切前購入可能性は未検証。** V5が主力。2025-07-01以降の履歴を対象候補とし、後日データは **retrospective payout scenario** のみに使う。V4/Production・Railway・DB・BUY不変更。

## 既存の純粋関数経路（連結は合成テストで確認済み、実DB接続はなし）

| 段階 | 既存ファイル / 関数 | 必須データ / 判定 |
| --- | --- | --- |
| 1. 前日までの学習 + 6艇特徴 | `v5/offline_archived_six_lane_bridge.py:build_archived_rank` | `ArchivedRaceFactors`：race_id、タイムゾーン付 `decision_cutoff_at/deadline_at`、**対象レース日前**`model_fitted_through`、6艇lane/racer_number/class、各艇1～5件 `recent_form`（前日以前）、展示順位1～6とソース/保存時刻、前日までの基本確率・5特徴量ベクトル、**明示**ticket_count=1～120、stake_per_ticket_yen=100円単位 |
| 2. 1着から3連単確率へ | `v5/offline_trifecta_shadow_ranking.py:rank_offline_v5_trifectas` | Plackett–Luce仮定で120券の確率を作り、確率降順の上位N券を選ぶ。**2・3着の確率校正は未確認**。結果・最終オッズを予測入力に使わない |
| 3. 仮想券固定 | `v5/offline_retrospective_result_adapter.py:FrozenResearchRank` | `ranking`, cutoff, deadline, `materialized_at`（展示履歴の後日保存日時）, stake。後日生成した券は **`RETROSPECTIVE_ARCHIVE_NOT_ASOF`** として残す。数値上cutoff前でも独立原本確認なしなら真の意思決定と呼ばない |
| 4. 結果との結合 | `join_ranked_v5_scenarios(frozen_cases, result_rows)` | `StoredResultRow`: race_id, result_status, race_status, winning_ticket, **payout_per_100_yen**, refund_boats, refund_section_verified, whole_race_void_verified。結果が未紐付け/証拠不明ならPENDING・元の候補群を削除しない。1回のbatchは1～500候補 |
| 5. 仮想収支 | `v5/offline_retrospective_trifecta_returns.py:evaluate_fixed_retrospective_returns` | 返還済み艇を含む券は購入金額返還、VOID全額返還、正式配当は `payout_per_100_yen` を使用。公式結果でも返還欄未確認は `REFUND_MAPPING_UNVERIFIED`。全件が解決するまで **hypothetical_net_yen / hypothetical_roi_pct = None** |

### 検索・テストで確認した範囲

- GitHubコード検索では `build_archived_rank` と `join_ranked_v5_scenarios` の具体的な呼出しは、該当モジュールと **合成データ単体テスト** `tests/test_v5_offline_archived_six_lane_bridge.py` 等に限定。**DBの保存値から両dataclassへの実連結は見つからなかった**。GitHub検索は現在の索引範囲の確認であり、別経路の不存在までは証明しない。
- この経路は `v2_odds_trifecta` の120件価格を**直接読まない**。収支は**公式3連単100円当たり払戻**ベースであり、`closing-price EV` や実購入時点のオッズ再現とは区別する。以前の大村12R保存オッズ61.8倍と配当6,180円の数値一致は1件の事後整合にすぎない。
- `join_ranked_v5_scenarios` は **1～120券を持つ候補レースだけ**を受け、`FixedSelection` も券0件を拒否。別実装 `v5/offline_frozen_day_evidence_adapter.py` の全レース `FROZEN/NO_BUY/PENDING` 台帳とは**未結合**。選定しなかったレースをバックテスト母集団から消すと選定率・日次0～3レース方針を誤表示するので、別台帳との一対一照合が必要。
- 明示購入点数・単価・しきい値は未決定。**V4の2点×100円をデフォルト転用禁止**。後日結果から当たり券を選定したことにしない。

## 現在の主要未接続点（推奨順）

1. **日付・全レース台帳**：既存 `FrozenDay` / NO_BUY / PENDING 台帳に、研究用 `ArchivedRaceFactors` 生成成功・HOLD・券固定レコードを全件紐付ける。結果側の条件でレースを捨てない。
2. **オフライン入力組立**：保存 `v2_races`/ `v2_race_entries`/ `v2_realtime_exhibition_snapshots` と、対象日前で固定したCounterベクトルから `ArchivedRaceFactors` を作る **read-only** アダプターと監査レポートが必要。後日展示は**研究用再構築**として扱い、cutoff前の本当のfirst_observedと混同しない。
3. **結果・返還アダプター**：`v2_results`、公式Kの事故/F/L/VOID・返還原本を `StoredResultRow` に変換する工程が未結合。**refund_boats=None→()禁止**、未確認はPENDINGのまま。元研究の事故による学習対象除外を、購入収支の分母に流用しない。
4. **日次上限・最終モデル選定**：1日0～3レースの選択条件、買い目点数・単価、しきい値・期待値仮説を**結果参照前**に固定。現PLは確率順位のみでオッズEVではない。選択後の価格感度分析と真の締切前実現可能性は別検証。

**最短で次に着手する1作業：** GitHub開発ブランチで、実DBを読まず `FrozenDay`（全日NO_BUY/PENDING含む）・`FrozenResearchRank`（選定レースのみ）・`StoredResultRow`（結果不明可）の**入力突合せ仕様**を小さく定義する。既存の数式・払戻コードは変更せず、模擬小規模ケースで全件分母を保持する。初回は設計かごく小さい独立オフラインアダプターに限定。新Railway実行・有料CIなし。

**HARD HOLD：** 公式6艇肯定出走証拠、独立締切前初観測、実3連単収益性、Forward、BUYは未証明。原本未確認の段階で本番を解除しない。
