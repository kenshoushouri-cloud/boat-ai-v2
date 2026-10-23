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
- 実6艇の前日Kの個別`race_date`+`finish_position` JSONB配列を返す**read-only専用SQL** `deploy/conoha/v5_prior_day_recent_form_bridge_readonly_20261023.sql` をGitHub追加。文書`docs/V5_REAL_PRIOR_DAY_FACTOR_BOUNDARY_20261023.md`に全5因子・13Counter・HOLD条件を記載。**ConoHaで11:53実行し6艇各5走のKデータJSONを確認、実予測/BUY未実行**。
- 既存writer/共通13VIEW/物理移行/旧表/タイマーは一切変更なし。初回原本とofficial positive six-active evidenceのHARD HOLD継続。

## 10/23 12:04 13Counter元データの1日検査（Termius実測）
- `v5_prior_day_counter_sources_coverage_readonly_20261023.sql`をConoHaで`2026-10-20`だけ実行。race_total **144**、出走6艇 **144**、official results **144**、clean K6艇・コース等 **132**、`historical`展示順位6艇 **0**、全条件の構造的学習候補 **0**、historical時刻条件 **0**、COMMITで成功。**展示データ全体が0とはまだ判断できない**（他ラベル未集計）。132との差分12レースは原因不明、後で分類。
- 他ラベルの展示6艇の保存有無を調べる限定read-only `deploy/conoha/v5_exhibition_label_coverage_readonly_20261023.sql` をGitHub追加。未実行、学習/予想/BUYなし。後日取得の展示を当時の初回取得証明に転用禁止。

## 10/23 12:09 過去展示ラベル調査（Termius実測）
- `v5_exhibition_label_coverage_readonly_20261023.sql`を10/20だけread-only実行：全144レース中**29レース**で展示6艇が同じラベルに揃い、計174艇行。`conoha_forward_*` 28レース/168行、`conoha_other_*` 1レース/6行、`historical` 0。29件とも現存`snapshot_at`が締切前の形式条件を満たすが**初回取得の不変証明ではない**。残り115件はforward対象絞込か欠測か未分類。K6正常132件と展示6の**積集合は未計測**。
- GitHubに`deploy/conoha/v5_exhibition_k_joint_coverage_readonly_20261023.sql`追加。10/20の1日だけでK正常132件と展示29件の同一race_id積集合を集計するSQL。未実行、DB write/モデル/BUYなし。

## 10/23 12:17 公式K×展示の同一レース積集合（Termius実測）
- `v5_exhibition_k_joint_coverage_readonly_20261023.sql`を`2026-10-20`1日だけ実行成功/COMMIT：全144、出走6=144、clean-K6=132、いずれか同一ラベル展示6=29、現存時刻上締切前展示6=29、**Kと展示が同一race_idで両立=27**、時刻条件込み=27（**初回原本証明ではない**）、展示6だがclean-K6ではない=2、clean-K6だが展示6なし=105、展示6なし合計=115。
- Kの非clean対象12件の欠測/進入コース/着順/ F・L 状況を1日だけ診断する `deploy/conoha/v5_k_six_row_exclusions_readonly_20261023.sql` を追加、**未実行**。F/L等の事後情報は研究用学習可否の分類専用であり、当時の出走前フィルタや事後的な負け除去に使わない。後日展示再取得でpredeadline原本と認定しない。

## 10/23 12:23 K除外12レースの詳細（Termius実測）
- `v5_k_six_row_exclusions_readonly_20261023.sql` を10/20だけ実行、**12行/COMMIT/監査正常終了**。画像下部で`K_FINISH_NOT_1_TO_6`（不正/欠測着順）と`K_COURSES_NOT_SIX`（進入コース6種類不成立）の双方を確認。可視行のF/L真・未知は0だが**画像上部切れのため12件全体の原因内訳は未確定**。12件は勝手に補完/削除せず研究用除外候補、実際の出走前選別には使わない。
- 例外艇の`finish_status`、進入/着順、展示6の有無を12件の短い一覧として調べる`deploy/conoha/v5_k_anomalous_lanes_readonly_20261023.sql`をGitHub追加、未実行。**既存27のK+展示6の重複はあくまで学習用source shape**であり、当時時点初回の証明でも収益証明でもない。

## 10/23 12:33 K除外の全レース原因と13Counterオフライン実装
- Termius `v5_k_anomalous_lanes_readonly_20261023.sql` 12行/COMMIT：`F_OR_L` **1**（`20261020_01_08` 展示6あり）、`FINISH_OR_STATUS` **8**（うち`20261020_19_06`展示6あり）、`COURSE` **3**。F/Lまたは着順・コース不明を公式事前判定で後知恵除外禁止。12件は保存し研究適合を別分類。10/20のK6 + 展示6の共通**27件は構造候補**、証拠確定ではない。
- `v5/offline_retrospective_counter_seed.py` で**明示的にretrospective限定**の13Counter「1日分寄与値」計算を追加。未知の公式結果/事故なし/返還なしはfail-closed、着順とwinnerの矛盾・6艇/展示/進入異常も除外、出力は`forward_eligible=False,buy_eligible=False`固定。ConoHaからの実27行アダプターは未作成、過去の全日付累積も未完成。
- `tests/test_v5_offline_retrospective_counter_seed.py` の合成8件をGitHub Actionsで実行。当初のfixtureの`incident_free_verified`指定ミスにより4 FAIL、修正後**8/8 PASS**（Issue #581 `6356816325`）。公式HTTP/ConoHa/Postgres/BUY未使用。**research-native parity未証明**：特に研究版のコース別履歴には展示がない正常Kレースも使われ得る一方、現1日prototypeは受理した展示有りレース由来のcourse値のみ。これを完成した前日学習状態としてV5へ流用禁止。

## 10/23 研究fitとK進入履歴の母集団分離（GitHub実装）
- `v5/offline_research_two_population_day.py`を追加：展示順位6艇を要するモデルfit用と、展示欠損でも正常公式K進入・着順から利用できる`cs/ct/rcs/rct`履歴用を別集計するretrospective専用純粋Python。交差レースは二重計上せず、K未提示・選手/着順/進入不一致・事故/返還が未確認ならfail-closed。前日以降にしか学習対象へ反映しない。初回原本認証・長期モデル凍結・BUYの証明にはならず、全許可flag=False。
- `tests/test_v5_offline_research_two_population_day.py`模擬8件をGitHub Actionsで**8/8 PASS**（Issue #581 コメント`6356897640`）。ConoHa/HTTP/Postgresには未接続。既存 `v5/offline_retrospective_counter_seed.py`の1日fit寄与のコースカウンタを、独立Kコース母集団の値に置換して二重計上を防ぐ。原本/公式事故・返還独立証明が揃う実DB adapter と本家research数式・コース母集団のparityは未検証。

## 10/23 返還・事故ソースの実DB接続前提（GitHub準備）
- `deploy/conoha/v5_one_day_result_refund_source_contract_readonly_20261023.sql` を追加。10/20の144レースを対象に、結果/返還・事故・公式K・展示の**実在列と結果状態の分布**をread-onlyで検査する。DBへの実行はまだ。現存 `result_status='official'` やF/Lが偽でも**返還なしが独立証明されたことにならない**。ない列を架空の証拠にせず、27構造候補を勝手にfit採用しない。先行 `v5/offline_research_two_population_day.py` 8/8 PASS は合成検査だけ。

## 10/23 13:03 結果・返還源泉の実DB構造（Termius実測）
- `v5_one_day_result_refund_source_contract_readonly_20261023.sql`で`2026-10-20`の`v2_results`**144/144がresult_status=official/race_status=official、raw JSONBあり**、COMMIT済み。ただし別列の返還艇証拠は未確認。公式扱いでも事故・特殊着順・返還なしを推認不可。前日監査では12レースにK異常あり。 `save_k_day_results_pg.py`はK結果をstructured/rawへ保存する設計だが`raw`の実内容は未確認。
- `deploy/conoha/v5_result_raw_keys_readonly_20261023.sql`追加：同日144行の`v2_results.raw`最上位/1階層下の**JSONキー名・型だけ**をread-only調査。未実行。独立の返還なし証拠が見つかるまで実27候補を`incident_free_verified=True/refund_boats=()`としない。

## 10/23 13:08 V5実DB読取アダプター整備
- ConoHa Termiusで`v5_result_raw_keys_readonly_20261023.sql`成功/COMMIT。10/20結果`raw`144/144がJSON objectで、上位は`finish_order/race_title/source/wave_height_cm/weather/wind_direction/wind_speed_m/winning_method`の8キー、下位objectキー0。**返還艇原本は確認できず**。公式result status=official全144でも事故・返還なしを立証しない。
- GitHub`v5/conoha_research_one_day_sources_readonly.py`追加：ローカルPostgres 1日限定SELECTのみ、`boat_data`出走6+展示同ラベル6+公式K6+結果ticketを照合して**fit構造候補とKコース構造候補**を独立に準備。全候補の事故/返還/初回取得権限を明示的にUNVERIFIEDとして計算への昇格を拒否。**実DB実行は未実施**、Python/SQLは本番収集コマンドへ接続しない。
- 合成オフラインテスト`tests/test_v5_conoha_research_one_day_sources_readonly.py` **7/7 PASS**（Issue #581 bot `6357196894`）。これはSQL/cardinality/実学習のPASSではない。新実装の現場読取には稼働git作業ツリーを`git pull`せず、`git archive origin/main`を一時ディレクトリへ抽出して実行する。自動収集・DB/BUYは継続無変更。

## 10/23 13:32 初回実DB adapter 0件の原因と修正
- ユーザーが一時tar展開の`v5.conoha_research_one_day_sources_readonly --date 2026-10-20`を実行。RACES=144だがROSTER_6=0、K_COURSE_SHAPE_6=0、EXHIBITION_6=0、JOINT=0、各提案0、HOLD=維持。過去SQLの144/132/29/27と矛盾し、**データ消失ではなくPython入力型の非互換**。現時点でDB実データ0件の原因解消はまだ現場未確認。
- 根因の有力候補：`pg_schema_compat_v5.py`で`v2_race_entries.racer_class`は**integer**。旧アダプターの`type(racer_class) is str`が全艇拒否。公式Bファイル`CLASS_MAP={B2:1,B1:2,A2:3,A1:4}`と同じ対応で数値コードを正規化し、`racer_class_text`と矛盾する場合はfail-closedする修正を`v5/conoha_research_one_day_sources_readonly.py`に実装。SELECTにも`racer_class_text`追加。
- GitHub Actions Issue #581 コメント`6357476166`：修正後の合成テスト**9/9 PASS**。**ConoHa再検査は未実行、144/132/29/27を復元したとはまだ断言しない**。元サービス/DB/13VIEW/旧writerは変更していない。独立事故/返還なし・初回原本証明は未完了、HOLD継続。

## 10/23 13:39 実DB sourceアダプター完全一致＋13Counter安全プレビュー
- ユーザーTermiusで修正版 `v5.conoha_research_one_day_sources_readonly --date 2026-10-20` を隔離`git archive`からread-only実行：**RACES=144、ROSTER6=144、K_COURSE_SHAPE6=132、展示の時刻付き6形状=29、共通fit形状=27、fit proposals=27、course proposals=132**。以前のSQL結果に完全一致。正常終了。**研究fit承認0、course fit承認0、初回原本0、Forward0、BUY0**は意図したHOLD（事故/返還独立証明不足）。実DB/稼働収集/13VIEWへ書込み変更なし。
- GitHub `v5/offline_unverified_counter_shape_preview.py`を追加。上記ソースproposalsから13Counter**各系統の総数だけ**を計算する非モデル用構造確認。実Counterの中身・`PriorDayCounters`オブジェクト・係数・予測を生成せず、未証明出所/事故/返還を実学習へ昇格しない。独立Kコース母集団132と展示付き27を区別し二重計上/不一致拒否。`v5.conoha_research_one_day_sources_readonly`へオプション`--counter-shape-preview`を追加。本番収集とは未接続。
- 合成オフライン tests 9+5＝**14/14 PASS**（Issue #581 `6357573649`）。最初の5件テストには重複拒否の期待値誤りが1つあり修正済み。**ConoHa上で追加オプションの実行はまだ**。実際のモデル学習値・独立predeadline原本・ROI/BUYは完成していない。

## 10/23 13:55 Counter shape preview の `python -m` 型エラー修正
- ユーザーTermiusの`--counter-shape-preview`実行ではSOURCE検査は**144/144/132/29/27**で再一致、その後`ValueError: EXACT_SOURCE_PROPOSALS_REQUIRED`で停止。原因は`SourceProposals`を実行用モジュールに定義したため、`__main__`と通常importの同名クラスが別オブジェクトになったこと。データ欠損/収集故障でない。`SHAPE_*`値の実DBプレビューは未取得。
- 型を独立した`v5/conoha_research_source_contract.py`へ切り出し、実行側/計算側が共有するよう変更。回帰テストには**実際の`runpy.run_module(..., run_name='__main__')`+模擬DB**を追加、最終GitHub Actions Issue #581コメント`6357768348`で**16/16 PASS**。途中のモック`rollback`検査期待値の修正を含む。**実ConoHa再実行は未実施**。返還/事故・初回原本証明なし/実Counter fit未完了/Forward0/BUY0を維持。

## 10/23 14:24 実DB13Counter構造プレビュー成功
- Termiusで `--date 2026-10-20 --counter-shape-preview` 正常終了：**144/144/132/29/27**、未認証fit27/K履歴132。13家族のSHAPE総数は`lw27/lcs162/lcw27/rks162/rkw27/ps810/pw135/vc27/vn27/cs792/ct396/rcs792/rct396`で整合。**純粋な件数で本当の前日Counter/予測ではない**。`PRIOR_STATE_FITTED=0/FORWARD_ELIGIBLE=0/BUY_ELIGIBLE=0`は意図通り、結果/返還/初回時刻は未証明。
- ギャップを`docs/V5_PRIOR_STATE_COHORT_PARITY_REVIEW_20261023.md`に整理：本来の研究K進入母集団と旧`offline_prior_day_counter_update.py`のfit限定コース更新で差が生じ得る。また研究側の級別数字文字列と新側`A1/A2/B1/B2`を混用できない。数式・日次母集団一致と事故/返還根拠が次の優先ゲート。

## 10/23 14:24 実測更新
- Termiusの1日read-onlyプレビュー完了：全144、出走6艇144、K正常132、展示6艇29、共通形状27。13集計系統の総件数が構造的に一致。正式な学習済み状態ではない。
- 研究CounterとKコース母集団の差、級別キーの規約、同日結果の先読み禁止を検査。合成回帰10/10成功。詳細は docs/V5_PRIOR_STATE_COHORT_PARITY_REVIEW_20261023.md。

## 10/23 15時台 研究13Counterの暦日ロールフォワード検証
- `v5/offline_retrospective_prior_day_chain.py`追加。旧研究ループの2母集団・日付D→D+1加算を合成日付で再現。**fit対象がある日には展示なしKもコース履歴へ加算、fit0の暦日は旧研究ループと合わせKだけの増加を保留**。他方式は研究候補として別比較。欠損日・同日結果使用・Counter矛盾を拒否、HOLD/BUY無効固定。
- `tests/test_v5_offline_retrospective_prior_day_chain.py`8件を追加し、従来2母集団10件とあわせ**GitHub Actions 18/18 PASS**（Issue #581 comment 6358891179）。全実データ学習・公式返還認証・本番予測は未実施。詳細`docs/V5_PRIOR_STATE_COHORT_PARITY_REVIEW_20261023.md`。

## 10/23 公式K事故・返還証拠の最小監査
- `research/historical_incident_eligibility.py`は`NO_INCIDENT_EVIDENCE`でも`primary_training_eligible=None`。公式Kの正常艇6行・result_status=officialは**返還ゼロ認証ではない**。`save_k_day_results_pg.py`のK保存は`finish_status`/F/L等の事故兆候を保持するが、独立した返還節の証明は未確認。確認済み全レース取消レジストリ71件は対象日が別で、非掲載＝返還なしではない。
- `deploy/conoha/v5_k_incident_refund_gap_readonly_20261023.sql`を追加。**10/20の1日限定**で公式Kの正常・事故・未知着順・進入不完全レースを分類、現在のDBスキーマ内の返還関連列候補だけを列挙。**ConoHa未実行**。履歴別DBのメタデータは未検査。削除・fit昇格・BUYなし。

## 破壊防止・重要
- **`deploy/conoha/boat_shared_bulk_schedule_once_20261023.sh`と`boat_shared_bulk_stage_20261023.py --apply`は実行しない**：同名の13 VIEWが存在し物理COPY先と競合。実行予約があったならread-onlyで確認。旧`public`物理DBテーブルや`v5_data.venues`のDROP、`ALTER TABLE SET SCHEMA`、大量COPY、収集停止、サービス設定、課金、LINE、自動購入は独立検証とユーザーの明示承認後。新`boat_data.venues`は非更新VIEWなので`shared_venues_v1` writer profileは**絶対に有効化しない**。
- 締切前に保存された展示・オッズ等の一次証拠と単なる取得日/後日公式履歴を区別すること。未来情報リーク禁止、結果/払戻は予想特徴量に混ぜない。結果は翌日追補可でも事前スナップショットは後日再現不可。
- 10/19時点のdumpのみではその後の原本を復元できない恐れ。削除/物理移行よりバックアップ・切戻し保証を優先。
- トーク容量対策：**1回1作業**、必要最小のGitHub/Railwayツール、巨大文書・過去会話参照禁止。SHA/run/件数/容量はliveに必要なものだけ。タイムアウト後の再実行禁止。短い結果報告、所要時間は精度がある場合だけ。最新進捗の追記は**このcompactを上書き・精査**、古い長文handoffへの追記は禁止。

## Next ONE task（次の一作業）
ConoHa Termiusで`deploy/conoha/v5_k_incident_refund_gap_readonly_20261023.sql`を`day=2026-10-20`で1回だけREAD ONLY実行し、144レースの公式K事故・不明データ分類と返還原本の候補列を確認。正常コードでも返還なしと認証しない。`boat_history_archive`等別DBまでは今回確認しない。ConoHa収集、13VIEW、旧writer、物理移行、DB更新、BUYは維持・不変更。最小の1作業ずつ進める。
