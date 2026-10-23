# V5実データ→強化型5因子 入力境界（2026-10-23）

**静的監査と非更新SQLの準備のみ。本番確率算出・係数凍結・データ移行・BUYは未実施。**

## 静的確認した確定事実

- `v5/offline_prior_day_factor_export.py` は `PriorDayCounters(fitted_through, history_start, completed_races, counters, source_ref)` を受ける純粋関数。結果は6艇の基礎確率+`recent_form/exhibition_rank/racer_course/opponent/venue_lane` の5本の6要素factor。研究側の `v5_lc_rf_exrank_rc_plus_opponent_pg.py`、`v5_lane_class_plus_venue_residual_pg.py` 数式に依存。**入力日付チェックは、過去時点に本当に観測されていた証明ではない**。
- 13種のCounterキー：`lw`（枠ごと1着）、`lcs/lcw`（枠×級別出走/1着）、`rks/rkw`（枠×級別×展示順位出走/1着）、`cs/ct`（進入コース出走/3着内）、`rcs/rct`（コース×選手出走/3着内）、`ps/pw`（対戦相手組成出走/1着）、`vc/vn`（場別1着枠/対象レース数）。これらは単なる公式K結果件数や直近5走のTOP3率だけでは再構築できない。
- `v5/offline_prior_day_counter_update.py` は研究用に一日分の全レース予測（NO BUY含む）を結果より先にfreezeし、当日全結果（PENDING/VOID/返還/F・L含む）照合後にfit eligibleなものだけ次日Stateへ更新。既存の`source_ref`とstate fingerprintは呼出側由来で、独立した原本性・全対象日網羅性の証明ではない。結果除外を後から購入対象選択の条件に流用禁止。
- `v5/offline_mainline_inference.py` は5因子から1着確率、`v5/offline_trifecta_shadow_ranking.py` は研究仮定のPlackett–Luce 2・3着拡張で120点券順位。**実データによる学習係数認証や3連単の実測精度/利益が成立したことにはならない**。
- 2026-10-23 `20261023_21_02` の共有VIEW接続は選手6・展示6・オッズ120・5走件数を確認済み。しかし先のSQL出力は`prior_k_top3_pct`など集計値で、モデルの`recent_strength`が要求する各走の `race_date` と `finish_position` 配列を提供していない。

## 今回追加した具体的な接続部

`deploy/conoha/v5_prior_day_recent_form_bridge_readonly_20261023.sql` は上記一レースに限り、既存Kテーブルから各艇直近5レースの`[{"race_date":"YYYY-MM-DD","finish_position":N}, ...]`を新しい順に`jsonb`で返す。選手番号・級別とともに既存`ArchivedLane.recent_form`へ移すための**入力ペイロード確認専用**。K取得時刻は**当日0:00 JSTより前**で、同日結果や着順未来情報の混入を拒否。直近5走のKがあるかだけを検査し、Counterの生成、DB保存、予測/BETは行わない。

出力 `HOLD_NO_FROZEN_PRIOR_COUNTERS_OR_FIRST_CAPTURE` は**「5走が足りる場合でもV5予測可ではない」**ことを明示。DBに本当に存在する証明はTermiusのread-only実行待ち。

## 残る重要な接続ゲート

1. 2025-07以降の公式結果に対応する**過去の出走6艇・級別・当該レース締切前展示6順位・コース履歴**を研究用に日付境界付で適切に対応付け、上記13Counter全キーの母集団・欠損を監査。mutable展示履歴は当時のfirst-observed証明ではないので混同しない。
2. 前日確定時点までのCounterを**同一過去日より未来を読まず**に構築、カウンター一致性/日付・モデル定義・ハッシュ・データ出所の凍結を監査。適切に再構成できない日は欠損HOLD。
3. 選手6人が実際に出走可能と確認された公式positive start evidence、初回HTTP raw bytes/時刻・DB commit・独立監査、締切前の展示/オッズ状態を別々に検証。どれか不足なら本番Forward/BUYはHARD HOLD。
4. まず非購入シャドーと2025-07以降の同一母集団ウォークフォワード・バックテストでPL3連単確率校正と収支を評価。採用特徴量/買目は事後結果で選定しない。

**実行禁止事項：** 13 VIEWへINSERT、今のwriter停止/経路切替、DB全件COPY、過去のmutable snapshotの「初回原本」昇格、BUY・LINE変更、未承認DDL・SQL UPDATE。

## 次の一作業

ConoHa Termiusで上記read-only SQLを一度だけ実行し、6艇のK5走レコード日時・配列が仕様どおりか確認する。タイムアウト時は無条件再実行せず原因を確認。
