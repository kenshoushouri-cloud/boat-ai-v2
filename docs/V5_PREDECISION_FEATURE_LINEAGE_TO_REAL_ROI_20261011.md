# V5 3連単回収率検証：実DB特徴量の由来と締切時点の判定（2026-10-11）

**Scope:** GitHubコードを狭くREAD ONLY確認した設計監査。DB実レコード・カバレッジ・処理時刻の実測ではない。**V5主力、V4収益比較は必須でない。** 2025-07-01以降の対象レースを前提に、締切前に選べた予測を作るためのデータ依存を特定する。Production/BUY/Railwayは一切変更しない。

## 実装コード上の接続経路（確定した *ソース定義*）

`v5/offline_mainline_inference.py:OfflineV5InferenceInput` は `race_id`、`decision_cutoff_at`、艇番順の `lane_racer_numbers`（6艇）、`base_probabilities`（6要素）、以下5つの `factors`（各6要素）を要求する。固定ウェイトは最近成績0.50 / 展示順位1.00 / 選手コース0.75 / 対戦相手1.25 / 場×艇番0.75、温度T=1.00。**実DBを直接読む組立て処理ではなく、呼び出し側が値を与える純粋計算関数**。締切日時の形式だけ検査し、独立したソース時刻証明は行わない。

実データ学習の数式・入力元は `research/v5_strong_core_calibration_pg.py:main`（`research/v5_lc_rf_exrank_rc_plus_opponent_pg.py` と `research/v5_lane_class_plus_venue_residual_pg.py` に依存）と一致：

| 入力・特徴量 | DBまたは計算元（race_id・laneで6艇結合） | 歴史的「予測時点の値」としての結論 |
| --- | --- | --- |
| 競走ID・日付・場・締切 | `v2_races.race_id/race_date/venue_id(venue_code)/deadline_at` | 締切は検査基準として利用できる候補。**学習コードは`deadline_at`をSELECTせず日付境界でのみ学習履歴更新**。予測の`decision_cutoff_at`は別途締切より前に確定必要 |
| 6艇の登番と級別（base用） | `v2_race_entries.lane/racer_number/racer_class`; `lane_probs/lc_probs`は**過去日の**1着累積 `v2_results.first_lane`（または `trifecta_ticket`先頭）から計算 | エントリー6件・当日出走可否・級別の公開時刻、過去成績の対象日上限・学習固定時刻を別途証明する必要。現DBの最新UPSERT値が当時値とは限らない |
| `recent_form` | `v2_race_entries.recent_form`（JSONB最大5走の先着履歴）→ `recent_strength`、平滑化値/0.5 | `research/historical_recent_form_backfill_pg.py` は `v2_result_entries.source='official_k_file'` **前日まで**から再構築、当日Kは特徴構築の後に取り込む。**研究上の前日境界はOK**。ただし既存の非空値を上書きしないため全行の実在由来/取得時刻は別途未確認。後日再構築はリアルタイム証明ではない |
| `exhibition_rank` | `v2_realtime_exhibition_snapshots.exhibition_time_rank`, `snapshot_label='historical'`、`race_id+lane`; `adjusted`で過去日の順位別実績から補正 | **最大の実時間リスク**。歴史的`historical`は後日`official_beforeinfo_historical`取得によるUPSERTがあり得る。`snapshot_at=now`は過去の予測時刻ではない。`research/historical_exhibition_reuse_pg.py`で以前の`learning_all` / `final_ab`から再利用する経路もあるが、元の`source_snapshot_at`と締切の比較が不可欠。存在・6艇の順位だけで締切前取得と誤認不可 |
| `racer_course` | `v2_result_entries.racer_number/start_course/finish_position` の**前日まで**のK履歴→`rc_prior/rc_adjusted`（以前の3着内成績） | 校正スクリプトの`hday[day]`を当日予測分の計算**後**に追加する順序はOK。2025/07以来の各履歴の元レース日と原本由来、スタート後の情報を当日予測に混ぜていないことを本番導線で確認必要 |
| `opponent` | `v2_race_entries.racer_class/lane`6艇＋以前の1着実績を `opponent_probs` で相手級別組み合わせ補正 | 当日6艇の出走確定/級別の凍結時刻と、ペア実績の学習上限を別途確認。現在DB値から当日結果を選択条件にしない |
| `venue_lane` | `v2_races.venue_id`＋過去日の `v2_results.first_lane` / `trifecta_ticket` → `venue_shrunk` 場別艇番1着率 | 同日成績は研究ループで後からカウンタに加算、直接の当日リーク回避。ただし研究終了後まとめて学習した係数を当該過去年月の既知係数として扱わないこと（train/OOSの時系列切断） |
| ラベル・払戻・返還（予測不可） | `v2_results.result_status/race_status/trifecta_ticket/trifecta_payout_yen`、`v2_result_entries.finish_status/is_flying/is_late`; `v2_odds_trifecta.odds/is_final/fetched_at` | **結果・F/L・取消・返還は予測入力禁止**。レース後の収支判定だけに使い、VOIDも初期対象群から削除しない。公式の艇番別返還欄はまだ実原本で照合していない |

## 実データで立証済みの範囲（狭く、過大評価しない）

ユーザーがRailway Query UIで検証済み：`20260501_24_12` 大村12R：3連単120/120合法・一意の保存行、`is_final=true`120件。保存払戻 `2-1-5` **6,180円**、同一DBの的中オッズ **61.8倍** × 100円 = 6,180円、**差額0**。取込時刻 `2026-08-03 17:58:10` は締切 `2026-05-01 17:41` より後。これは **一つの過去レースの保存値間の数値一致**であり、「締切前に観測できたオッズ」「公式原本と照合済み」ではない。`20261005_23_12` 唐津12Rも120/120だが全行 `is_final=false`。いずれもV5回収率は未算出。

## バックテストに移るための最短実装境界

1. **予測入力のみ**で、race_id・6艇+級・古いK履歴・`recent_form`・展示順位について、それぞれ値、真のソース日付/取得時刻、当日の締切前cutoffを記録。研究用に「当時に知られ得る値（retrospectively reconstructed）」と実際のfirst-captureが実証された値（prospective verified）を**別ステータス**で保持。出走確定肯定証拠なしでは正式Forward/BET禁止。
2. 学習した`lane_probs`、`lc_probs`、`rc_adjusted`、`opponent_probs`、`venue_shrunk`、`adjusted(exhibition_rank)` の**学習データ最終日時**と対象日を比較。2026年以降に再学習したモデルパラメータは、それ以前の実購入可能性を主張する根拠にならない。研究の退避/OOSは継続できるが、履歴モデルに当該対象レースの結果が入ってはいけない。
3. 一度選んだ V5 `race_id + ticket + stake` をその時点の候補群として固定し、後日取った締切時オッズは**最終価格ベンチマーク**にのみ使用。終了結果・F/L艇の返還対象・全額返還VOIDは**購入候補を後から消さず**に別テーブル/レコードで決済。データ不備は`UNVERIFIED/PENDING`として件数を開示、絶対に負けを除外して回収率を水増ししない。
4. V5の真の実行可能回収率、利益+JPY50,000/月の実現性、資金変動/最大ドローダウン、前向き観測は**まだ未確認**。過去最終オッズから出す仮想ROIには「retrospective closing-price sensitivity only」と明記する。PLの2/3着条件付き分布はまだ研究仮説なので3連単精度そのものは未検証。

### 最小次アクション（ここでは未実行）
過去日の1レースについて、既存 `v2_race_entries` 6艇の `recent_form` の全history日付が対象日の前であるか、`v2_realtime_exhibition_snapshots` `historical`各艇の `snapshot_at/raw->>'source_snapshot_at'` の実時刻/由来が締切前かを、**既存race_idインデックスで最大6艇だけSELECT**して状態を分類する。実DBの日付型/実列定義はコード上の知識であり、必要に応じて狭い`information_schema`で先に確認する。120枚の最終オッズや全期間データは再取得しない。

**非交渉条件：** ChatGPT+Railway合計月JPY6,000以内、理想JPY5,000以内。Railway月USD10以下理想/10–12目標/15警戒/20次請求上限目標。V5月次純利益+JPY50,000は未検証の目標。Production V4保護、V5本番切替・BUYは独立した後日判断。Railway Agent/AI禁止。
