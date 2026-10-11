# 新競艇AI No.2 — 2026-10-11 新チャット用・最小引き継ぎ

**唯一の最新引き継ぎ。** 古い`LIVE_HANDOFF_*`、`PROJECT_HISTORY`、長いworkflow、過去チャットは履歴扱い。必要な個別判断以外は読まない。常に **1ターン1作業・最小tool call・短い結果報告・実行時間目安**。古いSHA・件数・使用量・runを現在値とみなさず、次の1作業に必要なものだけliveで取得。タイムアウト時は重複実行せず実行済みか確認。CI/Railwayの大量ログや全履歴検索禁止。ChatGPT内で行った模擬テストを本番結果と混同しない。

## 目的、予算、安全条件（必須）
- GitHub `kenshoushouri-cloud/boat-ai-v2` / branch `main`。**V5が主力開発対象、本番はV4のまま保護**。V4の収益は不振だったため、V4対V5収益比較は**必須ではない**。研究の`research/`ファイル名は互換用。V5本体完成→V5単独3連単過去収支と締切前Forward確認→十分安全なら本番切替→V4安全停止→過去データ外部保管・復元検証→不要データ/サービス整理。**自動購入は最後で別途明示承認**。本番/LINE/購入額/DB/ボリュームを無断変更しない。LINE仮候補通知は不要。
- V5目標 **月間純利益＋50,000円（未検証、利益保証・ROI実証なし）**、質を重視して**1〜3レース/日、条件不足なら0**。V5の購入点数・単価・閾値は未決定。V4旧ルールの2点×100円を流用しない。負け、VOID、返還、F/L、当時入手可能だった情報を含む同一母集団で検証、欠損はPENDINGにして水増ししない。
- **ChatGPT＋Railway合計月6,000円以内、理想5,000円以内**（税・為替・契約確認が必要）。Railway **月$10以下理想、$10–12実務目標、$15警戒、次回請求$20上限目標**。Railway Agent/AI禁止、CPU/RAM/Network/DB/WALの無用な負担を避ける。前回計測値ではV4系DB約**4.823/5GB**と容量逼迫、4 Postgres等の実費推計には**$20超のリスク**も記載（`20261010`の履歴値、現請求額ではない）。重い全期間スキャン、サービス追加、移行、削除、設定変更・再デプロイ禁止（安全審査と別承認が必要）。
- Railway接続機能では**任意SQLを直接実行不可**。ユーザーは安全なread-only SQLの実行を承認しているが、既存のRailway Queryタブを本人が実行して結果を送付した。認証情報を要求・露出しない。作業中に費用増を起こさない。

**条件付きスケジュール（保証ではない）：** 旧・2026年10月中旬の本番切替目標は現状のHARD HOLDで困難。10/10–17 公式6艇出走肯定証拠/締切前初回記録条件、10/18–25 V5読取専用選定・オッズ・決済接続、10/26–11/1 V5実3連単収支/返還検証、11/2–15 小規模Forward（BUYなし）、各安全条件・損失/費用/十分な標本が合格した場合のみ11月中下旬以降に切替検討。自動購入は別途承認・実装、開始日未確約。

## 確認済みデータ・モデル（予測能力と収益は別）
- 2025-07-01以降の履歴を基本使用。V5強化型の凍結学習は2026-03-31まで**38,442レース**、2026-04-01〜10-05の評価は**27,161レース**（過去研究の確定値、現DB再計測ではない）。1着TOP1 **56.279%→56.916%**、logloss **1.222549→1.207893**、Brier **.595876→.589822**、24場で改善。**3連単の真の収支・選定的中率ではない**。5特徴量の重み：recent_form=.50、exhibition_rank=1.00、racer_course=.75、opponent=1.25、venue_lane=.75、T=1.00。3連単120通りへのPlackett–Luce展開の2/3着分布は**未検証研究仮定**。
- Railwayでユーザーが実行済みread-only検査（**繰り返さない**）：**2026-05-01 大村12R `20260501_24_12`**、6艇×直近5走＝30走すべて4月30日以前。展示順位6艇 `[3,1,4,2,6,5]`は過去取得`official_beforeinfo_historical`、`snapshot_at=2026-08-15 13:54:54` **レース締切5月1日17:41より後**。3連単120/120有効・`is_final=true`の保存オッズ、的中 **2-1-5**、61.8倍×100円＝**払戻6,180円**、保存数値差0。オッズ取得も8月3日の後日記録。**実際の締切前取得・原本真正性・V5がその券を選定した事実・V5回収率は未証明**。別の10月5日唐津12Rも120/120だが`is_final=false`。
- 歴史的なK結果・`v2_race_entries`・`v2_realtime_exhibition_snapshots`・`v2_results`・`v2_odds_trifecta`が利用候補。過去公式HTMLはすでに構造化保存されている可能性があり、盲目的に再ダウンロードしない。締切後に取得した展示・最終オッズは**研究用事後データ**であって当時購入可能な予測入力に偽装しない。6艇の出走確定を示す**独立した公式肯定証拠なし**：`APPROVED_POSITIVE_SOURCE_SCHEMAS`は空、beforeinfo初回書込/Forward/BUY HARD HOLD。2026-10-10江戸川1Rの公式GET・24/24診断は**完了済み、再実行しない**。
- 返還艇の原本別確認は未済。`refund_boats=None`を勝手に空配列（返還なし）にしない。未確定レースを母集団から削らない。購入実績も未確認。

## V5実装済みの重要な経路
- `v5/offline_mainline_inference.py`：強化型6艇の1着確率。 `v5/offline_trifecta_shadow_ranking.py`：3連単120券ランキング。 `v5/offline_archived_six_lane_bridge.py`：6艇の直近成績・展示由来と前日学習ベクトルを受取り、券予測へ。 `v5/offline_retrospective_result_adapter.py`：固定TOP-N券と保存結果を結合。 `v5/offline_retrospective_trifecta_returns.py`：返還・VOID・PENDINGを含む仮想収支。すべて**offline/synthetic/retrospective**、Forward/BUY不許可。既存テストは各所で実行記録あり（古いテストを理由なく再実行しない）。
- **直近完了した1作業：** `v5/offline_prior_day_factor_export.py` (GitHub blob `8d155a1c35fcc2d9281e7c57aa470b846c628a75`)＋`tests/test_v5_offline_prior_day_factor_export.py` (blob `8a88efa13b9f8a823eb7b839af9a1f3f4e167fb4`)。過去日までのカウンタ `lw,lcs,lcw,rks,rkw,cs,ct,rcs,rct,ps,pw,vc,vn` と学習実績件数から、**元の**`research/v5_strong_core_calibration_pg.py` が使う`b/vr`数式で基本確率＋5特徴量を出力する研究用関数。過去日境界・6艇・重複・不足・不整合を拒否し入力Counterはコピー。**GitHubと同一コードでオフラインstubテスト12/12 PASS・py_compile PASSとの記録あり**。ただし**本物のb/vr数式との数値一致テストと、DB実データの時系列因果・完全結合は未実施**。元研究コードの結果側フィルターは実購入の母集団に流用禁止。SHAは次回必要時だけ再取得。
- **2026-10-11追加：** `v5/offline_prior_day_counter_update.py` と `tests/test_v5_offline_prior_day_counter_update.py`。全対象日の券（NO BUY含む）を`freeze_day_predictions`で固定し、全件結果照合後の`roll_forward_day`のみが翌日Counter更新。元研究の`lw/lcs/lcw/rks/rkw/ps/pw/vc/vn`と`cs/ct/rcs/rct`増分に沿う。VOID/PENDING/F/L/返還・不明は`all_results`に保持、学習採否と決済母集団を分離。入力非変更・基準状態指紋・再適用拒否。**GitHub追加済み／単体テスト9件作成済みだが実行PASSは未検証**（本環境にリポジトリ実行ランタイムなし）。本番・DB・Railway未変更。
- 既存確認ファイル：`docs/V5_PREDECISION_FEATURE_LINEAGE_TO_REAL_ROI_20261011.md`。長い旧handoffは**履歴として残す**が次チャットで全読みしない。

## Next ONE task — 新規Counter更新テストの隔離実行
`tests/test_v5_offline_prior_day_counter_update.py`を**Railway・有料GitHub Actionsを使わないオフラインPython環境**で実行し、成功確認後のみPASS記載。失敗があれば新規モジュールを最小修正。未実行のまま本番投入禁止。次段階は元研究`b/vr`との実数値一致検証で、DBの重いscanはしない。引き続き1回1作業・短い報告・目安表示・費用保護。
`ONE_TASK_ONLY / SHORT_OUTPUT / NO_BULK_HISTORY / NO_RAILWAY_AGENT_AI / BUY_LAST`
