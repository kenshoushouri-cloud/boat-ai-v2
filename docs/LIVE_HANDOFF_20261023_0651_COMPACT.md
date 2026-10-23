# 新競艇AI No.2 — 2026-10-23 06:51 JST compact handoff
この文書がcurrentの唯一の運用要約。過去の長いhandoffは履歴扱い、必要な事実を確かめる場合だけ限定参照。

## 目的・優先順位
- **ConoHa上のV5**を主力に、締切前の一次データを用いた実3連単予測を完成し、2025年7月以降のウォークフォワード・バックテスト、非購入試験運用、結果検証へ。最終的に自動購入を検討するのは別途承認後。純利益+5万円/月、1～3レース/日または見送りの目標は未検証。
- 最優先：**V5実データ入力→HOLD理由→実モデル接続→非購入試験**。データ物理移行と欠損補完は精度・安全に必要な範囲で並行。全量復旧待ちで本体開発を停止しない。予想精度を下げる特徴量はバックテストで評価し採用しないが、将来用の収集は継続。
- 過去データ取得方針：2025-07以降を基本に、保存済み`boat_history_archive`やメインDBの欠損率を先に検査。公式出走表・結果・選手/モーター/ボートのprior-only特徴は必要箇所だけ補完。後日取得の展示/オッズは**本当の締切前捕捉証拠と混同しない**。まずV5非購入試験とバックテストを進め、全期間再取得を開始条件にしない。旧10月中旬目標から遅延、10/31整理目標は未保証。
- Railway Hobbyはユーザーが2026-10-23に解約済み（契約終了11/03、追加請求予定$4.92は画面時点の見込み）。今後はConoHa優先、Railway Agent/AI禁止、費用/CPU/RAM/Network最小。Google Driveはバックアップ候補だが暗号化/外部転送/復元検証は未完。旧DB/アーカイブ/backupの削除は禁止。

## 状況（Termiusスクショで確認済み）
- Repo `kenshoushouri-cloud/boat-ai-v2`、ConoHaコード `/opt/boat-ai-v5`、postgres DB名`railway`、履歴別DB `boat_history_archive`（先のread-onlyで3テーブル約1069MB）。ConoHaメインDB概数3.4GB（時点値、再利用禁止）。
- 10/22 `boat_data`スキーマ作成済み。`public.v2_venues`とステージ`v5_data.venues`は24件差分0。10/23 00:43 共通`boat_data`に**13個の非更新VIEW**を作成したが、実表物理移動/大容量COPYではなく、元`public.v2_*`を参照するだけ。旧データ収集経路/書込先は未切替。
- 10/23 **06:45** `deploy/conoha/v5_shared_views_cutover_readiness_readonly_20261023.sql`：**13/13 VIEW、非更新13/13、依存13/13、COMMIT、PASS**。再検査不要。
- 10/23 **06:51** `deploy/conoha/v5_live_prediction_inputs_sample_readonly_20261023.sql`：**0 rows、COMMIT、`V5_LIVE_INPUT_SAMPLE_READONLY_DONE_NO_FORECAST_NO_BUY`**。これは「当日JSTの実行時点より先に締切のある最大6レース」を選ぶ限定SQL。07:00予定のmorning/forward前の06:51だったため、**収集失敗・データ欠損の証拠にはならない**。実予想/BACKTEST/BUYは未実行。午後・深夜に同じSQLを使って0件となっても診断不能（既に締切終了）。当日レースの締切時点原本を検査する新たなread-only監査が必要。
- 直前の収集timersはmorning 07:00、night23:00、forward07:00、midnight-catchup01:20、当時4件 enabled/active。**10/23 07:00の実行成否は未確認**。4件のsystemdサービスが検査瞬間inactiveでもoneshotなので直ちに失敗とは判断しない。再起動は収集停止窓の検証後。
- 共通routeのunit test **29/29 PASS**。しかし既存の`v5.offline_mainline_inference`は合成入力での1着確率に留まり、実レース出走6人/時点検証/3連単買目・ROIの本番予測は未証明。**V5予想本番/HARD HOLD、BUY無効**。


## 10/23 午前の実測更新（同日11:00 JSTまで、追加確認済み）
- morning 07:46:35 正常終了：成功168、非開催/データなし120、失敗0。forwardの07:50実行は対象0で正常終了、08:55には対象1Rのentry6/odds120、exhibition0（公式掲載前）を記録。07:00-07:10 forward status75は `flock -E 75 -n` + `SuccessExitStatus=75` の意図的なロック競合扱いであり、systemd成功表示はデータ保存の証拠ではない。
- 実レース `20261023_21_02` 締切09:17：同じ `conoha_forward_20261023_090502` ラベルでentry6（09:05:13）/exhibition6（09:05:13）/odds120（09:05:22）を保存。締切前ラベルと時刻は確認したが初回観測・未改変の第三者証明ではない。
- 10/23公式K過去日監査：1,008出走（618選手）は`entries.recent_form`が全件0/空だが、前日までに取得記録のあるKから5走再構成可能1,008/1,008。対象6艇の5走TOP3率60/0/0/40/40/40。過去K 2025-07-01～2026-10-20は71,912レース、431,472艇行（0時前取得記録431,472、コース・着順等425,605）。これらは研究学習材料で、前日状態凍結・特徴量の時点認証・予測ではない。
- GitHub read-only SQL `deploy/conoha/v5_live_asof_gap_audit_readonly_20261023.sql` と `deploy/conoha/v5_live_six_lane_input_bridge_readonly_20261023.sql` を追加。後者はTermiusで6行、同一ラベル6/6/120、K5走、`HOLD_UNVERIFIED_FIRST_CAPTURE_AND_MODEL` を確認。実モデル推論/3連単券推奨/BUYは未実行。
- `public.v2_bao_exhibition_shadow_snapshots`/`public.v2_bao_market_shadow_snapshots` はテーブルが存在するが、当該レースは両方0行（他レース・全表は未検査）。このBao研究用表は稼働中の `v5/conoha_realtime_window_pg.py` + `v21_realtime_collector_pg_safe.py` の保存先ではない。V5専用の`official_http_transport.py`/`official_first_write_storage.py`/`official_first_write_executor.py`/`official_capture_pipeline.py`はGitHubの未配備設計。後者はofficial_beforeinfoに対して認証済み6艇出走証拠未確定のためPRE-HTTP HARD HOLD。既存の保護ゲートを無断解除/改造しない。将来の初回取得証拠は取得時に独立記録し、後からレース原本を捏造しない。
- ユーザーと再確認：予想に必要なデータは将来V5/V6共通の`boat_data`に一元化。**今も稼働中の旧writerは維持して13 VIEW経由で読む**。物理正本切替はバックアップ・同期・停止窓・戻し確認後、表単位。履歴別DBは重複コピーせずread-only参照。収集停止・大量移行・削除・BUYは引続き不可。

## 2026-10-23 前日学習状態の実モデル接続監査
- `v5/offline_prior_day_counter_update.py`（13Counter増分）/ `v5/offline_prior_day_factor_export.py`（基礎確率+5x6因子）を静的点検。モデル入力には `lw/lcs/lcw/rks/rkw/cs/ct/rcs/rct/ps/pw/vc/vn` の**13系統の前日固定Counter**が必要。公式K5走とTOP3率だけでは作れない。凍結された当時の完全なCounter/独立原本証拠は未確認。
- 実6艇の前日Kの個別`race_date`+`finish_position` JSONB配列を返す**read-only専用SQL** `deploy/conoha/v5_prior_day_recent_form_bridge_readonly_20261023.sql` をGitHub追加。文書`docs/V5_REAL_PRIOR_DAY_FACTOR_BOUNDARY_20261023.md`に全5因子・13Counter・HOLD条件を記載。**ConoHaでは未実行、実予測/BUY未実行**。
- 既存writer/共通13VIEW/物理移行/旧表/タイマーは一切変更なし。初回原本とofficial positive six-active evidenceのHARD HOLD継続。

## 10/23 12:04 13Counter元データの1日検査（Termius実測）
- `v5_prior_day_counter_sources_coverage_readonly_20261023.sql`をConoHaで`2026-10-20`だけ実行。race_total **144**、出走6艇 **144**、official results **144**、clean K6艇・コース等 **132**、`historical`展示順位6艇 **0**、全条件の構造的学習候補 **0**、historical時刻条件 **0**、COMMITで成功。**展示データ全体が0とはまだ判断できない**（他ラベル未集計）。132との差分12レースは原因不明、後で分類。
- 他ラベルの展示6艇の保存有無を調べる限定read-only `deploy/conoha/v5_exhibition_label_coverage_readonly_20261023.sql` をGitHub追加。未実行、学習/予想/BUYなし。後日取得の展示を当時の初回取得証明に転用禁止。

## 破壊防止・重要
- **`deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh`と`boat_shared_bulk_stage_20261023.py --apply`は実行しない**：同名の13 VIEWが存在し物理COPY先と競合。実行予約があったならread-onlyで確認。旧`public`物理DBテーブルや`v5_data.venues`のDROP、`ALTER TABLE SET SCHEMA`、大量COPY、収集停止、サービス設定、課金、LINE、自動購入は独立検証とユーザーの明示承認後。新`boat_data.venues`は非更新VIEWなので`shared_venues_v1` writer profileは**絶対に有効化しない**。
- 締切前に保存された展示・オッズ等の一次証拠と単なる取得日/後日公式履歴を区別すること。未来情報リーク禁止、結果/払戻は予想特徴量に混ぜない。結果は翌日追補可でも事前スナップショットは後日再現不可。
- 10/19時点のdumpのみではその後の原本を復元できない恐れ。削除/物理移行よりバックアップ・切戻し保証を優先。
- トーク容量対策：**1回1作業**、必要最小のGitHub/Railwayツール、巨大文書・過去会話参照禁止。SHA/run/件数/容量はliveに必要なものだけ。タイムアウト後の再実行禁止。短い結果報告、所要時間は精度がある場合だけ。最新進捗の追記は**このcompactを上書き・精査**、古い長文handoffへの追記は禁止。

## Next ONE task（次の一作業）
**ConoHa Termiusで`deploy/conoha/v5_exhibition_label_coverage_readonly_20261023.sql`を2026-10-20だけ一度read-only実行**。全ラベルの展示6艇記録・ラベル別件数を確認し、historical=0と展示自体の欠損を切り分ける。今回のtimestamp<deadline列も初回原本性を証明せず、3連単/実収支/BUYには昇格不可。DB更新・既存収集停止・物理移行・旧表削除なし。12レースのK欠落理由はこの次の別作業。
