# 新競艇AI No.2 — 2026-10-11 新チャット用・最小引き継ぎ

**唯一の最新引き継ぎ。** 古い`LIVE_HANDOFF_*`、`PROJECT_HISTORY`、長いworkflow、過去チャットは履歴扱い。必要な個別判断以外は読まない。常に **1ターン1作業・最小tool call・短い結果報告・実行時間目安**。古いSHA・件数・使用量・runを現在値とみなさず、次の1作業に必要なものだけliveで取得。タイムアウト時は重複実行せず実行済みか確認。CI/Railwayの大量ログや全履歴検索禁止。ChatGPT内で行った模擬テストを本番結果と混同しない。

## 目的、予算、安全条件（必須）
- GitHub `kenshoushouri-cloud/boat-ai-v2` / branch `main`。**V5が主力開発対象、本番はV4のまま保護**。V4の収益は不振だったため、V4対V5収益比較は**必須ではない**。研究の`research/`ファイル名は互換用。V5本体完成→V5単独3連単過去収支と締切前Forward確認→十分安全なら本番切替→V4安全停止→過去データ外部保管・復元検証→不要データ/サービス整理。**自動購入は最後で別途明示承認**。本番/LINE/購入額/DB/ボリュームを無断変更しない。LINE仮候補通知は不要。
- V5目標 **月間純利益＋50,000円（未検証、利益保証・ROI実証なし）**、質を重視して**1〜3レース/日、条件不足なら0**。V5の購入点数・単価・閾値は未決定。V4旧ルールの2点×100円を流用しない。負け、VOID、返還、F/L、当時入手可能だった情報を含む同一母集団で検証、欠損はPENDINGにして水増ししない。
- **ChatGPT＋Railway合計月6,000円以内、理想5,000円以内**（税・為替・契約確認が必要）。Railway **月$10以下理想、$10–12実務目標、$15警戒、次回請求$20上限目標**。 **2026-10-12決済条件追加：VPS移行先はデビットカード（カードブランド/発行会社の認証成立を要確認）で支払えることが必須。2026-10-12公式情報: シンVPSはVisa/Mastercard/JCBデビット受付（ただし最低3か月、一括前払い。2GB・3か月契約換算月1,020円）、ABLENET VPSはデビット受付（2GB L1月払い税込1,234円、試用申込みでも一時引落し）、XServer VPSも一部デビット対応（2GB月契約1,980円）。KAGOYA CLOUD VPS/WebARENA Indigoは明示的にデビット不可、ConoHa VPSもクレカ登録のデビット不可。カード発行元制限と3Dセキュア2.0要確認。無断契約なし。**
**2026-10-12ユーザー最新方針：自宅PC24時間稼働はしない。収益未実証の間は最安運用を最優先し、VPSがRailwayより総費用で安ければV5完成前でも早期移行を検討。**2026-10-13最新VPS条件: 自宅PC24h稼働なし、オンライン申込・決済完結（書類郵送なし）、Olive VISAデビットまたはネット銀行決済可、1ヶ月ずつ契約・支払、長期一括前払いなし、収益未証明中の費用最小化。** 3ヶ月前払いのシンVPSは除外。KAGOYAは口座振替に書類郵送が必要・VISAデビット不可のため優先度を下げる。WebARENA Indigoはデビット不可。**新第一比較候補: ConoHa VPS 1ヶ月まとめトク2GB/SSD100GB通常月1,259円、4GB/SSD100GB月2,189円、ConoHaチャージへVISAデビットまたはオンライン銀行振込で入金可、申込/支払郵送不要。ただしチャージ残高管理必要、Oliveカード個別決済承認未確認。**月払い税込候補(公式確認): ABLENET Linux VPS L1 2GB/SSD40GB更新後1,476円、L2 4GB/SSD80GB更新後2,167円(カード発行元審査、試用申込時デビット即引落しあり)。WebARENA VPSクラウド2GB/SSD30GB 946円/月(契約1ヶ月自動更新、初回請求は当月日割+翌月分、二重引落し可能性、安価版有料バックアップ非対応)。XServer VPSクラウド4GB/SSD50GB 2,480円/月(1ヶ月契約、最大7日自動バックアップ標準、VISAデビット可だが発行元審査)。旧XServer VPSは新規申込停止。新規契約は別承認、毎月1回の支払でも初回2か月相当の請求の例あり。容量、月額、バックアップ、移行時の二重支払も比較して決定。Railway live productionには4件の5GB設定DBボリューム、直近24時間disk使用の代表値はcandidate-v4約4.898GB、Postgres-EKp2約3.806GB、archive約2.340GB、candidate-v3約4.553GB（合算は概算15.6GB、現請求額ではない）。事前のバックアップ・別環境復元・V5処理性能・cron/監視・費用比較・切替後再検証を必須。無断VPS新規契約/有料サービス追加、DB削除、V4本番停止・移行実行なし。 **ConoHa VPS 3.0バックアップ最新公式確認(2026-10-13): 日次自動バックアップは別料金、100GB/月363円・標準14世代(最大30世代、有料増)。VPS 1ヶ月通常更新2GB/100GB 1,259円+363円=1,622円、4GB/100GB 2,189円+363円=2,552円。無料スナップショットは1世代/24時間限定でバックアップ代替不可。PostgreSQLはサーバーイメージだけに頼らず定期的なpg_dump/復元試験、可能ならConoHa外の独立保管先が必要。追加の保管料金・二重契約・2GB性能は未検証。契約/購入/移行は未承認。****Railway Agent/AI禁止、CPU/RAM/Network/DB/WALの無用な負担を避ける。前回計測値ではV4系DB約**4.823/5GB**と容量逼迫、4 Postgres等の実費推計には**$20超のリスク**も記載（`20261010`の履歴値、現請求額ではない）。重い全期間スキャン、サービス追加、移行、削除、設定変更・再デプロイ禁止（安全審査と別承認が必要）。
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
- **2026-10-11追加：** `v5/offline_prior_day_counter_update.py` と `tests/test_v5_offline_prior_day_counter_update.py`。全対象日の券（NO BUY含む）を`freeze_day_predictions`で固定し、全件結果照合後の`roll_forward_day`のみが翌日Counter更新。元研究の`lw/lcs/lcw/rks/rkw/ps/pw/vc/vn`と`cs/ct/rcs/rct`増分に沿う。VOID/PENDING/F/L/返還・不明は`all_results`に保持、学習採否と決済母集団を分離。入力非変更・基準状態指紋・再適用拒否。**隔離Python 3.13で9/9 PASS・py_compile PASS**。GitHubの実装/テスト両ファイルと隔離コピーのblob SHA一致。`_fingerprint`構文括弧1件修正は**開発ブランチのみ**（`feature/v5-prior-day-counter-test-20261011`）、mainへの未反映に注意。`PriorDayCounters`依存は同じ公開定義の軽量stubを使用したため、フルリポジトリ結合テストとは区別。本番・DB・Railway未変更。
- **2026-10-11研究Counter同値テスト追加：** 開発ブランチ `feature/v5-prior-day-counter-test-20261011` に `tests/test_v5_offline_prior_day_research_parity.py` 追加（4ケース、**隔離Pythonで4/4 PASS**）。研究元`research/v5_strong_core_calibration_pg.py`のCounter更新ASTを抽出して13種比較、2レース/2日を正例にする。**要注意：元研究の`hday`は予測対象外の正常レースも含み、個別の有効コース行も算入する。現V5モジュールは予測固定レースの完全6行のみ算入→`cs/ct/rcs/rct`で不一致となる2ケースを明示**。既存9/9テストは別の隔離stub検証、**今回の合計13/13 PASS**。実装本体・既存9件はGitHub blobと実行コピー一致。研究本体は更新部分だけの正確な抜粋を隔離使用、全リポジトリ結合未実施。ASTテストの参照位置誤り1件を開発ブランチのみ修正。
- **コース履歴採用契約の設計（2026-10-11）：** 開発ブランチに `docs/V5_COURSE_HISTORY_ELIGIBILITY_CONTRACT_20261011.md` を追加。元研究の正常結果 `hday` は予測特徴が欠損したレースも行単位算入し得るが、日付更新は予測 `days` のある日に限定。`cs/ct/rcs/rct` の履歴専用入力・6艇事故の肯定証拠・`refund_boats=None` 保留・全予測を固定してから翌日反映・収支母集団分離を規定。**設計のみ、実装・DB検証未実施**。
- **2026-10-11 実装：** 開発ブランチのみ `v5/offline_evidenced_course_history.py` と `tests/test_v5_offline_evidenced_course_history.py`（7テスト）を追加。元`roll_forward_day`をコース履歴0行で一度呼び出し、確定日次結果のあとに、別証拠で公式/非VOID/返還なし/6艇正常F/L=falseが示されたレースの有効コース履歴を翌日用4 Counterへ一度だけ集計。特徴不足レースも履歴候補、部分数値不正は行単位除外、不明・事故・重複はHOLD/拒否。予測0件日は既存freezeで拒否。監査内訳付き、Forward/BUY=false。**GitHubコミット済み、隔離Pythonで7/7 PASS（GitHubとソースハッシュ一致）。外部証拠の真正性・全レース網羅・購入収支は未証明。main/V4/Railway未変更。**
- **日次網羅性/時点証拠ガード（2026-10-11）：** 開発ブランチに`v5/offline_day_evidence_coverage.py`＋`tests/test_v5_offline_day_evidence_coverage.py`追加。隔離Pythonで11/11 PASS、GitHub blob一致(`397aff45`/`32e87b78`)。申告された全レース台帳とFROZEN/NO_BUY/PENDINGの集合差・重複・日付、6艇、展示初回取得/保存時刻と決定締切、結果初回取得の不整合を検出。事後取得を事前証拠扱いしない。**公式の独立網羅/初回証拠は一切認証不可、positive-source許可集合は空、Forward/BUY=false**。DB/本番未接続。
- 既存確認ファイル：`docs/V5_PREDECISION_FEATURE_LINEAGE_TO_REAL_ROI_20261011.md`。長い旧handoffは**履歴として残す**が次チャットで全読みしない。

- **コース履歴数値差分（2026-10-11）：** 開発ブランチに `tests/test_v5_offline_course_history_parity.py`（Git blob `40ee19e3`）を追加。隔離Pythonで6/6 PASS（元研究 `hday` 更新部分を正確に抜粋、実装/テストGit blob一致）。正常・特徴欠損・部分有効行では4 Counter一致、返還不明・重複・証拠不足では新V5が意図的にHOLD。実DBや原本真正性は未検証。

- **2026-10-11 FrozenDay台帳接続：** 開発ブランチに`v5/offline_frozen_day_evidence_adapter.py`とテスト8件を追加。実`FrozenDay.races`対申告集合の不一致/重複/艇ID不一致を拒否。買い目あり=仮想`FROZEN`、空券= `NO_BUY`、未固定= `PENDING`（購入実績ではない）。既存ガードと合計19/19オフラインPASS、py_compile PASS。GitHub blob `776bd7f1`/`45c68f43`は実行コピーと一致。`PriorDayCounters`依存のみ既存軽量stub。公式全日網羅・出走6艇・締切前取得の独立証拠は依然未確認、BUY不可。`main`/V4/Railway/DB変更なし。

- **大村12R 1件限定・read-only不足証拠分類（2026-10-11）：** `docs/V5_OOMURA_20260501_24_12_EVIDENCE_GAPS_20261011.md`作成。30履歴は前日以前だが初観測未証明、保存展示2026-08-15/オッズ2026-08-03は締切後、6艇の独立公式出走肯定証拠・V5固定買い目・返還・母集団網羅は不足、PENDING/HARD HOLD。`offline_day_evidence_coverage.py`でcutoff不明でも締切後保存を警告、模擬テスト1件を**GitHub blob一致の隔離PythonでPASS**（関連テスト12/12、py_compile PASS）。新しいDB読取なし、main/V4/Railway未変更。

## Latest ONE finding — positive official six-start source absent
限定コード監査を `docs/V5_OFFICIAL_SIX_START_FIRST_CAPTURE_PATH_AUDIT_20261011.md` に記録。historical beforeinfo は取得時 `snapshot_at=now`、reuse `source_snapshot_at` は独立初観測でない。racelist 6艇一致≠6艇出走確定。公式start-statusは肯定証拠未定義、`official_capture_pipeline` beforeinfoは**HTTP前HARD HOLD**。first-write設計/読戻しも first_observed_at=None でForward未承認。Railway/DB実状態は未確認。

**2026-10-11 公式6艇出走肯定項目を限定read-only監査：** 出走表パーサは6艇lane/登番/級別と取消表示を読み、`active_verified=False`固定。`出走`テストHTMLは合成。beforeinfoの6艇展示タイム≠6艇出走確定。既存観測pilotは`th/dt`見出し件数のみ、原本は保存せず、positive contractの許可集合は空。詳細は`docs/V5_OFFICIAL_SIX_START_FIRST_CAPTURE_PATH_AUDIT_20261011.md`追記。公式GET/DB/Railway操作なし、**HARD HOLD維持**。

- **2026-10-11既存保存証拠の限定監査：** 江戸川1Rの既存GitHub観測は匿名化hash/時刻/見出し集計のみ。原本HTML・lane/racer別肯定状態を保存せず、初観測も未認証。positive reviewed schema/approval空。監査書`docs/V5_OFFICIAL_SIX_START_FIRST_CAPTURE_PATH_AUDIT_20261011.md`追記、再HTTP/Actions/DB/Railway実行なし。**6艇肯定証拠未発見/Forward/BUY HOLD維持**。

- **2026-10-11 研究用3連単接続監査：** `docs/V5_OFFLINE_TRIFECTA_BACKTEST_JOIN_GAPS_20261011.md`を開発ブランチに作成。6艇→PL120券→指定N券→`StoredResultRow`→VOID/返還/PENDING込の仮想払戻まで純粋関数あり（合成テストあり、今回未実行）。**実DB→入力dataclass変換、全日NO_BUY/PENDING台帳との結合は未実証**。0券が収支Joinに非対応、最終オッズの直接入力なし。実ROI/締切前BUY未証明。main/V4/Railway/DB未変更。

- **2026-10-11 全日・全レース台帳＋仮想買い目統合：** dev branch `v5/offline_whole_day_research_ledger.py`（blob `5ef42718`）＋`tests/test_v5_offline_whole_day_research_ledger.py`（blob `1a780edd`、9ケース）追加。実`FrozenDay`/日次PENDING・NO_BUY含む申告inventoryを残し、仮想FROZEN ID/券順/決定cutoffと`FrozenResearchRank`を一致照合。結果は**照合後にのみ**Joinへ渡し、NO_BUY/未固定レースの結果も監査に保持。0購入日はROIなし、返還不明/結果未着は仮想ROI保留。**9/9オフライン実行PASS**。ローカル `git hash-object` とGitHub SHAが一致：`5ef42718`/`1a780edd`。払戻・結果Join・順位モジュールも実GitHub SHA一致、未使用の予測依存2件のみ軽量stub。公式全日網羅・本当の締切前券凍結は未証明、Forward/BUY=false。main/V4/Railway/DB不変更。

- **大村12R保存値→研究入力の1件限定照合（2026-10-11）：** `docs/V5_OOMURA_20260501_RESEARCH_INPUT_FIELD_MAP_20261011.md`作成。確認済みはレースID/締切参照、6艇×直近5走の前日以前の日付、後日展示順位、保存的中券`2-1-5`/払戻6,180円の内部整合のみ。未証明: 6艇の登番/級別生値、当日以前に固定の基本確率+5因子×6、model fitted-through、decision cutoff、V5選定券/点数/単価、official/VOID・返還原本、全日inventory。**ArchivedRaceFactors構築不可、StoredResultRowはPENDING、ROI未算出。** GitHubのみ、DB/Railway操作なし。

- **2026-10-11 大村12R 6艇生値抽出契約：** devに新read-only SQL `ops/v5_oomura12_six_lane_values_readonly_20260501.sql`（未実行）、NULL/重複/履歴当日リーク/日時タイムゾーンをHOLDにする純粋関数 `v5/offline_six_lane_raw_extract_guard.py` と11単体テスト（**11/11隔離PythonでPASS**。重複順位の行番号依存テストをdevで修正、Git blob SHA実装`d6603211`/テスト`3c0ce819`一致）を保存。旧集計SQLは保持。仕様 `docs/V5_SIX_LANE_RAW_EXTRACT_NULL_CONTRACT_20261011.md`。構造完全でも後日展示は研究限定、公式6艇肯定/first-observed/Forward/BUYは全てfalse。DB/Railway/main/V4未変更。

- **2026-10-11 6艇→V5研究入力境界：** devに`v5/offline_archived_input_boundary.py`/test12件を追加。前日までの`FactorVectors`・5因子×6・明示cutoff/点数/単価・SQL列allowlistを要求し、結果/オッズ列混入をHOLD。成功も研究限定・Forward/BUY=false。**隔離12/12 PASS**（未使用の既存dataclass依存をstub）、実行コピーGitHub blob一致 `2ef3970e`/`094a12a6`。DB/Railway/V4変更なし。

## Latest compact verification (2026-10-11)
- 6艇NULLガード11/11、入力境界12/12、実型接続23/23、研究式全文Parity3/3は隔離合成テストでPASS。**実DB/本当の締切前証拠/実ROIは別**。
- **全期間を最優先へ変更**。dev `v5/offline_research_period_batches.py` + `tests/test_v5_offline_research_period_batches.py`、新規9件+既存9件=**18/18 PASS**（GitHub SHA `ee392987`/`43fc4a97`一致）。2025-07-01〜2026-10-10=467日→7日単位67窓の**計画だけ完了（実データ処理0窓）**。未処理日/NO_BUY/PENDING/返還不明があれば期間ROI保留。全件揃っても研究用仮想ROIのみ。
- 詳細は`docs/V5_FULL_PERIOD_BACKTEST_FAST_TRACK_20261011.md`。2026-10-05までの旧評価範囲と10-06以降を区別。コスト$10〜12理想、$15未満優先、$20上限。Railway/DB/Actions/V4/main/BUY操作なし。

## Latest ONE result — 七日データ抽出入口（2026-10-11）
dev `ops/v5_seven_day_archived_research_source_readonly.sql`を追加。1〜7日の完了済期間を名前付きバインドし、Q1全inventory、Q2艇番1〜6＋履歴/後日展示、Q3結果・払戻を**分離**。返還/VOID肯定原本はNULL/false維持。3SELECTに7日範囲・書込命令なしを静的検査。**実DB/SQLパーサ未実行**、課金0。欠損・重複をLIMIT/DISTINCTで隠さない。詳細は`docs/V5_FULL_PERIOD_BACKTEST_FAST_TRACK_20261011.md`。

## Latest ONE result — Railway read-onlyプリフライト準備（2026-10-11）
Railway既存プロジェクト`boat-v2-postgres`/productionをREAD-ONLY列挙。Postgres4 service（history archive=SUCCESS、Postgres-EKp2=SUCCESS、V3=SLEEPING、V4=SUCCESS）、staged changesなし。**Railway connectorは任意SQL実行をサポートせず、現DB索引/型のlive値は未照会・未証明**。devに`ops/v5_seven_day_archive_db_preflight_readonly.sql`（4表の必要20列/索引prefix/SELECT権限/READ ONLY txn/2秒timeout）を作成し、書込命令なしを静的検査。現DB変更・追加DB負荷なし。7日SQLの実行はHOLD。
## Latest ONE result — 7日Q1/Q2/Q3隔離アダプタ（2026-10-11）
devに`v5/offline_seven_day_stream_adapter.py`（GitHub blob`62c56775`）と`tests/test_v5_offline_seven_day_stream_adapter.py`（8件、blob`dda19d83`）を保存。Q1母集団、Q2で6艇/前日以前履歴/展示型を確認、欠損・重複・結果列混入をPENDINGに保持。Q3は**別関数**で結果を扱い、公式返還未照合なのでROI/BUYを決して認証しない。元コードの隔離試験は実施したが、**GitHub保存版blob一致で隔離8/8 PASS・py_compile PASS（2026-10-11）**。実DB処理0/67窓、Railway/DB/main/V4/BUY操作なし。

## Latest ONE result — 7日複数場/欠損日合成テスト（2026-10-11）
dev `tests/test_v5_offline_seven_day_multi_race_coverage.py`新規10件（GitHub blob `f84dda3d`/隔離実行SHA一致）。既存8件込み**18/18 PASS**/構文PASS。2日3レース2場・Q2欠損/重複・Q3結果欠損/重複/中止・Q2への払戻混入・当日履歴混入を確認。Q1にレース行がない日は`unrepresented_days`へ保持し、**休催確定とは認定しない**。実DB0/67窓、実ROI/BUY未証明、Railway/main/V4不変更。

## Latest ONE result — 開催日/Q1欠損ゲート（2026-10-11）
dev `v5/offline_calendar_denominator_gate.py` (blob `7deb6070`) + `tests/test_v5_offline_calendar_denominator_gate.py` (`d0cbe6ff`)を追加。既存7日Q1アダプタと期間planを結合し、Q1行ゼロを**休催認定しない**、自己申告の0件開催日/予定件数とQ1の差・7日窓欠損/重複をHOLD。公式スケジュール独立真正性は未確認で`hypothetical_roi_authorized=false`。既存8+10件、新規12件、**GitHub版SHA一致で隔離30/30 PASS**、構文PASS。実DB0/67窓、Railway/main/V4/BUY操作なし。

## Latest V5 batch DB-gate status (2026-10-11)
- dev: 7日Q1/Q2/Q3、休催日分母、catalog20列/4index判定、初回1日stream上限、巨大JSONをNULL HOLDにする1日SQLまで実装。SQLは静的検証、合成試験のみ。Q3は予測Q2と分離、返還未証明。実データ**0/67窓**。Forward/BUY/実ROI HARD HOLD。
- **新最短経路**: Railway公式2026-03-20からData UIでRaw SQL利用可。dev `ops/v5_archive_catalog_railway_data_query_readonly_20261011.sql` (blob `118625fc`)はカタログのみの単一SELECTで20列/4index/SELECT権限を確認（アプリ表scan/書込なし）。Railway `boat-v2-postgres` production `postgres-history-archive` live/SUCCESS、stagedなしをread-only確認。手順 `docs/V5_MANUAL_CATALOG_PREFLIGHT_20261011.md` に記録。
- このチャットのRailway連携はSQLの直接実行不可。**ユーザーがRailway Data > Queryから単一SELECTを1回実行する必要がある**。出力1行のみ（機密URL/パスワード不要）。`SHAPE_OK_SOURCE_NOT_AUTHENTICATED`でも研究・BUYの権限には昇格しない。全期間実走のためのDB索引・型のLIVE結果は現時点で未取得。
- コスト $10–12理想、$15未満優先、$20最大。Railway Agent/AI・有料CI/Actions・DB書込・V4/main/BUY禁止。

## Latest ONE result — DB所在確認（2026-10-11）
ユーザー実行済みの`postgres-history-archive` Data Query結果: DB=`boat_history_archive`、user relations=3（`archive.v2_realtime_race_condition_snapshots`, `archive.v2_realtime_racer_condition_snapshots`, `public.v2_recent_form_archive`）、`v2_races/v2_race_entries/v2_realtime_exhibition_snapshots/v2_results`は**0/4**。この**アーカイブ専用DBに対象4表がないだけで、消失や権限不良の確証ではない**。
GitHub既存の運用記録`docs/LIVE_HANDOFF_20261007_2321_COMPACT.md`では**Historical research DB=`postgres-hobby-fullhistory-candidate-v4`**、元のProduction source=`Postgres-EKp2`。Railway live read-only metadataではcandidate-v4とPostgres-EKp2ともlive/SUCCESS/stagedなし。V4候補DBの過去空き容量が厳しいため**カタログ以外の行scan/DDL/保守禁止**。実データ0/67窓、Forward/ROI/BUY HARD HOLD。

## Latest ONE result — candidate-v4 class型の実測とV5抽出修正（2026-10-11）
- ユーザーRailway Data Query実測: `v2_race_entries.racer_class=int4` (nullable)、`racer_class_text=text` (nullable)、`racer_number=int4`。先行catalogは`racer_class`のtext想定以外19/20列、4表index/SELECT権限一致。別クエリで新text列も確認したので、**改訂版20列の型期待値は整合**（改訂版自体のlive再実行は未）。レース行/級別の中身は未照会。
- dev初回SQL `ops/v5_one_day_archived_size_guarded_readonly.sql` blob `2e2e77d4`、7日SQL `ops/v5_seven_day_archived_research_source_readonly.sql` blob `0905a3d3`: Q2は`e.racer_class_text`がA1/A2/B1/B2の時だけ`AS racer_class`、それ以外NULL→HOLD。**整数級別の推測変換はしない**。catalog UI SQL blob `96105144` / psql metadata blob `7c69a740` / offline判定 `b1ca95c5`も級別text期待に更新。初回stream SHA `fbd1466c`、手動psql SHA `0a797571`に新SQL blobを固定。Regression単体テスト3件追記（GitHub保存、**このターンPython再実行なし**）。3系統SQL分離、pin、型、DMLなしを**12/12静的検査**。DB/本番/main/V4/BUY変更なし。
- 最初の実データ確認に備え、dev `ops/v5_candidate_v4_first_day_q1_count_readonly_20261011.sql` blob `65b4145f`追加（**2025-07-01だけ**、indexed `v2_races`行数と一意レース数の1 SELECT、氏名/個別レース/結果出力なし、400件以上・0件・重複はHOLD）。静的9/9チェック、**実行は未**。実データ処理**0/67窓**、実ROI/Forward/BUY HARD HOLD。

## Latest ONE result — candidate-v4初日Q1実データ確認（2026-10-11）
ユーザーがRailway Data > Queryで`2025-07-01`をlive確認: `q1_inventory_rows=144`, `unique_race_ids=144`, `Q1_ONE_DAY_COUNT_ONLY_NOT_COVERAGE_PROOF`。重複0、400件上限内。**公式全レースの独立母集団証明ではない**。この1日Q1カウントは全期間バックテスト67窓の実処理完了とは計上しない。
devに`ops/v5_candidate_v4_first_day_q2_shape_readonly_20261011.sql` (blob `70301192`)を保存。**2025-07-01のQ1 144件/一意144を再確認した場合だけ**144×6=864 slotの出走表+historical展示を別々にindexed LEFT JOIN集計し、選手番号/文字級別/最近成績JSON型、展示欠損/重複/後日snapshotの件数を結果**1行**で表示。Q3・払戻・レースIDを表示せず、0件/重複はHOLD、Q3/ROI/Forward/BUY不可。書込/無制限全期間scanのない単一SELECTを静的8条件検査。**PostgreSQL上では未実行**、CPU/通信量は実測前、実データ処理0/67窓。

## Latest ONE result — 2025-07-01 実データQ1/Q2、展示期限検査（2026-10-11）
- candidate-v4のユーザーRailway Data UI実測：Q1=144 race/一意144、Q2出走864/864・番号864・文字級別864・recent_form容器864、重複/欠損0。historical展示864/864にrankはあるが**snapshot_atが締切後864/864**。別ラベル`learning_all`/ `final_ab`は**どちらも0件**、prospective predeadline候補0。**重要訂正**: ユーザーによれば864件は最近公式サイトから取得した過去展示で、締切後の保存日時は当然。**公式の過去直前情報として取得元/契約を照合した場合、展示をV5の事後再現シミュレーションに採用可**。日時遅延だけで除外しない。ただし締切前実観測の証明ではないため真のas-ofキャプチャ/実ROI/Forward/BUYは認証しない。
- dev`ops/v5_candidate_v4_first_day_recent_form_prior_day_readonly_20261011.sql` blob `16f977a4`を新規作成。2025-07-01のQ1=144ガード→864 entry slot限定、recent_form JSON 12KBガード、履歴1〜5件の前日以前日付・着順の欠損/不正を**一行の件数集計**で返す。Q3/払戻/展示/ID出力なし。static10/10確認。**実DB未実行**。
- 既存`research/historical_recent_form_backfill_pg.py`は過去K結果から再構築している。履歴日付が当日より前でも、オリジナルの締切前取得を証明しない。V5 real ROI/Forward/BUY HARD HOLD、全期間実走67窓中0完了。Railway Agent/AI、DB書込/Actions、本番V4/main変更なし。費用 $10〜12目標/$20限度。

## User clarification — official archived beforeinfo vs captured predeadline (2026-10-11)
既存`research/historical_beforeinfo_backfill_pg.py`は`SOURCE=official_archived_beforeinfo_historical_reconstruction`、`SOURCE_CONTRACT=BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1`、`historical_reconstruction=true`、`prospective_evidence=false`、一部synthetic`snapshot_at`を明記している。**「事後取得＝使えない」という誤認を修正**。公式に公開された当時のbeforeinfoを事後取得した事例は、**再現バックテスト研究・仮定付きROI**に使用可能。ただしDB864件それぞれのsource/contractはまだ未照合のため`official_archive_provenance_verified=false`、元の締切前取得・運用実績・真のROI・Forward/BUYは未証明。出所の違う展示と混同しない。研究全期間67窓実処理0件は変わらず。

## Latest ONE result — 7/2オッズ不足の2レース特定（2026-10-12）
- User live Railway `postgres-hobby-fullhistory-candidate-v4` Data Query: `20250702_04_09`は0/120券 (不足120)、`20250702_13_04`は2/120券 (不足118)で、**欠損238件の内訳と対象race_idが確定**。母集団2025-07-02全180レース、178レースは120券揃い計21,362/21,600。保存21,362件は全て合法一意・正数・`is_final=true`、`fetched_at`は**2026-08-13**（1年以上後の歴史取得）。両欠損レースは`PENDING_ODDS`、**収益が良く見える母集団削除、返還の推定、架空オッズ作成、無断補完はしない**。7/2の結果/正数払戻は180/180、ただし元原本・返還・当時利用可能オッズ・V5事前券凍結/ROIは未証明。
- 既存の`probe_historical_odds_reparse_pg.py`は**2026-08-18版**で`TARGET_RACE_ID=20250702_13_04`をデフォルト指定。このレースは既に旧来のオッズ再解析調査対象だった証拠。ただし同スクリプトの成功や原因は未確認。`repair_month_all_pg.py::parse_odds3t`は表形式抽出→不完全時のfallback解析を持つ。**部分保存2件の原因は公式公開可否、parser、ETL、DB入庫など未確定**。
- dev `ops/v5_candidate_v4_july02_two_odds_gaps_status_readonly_20261012.sql`（blob `c29ebb2a58`）新規。**上記2 exact race IDsのみ**をrace_id索引で参照し、`v2_races`/Q3 `v2_results`/K `v2_result_entries`事故フラグ件数と保存オッズ0/2行（2券のみ明細）を**2行**で検査。Q3情報を予測入力に渡さない。単一SELECT・静的8条件PASS、**Railway未実行**。GitHub devのみ、本番/DB/V4/購入無変更、全67窓実バックテスト**0/67**、ROI/Forward/BUY HARD HOLD。

## Next ONE task — 欠損2レースの結果/事故/保存オッズを個別診断
Railway `boat-v2-postgres > production > postgres-hobby-fullhistory-candidate-v4 > Data > Query`で`ops/v5_candidate_v4_july02_two_odds_gaps_status_readonly_20261012.sql`を**1回**実行し2行結果を共有。該当レースが通常成立か、異常/開催中止か、2件保存の内容/取得日時を区別。原因は現行SQLだけでは断定しない。データ修正・公式ネット再GETは明示検討後。Railway Agent/AI・有料CI・広域scan・DB書込・main/V4/BUYは禁止、月$10–12目標・$20上限。
`ONE_TASK_ONLY / SHORT_OUTPUT / NO_BULK_HISTORY / NO_RAILWAY_AGENT_AI / BUY_LAST`
