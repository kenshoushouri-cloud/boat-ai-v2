# V5 前日因子・研究式Parity限定監査（2026-10-11）

**対象**：`v5/offline_prior_day_factor_export.py` と、研究実装 `research/v5_lc_rf_exrank_rc_plus_opponent_pg.py`、`research/v5_lane_class_plus_venue_residual_pg.py`。対象例`20260501_24_12`、ただしCounter・選手番号・級別・履歴・展示順位は全て**合成データ**。Railway、DB、公式サイト、CI実行なし。

## 実施・結果

- GitHub研究コードの純粋計算関数の該当箇所をread-only確認。係数・平滑化・`lc_probs`、`recent_strength`、`adjusted`、`rc_prior`、`rc_adjusted`、`opponent_probs`、`venue_shrunk`の関数式から**ローカルの計算用抜粋**を組み、既存GitHub blob一致の `offline_prior_day_factor_export.py` （`8d155a1c35fcc2d9281e7c57aa470b846c628a75`）を直接実行した。
- **基本確率＋5つの6艇因子ベクトルで、直接研究関数から計算した値と出力が全要素一致（観測最大絶対誤差0.0）**。5因子は直近成績、展示順位、選手コース、相手関係、場別艇番。無風の全1.0係数ではなく、差の出る合成Counter/展示を使用。
- **Counter非破壊**の確認と、`fitted_through=2026-05-01`なら `PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED` で拒否する日付境界確認もPASS。
- 開発ブランチに `tests/test_v5_offline_prior_day_native_math_parity.py` を追加（**3件**）。このテストは実GitHub研究モジュールをインポートし、`db_pg.fetch_all`などDBに触れ得る**非数式インポートのみ**をモックし、係数計算関数はモックしない。**追加検証：GitHub全文のblob SHA一致を確認して隔離Pythonで3/3 PASS（2026-10-11）。** 研究数式のモックなし、DB/事故台帳へのアクセス経路だけをインポート時に遮断。Python構文検査もPASS。完全原本と抜粋smokeの結果を区別する。

## 依然未確認

過去日の真正なCounter/モデル凍結タイムスタンプ、各6艇の元の選手番号・成績・展示の取得時刻、公式6艇肯定出走証拠、全日候補台帳、結果/返還原本、実V5 3連単適中率・純利益・実ROIは全て未確認。従って**retrospective only / Forward・BUY HARD HOLD**を継続。後日の展示・最終オッズから締切前購入を認定しない。

**Next ONE task**：`PriorDayCounters`→実`export_prior_day_factors`→`prepare_archived_research_input`のオフライン接続を、結果・オッズ混入無しの合成データに限定して検証。main/V4/DB/Railway/有料CI/BUY変更なし。

**検証一致SHA**：core研究全文`708569e9c2d19df52b26d586ca44a139286f5b1a`、venue研究全文`5ffc0a814e42e96f1c392599ca0df32d273c9d1b`、factor export`8d155a1c35fcc2d9281e7c57aa470b846c628a75`、test`884e7da4d67fb3a0fb3a06e07483f648b4edb5ca`。全てGitHubファイルのblob SHAとローカルgit hash-object一致。
