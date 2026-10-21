# 新競艇AI No.2 — 最新コンパクト引き継ぎ（2026-10-19 状況更新）

**唯一の最新引き継ぎ。** 古い引き継ぎ・長いworkflow・それ以前の過去チャットは履歴扱い。直前1チャットは参照可能な範囲で必要箇所のみ補助参照可。正式記録は本ファイルであり、全文大量読み込みは禁止。常に **1ターン1作業・最小tool call・短い結果報告・実行時間目安**。古いSHA・件数・使用量・runを現在値とみなさず、次の1作業に必要なものだけliveで取得。タイムアウト時は重複実行せず実行済みか確認。CI/Railwayの大量ログや全履歴検索禁止。ChatGPT内で行った模擬テストを本番結果と混同しない。

## 目的、予算、安全条件（必須）
- GitHub `kenshoushouri-cloud/boat-ai-v2` / branch `main`。**V5が唯一の主力開発対象でV4ランタイムとは独立構築。既存のV4本番・Railway DBは移行・依存確認と別途承認が済むまで保護し、V5完成を待たず不要分を撤退する方針**。V4の収益は不振だったため、V4対V5収益比較は**必須ではない**。研究の`research/`ファイル名は互換用。Railway全データ・依存関係の保全検証→不要DB/Volume/処理の安全撤去・Hobby解約→ConoHaの必要性能に増強→V5単独3連単過去収支と締切前Forward確認→安全合格後のみV5本番化。V4との本番切替を前提にしない。**自動購入は最後で別途明示承認**。本番/LINE/購入額/DB/ボリュームを無断変更しない。LINE仮候補通知は不要。
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

## 2026-10-18 運用方針・移行現況（短縮更新）
- **長期構成**：ConoHa VPSでデータ収集・PostgreSQL・V5予測/学習・定時実行を役割分離して集約。2025-07以降の履歴/原本をV5本体と分離管理し、無駄な二重保存なし、read-only参照を優先。後日GitHub Actions相当やGitHubコード管理をGit/Forgejo等でConoHaへ段階的移行。まずGitHub無料利用を残してもよく、**ChatGPTからの管理接続は別途実証**。単一VPS内のバックアップだけでは障害対策不足：外部に独立複製し復元を検証。データ元（公式サイト）・LINE等の外部通信は残る。詳細：`docs/V5_CONOHA_HISTORY_SEPARATION_20261018.md`。
- **順序/費用**：最優先はRailway完全撤退（Hobby解約）・請求を将来ゼロにすること。**2026-11-03の次期開始前**の解約を目指すが、解約は稼働デプロイを止め得るため保護完了後のみ。10/18のRailway画面では累積使用約$12.33・次回予測約$18.24（**変動する参考値**）。撤退後ConoHa 2GB→**4GBを優先検討**し負荷実測後8GB判断。不要な二重常時稼働・有料Actions・Railway Agent/AIは禁止。
- **ConoHa確認済**：TOTO 12表、V3 39表は復元と元件数一致（V3 Railwayサービス/Volume削除済）。V4はConoHa独立dump復元成功、**39表・13,640,730行**がConoHa内の元復旧DBと完全件数一致、検証用一時DB削除、空き容量約69GB（いずれも確認時）。ただし**Railway V4原本はOffline/約4.99GBで最終一致未確認**。RailwayメインDB・履歴アーカイブはConoHa保存物あり、原本との差分/網羅性・V5接続依存・外部複製の確認が未了。削除したと見なさない。10/18の旧スナップショットではDB+Volume各3組、合計36サービス（現値ではない）。無断削除・リサイズ・解約不可。
- V5前日Counter更新モジュールは10/18に`_fingerprint`構文修正をGitHub反映。テスト結果は当時の実行条件を別途確認すること。**元研究b/vrとの実数値一致・実データ因果・真の3連単ROIは未証明**。BUYは独立承認が必要。


## 2026-10-19 最新状況（古い件数より優先）
- **接続**：Termiusのboat-ai-v5-vpnからConoHaへTailscale SSH接続成功。Wi-Fi/4G/5Gで利用可能。公開IP経路・認証設定を無断変更しない。
- **移行**：ConoHa PostgreSQLメインDB railway、別履歴DB boat_history_archive、V3/V4復旧資産は保存済み。10/17独立収集の単回補完8レース/48出走/8結果をDBまで検証済み、既知会場の同日残118（未登録会場を含まない）。朝昼夜の独立定期収集は未完成。
- **10/19 Railway vs ConoHa read-only SQL照合**：Railway v2_races=71,406件（最終10/08）、v2_results=71,094件（最終10/07）。ConoHa v2_races=72,552件、v2_results=72,262件（共に最終10/17）。Railwayの最終日以前に絞ったConoHa件数は71,412件と71,268件（Railwayより+6/+174）。**件数増はレコード包含/全表完全一致の証拠ではない**。他の既存照合記録・最終差分・履歴アーカイブ/残存依存を確認する。削除は別途明示承認必須。
- **Railway live環境（10/19）**：production 25サービス、Postgres DB2と各5GB Volume計2件。cron6件はすべて2028年2月29日向け便宜的長期休止設定（0 0 29 2 *）。DBとVolumeは未削除。他の非cronサービスの依存先は未完全確認。Railway環境変数は名前のみ照会可能で接続値は不明。次期請求前の安全撤退を優先。
- **バックアップ検証**：10/18付近の暗号化ダンプ main_current_20261018.dump.age / archive_20261016.dump.age / v3_20261016.dump.age / v4_full_20261018.dump.age がConoHaとGoogle Drive上に存在。Driveリモートはgdrive_a_backup:。存在は確認したが今回の復元試験・SHA256完全照合は未実施。ConoHaでpg_dump/age/rclone/sha256sumが利用可能、空き約68GB。秘密鍵・認証情報は表示禁止。
- **10/19更新バックアップ（14:58確認、以前の未暗号化/未転送状態を上書き）**：ConoHa DB railway → main_current_20261019.dump.age 約284MB、boat_history_archive → archive_current_20261019.dump.age 約50MB、age専用鍵のパスフレーズ暗号化復旧ファイル boat_v5_key_recovery_20261019.age 371B。新規age鍵で両DBを暗号化・復号検証、鍵復旧ファイルはパスフレーズで復号し元秘密鍵とcmp一致（RECOVERY_OK）。**3ファイルすべてV5専用Google Drive v5_gdrive: 上に保存、rclone check 各1 matching/0 differences**。既存のgdrive_a_backup: にメインDBと復旧鍵も保存済み。V5専用アカウントの認証を更新し、正しいフォルダ boat-ai-v5-temp-202610/ のread-only表示を確認。認証トークンが一時写真に写ったため旧Google接続許可を取り消し新トークン発行・接続テスト成功。**認証トークン/復旧パスフレーズ/秘密鍵をチャット・GitHubへ絶対出さない**。pg_restore -l目録確認済みで実DBへのフルリストア試験は未実施。10/19 DBダンプの無暗号原本も現地に残存、外部へ平文転送禁止。\n- **外部保全方針**：当面Google Drive無料15GBを一時保存場所とし、Google One 100GB有料化はV5開発が落ち着くまで延期（未契約）。毎月1回PCから余裕のある自宅HDDに手動コピーする。照合後のみDrive旧世代整理、容量監視と転送失敗検知を設計する。ConoHaからの毎日自動バックアップは**未設定**。無断の契約、課金、消去は禁止。

- **Railway実稼働・依存（10/19 16:45頃 read-only）**：production DB2+各5GB Volume2。メインPostgres-EKp2と履歴postgres-history-archiveは各online/running 1レプリカ。非cron旧サービスのDB接続設定あり8件（v2-motor2-shadow-audit、storage-index-drop-once、tmp-date-sync-plan-20261006-EnSX、pg-snapshot-inspect、test-beforeinfo-extra、storage-maintenance-once、production-audit-readonly-2026-09-29、snapshot-audit-inspector）は最新SUCCESS/UI onlineでも**running replicas=0/1**。常時実行を示さない。DB2件のnetwork-flowログを前24時間照会して取得0件（書込なしの証明ではない）。変数名のみ取得可、接続値は不明。test-beforeinfo-extraは10/08最終deployでstartCommandがV4 wake+historical_recent_form_backfill、restartPolicy NEVER。DB/Volume/サービスは変更していない。

## 2026-10-20 方針決定とConoHa進捗（直近会話で確認）
- ユーザー承認：**現行V5の固定重み・過去採否を保護したまま、2025-07以降の取得済み全情報について、単独有効性・重み・条件間相互作用をAI/機械学習で再検証**。有望な組合せを計算量制限付きで探索し、訓練時期と未学習時期を厳密分離。締切後取得情報・当日結果のリーク禁止、6艇・事故除外は学習採否に適用し、収支母集団と区別。OOS比較で改善確認後のみ研究候補採用。本番モデル・購入設定は勝手に変更しない。AI研究完了はRailway解約の必要条件ではない。
- **ConoHa**: 10/20 07:00 JST morning、23:00 JST night の systemd timer 有効化、PRE_FLIGHT_OK・systemd構文正常。低負荷の`/opt/boat-ai-collector/daily_v5_safe.sh`で1 worker・排他・90分timeout・ODDS=0、朝は出走表/レース、夜は結果を収集する予定。**初回の実収集・DB反映・展示/オッズ収集は未確認**。初回ログ検証を優先。
- **公式返還証拠**: 2026-10-05の事故候補14件をHTML/取得UTC/SHA256/艇番でファイル保存・14/14照合OK。全期間返還可能性候補1,888件、うち7件既確認、pending初期1,881件。追加20件を1worker・5秒間隔で保存、ログの成功20/20、全保存34件（新20件SHA一括照合未了）。オッズ・払戻確定処理/全期間ROIはまだ未検証。通信エラーはPENDING、重複取得・過度アクセス禁止。
- **Railway**: 10/20 live read-only inventoryでproduction 25サービス、Postgres-EKp2 と postgres-history-archive のDB2件、各5GB Volume2件、cron6件は2028-02-29向けの休止設定。staged変更なし。ConoHaへのデータ移行の完全性・復元試験・依存解消・初回収集を確認し、**研究終了を待たずにRailway撤退**。DB/Volume/サービスの削除は対象と復旧可否を明示しユーザー承認後に限る。

## 2026-10-20 10:01 JST Railwayプロジェクト削除予約の実行証拠
- User explicitly approved irreversible deletion of Railway `boat-v2-postgres` project (25 services incl 2 PostgreSQL + 2 volumes). User personally typed exact project name and tapped Delete in Railway Danger. Screenshot after redirects to Projects shows no projects in current workspace.
- Railway deletion modal: permanent purge after **48-hour grace** (unless force deletion). No force deletion requested or performed.
- Post-action live Railway read-only verification: `describe_environment` for original project now returns **Project not found**; `environment_status` enumerates 25 original services with **offline** states, 0 failures. `list_projects` still contains the project ID/name, likely soft-delete grace/listing lag; do not call it fully erased or confirmed final invoice yet.
- ConoHa `boat-v5-daily@morning.service` on 10/20 08:56 JST ended `Result=success`, `ExecMainStatus=0`, `ActiveState=inactive`, with earlier progress 125 `v2_races`, 750 race entries. Full day coverage pending. 2GB ConoHa stays; user explicitly declined upgrade for now.
- **Next ONE task**: instruct user to view Railway Usage forecast after deletion; confirm project deletion mode/billing and whether Hobby plan should remain due other projects. Do not assert Railway subscription canceled. Then prioritize verifying ConoHa 23:00 midnight results and coverage.

## 2026-10-20 V5のミッドナイト配慮・夜間学習・4GB検討（提案、未適用）
- User accepts recommended general schedule, **explicitly requires midnight boat race support**. Official BOATRACE states last race finish around 21:40–22:50 JST, 2026-10-20 下関12R closes ~22:45. Fixed 23:00 result job may start too early; evening collection must ensure final result/payout/refund publication, retry incomplete instead of falsely marking complete.
- Proposed schedule (JST, NOT CONFIGURED): 07:00 pre-race collector; daytime through ~22:50 deadline-aware exhibitions/odds/forecast; 23:15–01:00 full results collection; 01:00–01:30 completeness retry; 01:30–05:00 batch learning/backtests only after results collection exits/completeness gate; 05:00–07:00 evaluation/preparation. Keep V5 approved model unchanged until OOS and forward validation, never compete with morning/night collector.
- ConoHa VPS official specs: 2GB=3vCPU / 4GB=4vCPU, memory doubles and aggregate CPU nominal +33%, **NOT guaranteed runtime speedup**. Current collector REPAIR_WORKERS=1, CPUQuota=70% and MemoryMax=900M, so must benchmark/tune after paid upgrade separately approved. No ConoHa plan changes made. Prioritize Railway retirement, budget, then measure whether 4GB justified.

## 2026-10-20 07:20 JST 最新優先 — ConoHa正本・不足分は公式から取得
- **ユーザー提案に同意・優先方針**: ConoHa上の既存DBを運用/研究の正本とし、不足した過去レース・結果の事実データは原則公式サイトから低負荷・重複回避で再取得。Railwayと再々照合し続ける方針は廃止し、Railway撤退を急ぐ。Railwayは復元不能な旧スナップショット証拠や最終復旧の例外的確認に限定（未だDB/Volume削除承認なし）。証拠とバックアップ、必要サービス依存を検査してから別途承認で削除。
- **時間証拠の注意**: 締切前の展示・オッズ等は事後再取得では当時取得できた事実を証明しない。取得日時、出所、再取得フラグを区別し、before-decisionに使うには当時スナップショットが必要。失われた証拠はPENDING/学習対象外として将来Forward収集で補う。事後結果/返還・払い戻しなど確定事実は公式で再取得可。
- **ConoHa日次自動収集初回**: 2026-10-20 07:20 JSTに`boat-v5-daily@morning.service`が`ActiveState=activating`で実行中。DB`public.v2_races`の当日`race_date='2026-10-20'` 60行、ログで`DEADLINE`が継続出力。実際の収集進行を確認済みだが**完了成功・結果保存・ODDS/展示捕捉は未確認**。実行中止/再起動せず、完了後にDBとログ確認。

## 2026-10-20 Railwayデータ固定方針・GitHub予定停止
- ユーザー明確方針：ConoHa移行済みDBとRailwayのデータ相違を増やさないため、**Railway向けの全自動書き込みを先に停止**する。Railway DB2台は最終照合・復元のため読み取り可能に維持し、DB/Volumeの削除は別途明示対象承認後。
- GitHub mainで**予約実行 `on.schedule` を削除した5ワークフロー**：`.github/workflows/exhibition-st-forward-scheduled-collector.yml`、`racer-course-top3-forward-scheduled-collector.yml`、`motor-guard05-forward-shadow.yml`、`candidate-discovery-v4-prospective-freeze.yml`、`bao-forward-shadow-auto-capture.yml`。元のcollectorコード・PR手動検証は保護。5ファイルを再fetchして`hasSchedule=false`確認。GitHub手動実行、issue_comment、PRによる手動/条件付き起動は一部残存、稼働中runやほかのデータ書き込み経路を排除した証明ではない。
- Railway cron6件は長期休止状態、DB2件オンライン。既存25サービスとDB参照環境変数あり。サービス停止/削除、DB停止、Volume削除は**まだ実施していない**。10/20 07:00 ConoHa初回timer実収集を確認し、DB差分を固定してから安全なRailway撤退を急ぐ。
- Railway Usage UI 10/20 06:45 JST: Current Usage $12.81, Estimated Bill $18.99 (10/03–11/03)。研究終了を解約条件にしない。

## 2026-10-20 15:42 JST V5前日結果＋直前データ収集、最新の作業指示（優先）
- ConoHa 2GB継続、Railway競艇プロジェクト削除予約（稼働25サービスoffline）。10/18=156R/936艇/156結果、10/19=132R/792艇/132結果、いずれも補完正常終了。前日結果のpendingは各0。
- 深夜の確定結果補完systemd`boat-v5-midnight-catchup.timer`をユーザーが有効化、`enabled`/`active`確認済み。01:20/02:20/03:20 JST。初回実稼働は10/21待ち。朝07:00/夜23:00日次timer稼働。
- 10/20 15:15 JST、展示/気象/オッズのrealtime table は全部0。尼崎11R 15:23 初回手動1Rで天候1,出走6,オッズ120,展示0(公式欠落)。15:35再取得は公式HTTP read timeout 8sec×2で0。curl -4の両URLは各8.1~8.25秒でHTTP200、通信遅延。15:41 桐生2R `20261020_01_02` をHTTP_TIMEOUT=20で厳格限定1R再取得したところ**展示6, オッズ120,天候1,選手6,レース条件1**を公式から締切前に取得保存成功。自動購入・モデル変更なし。ユーザーは別途17:35桐生6R最終判断リマインダ通知予定。
- GitHubに新規`v5/conoha_realtime_window_pg.py` / `tests/test_v5_conoha_realtime_window_pg.py` / `deploy/conoha/boat-v5-forward-window.{service,timer}` を作成。既存`v21_realtime_collector_pg_safe.py`を**V5_STRICT_PREDEADLINE=1時のみ**通信前後の厳格deadline（3minガード）とofficial odds以外のfallback禁止に拡張。read-only previewがデフォルト、applyは`V5_ENABLE_LIVE_COLLECTOR=YES`必要、2件/回・締切9〜24分前、5分毎の07〜23 JST timer案、同一lock/CPU50%/RAM750MBの設定、snapshot_label別時間証拠を上書きせず保存。**GitHub追加のみ、ConoHa未配備・テスト未実行、timer未設置/未有効化。** 実行前にunittestとsystemd verifyを必ず実施。既存DB、V5モデル、購入/LINE、2GB契約は保護。
- **Next ONE task**: Termiusで`git diff --quiet && git diff --cached --quiet && git fetch origin main && git merge --ff-only FETCH_HEAD`後、`/opt/boat-ai-v5-venv/bin/python -m unittest discover -s tests -p test_v5_conoha_realtime_window_pg.py -v` と `systemd-analyze verify deploy/conoha/boat-v5-forward-window.service deploy/conoha/boat-v5-forward-window.timer` を行い結果を確認。timer即時有効化はしない。失敗やschema差は診断して修正、繰返し大量DB参照はしない。

## 2026-10-20 Telegram V5試験配信・日次/月次成績（最新優先）
- ユーザーはTelegramを通常の無料試験通知先、既存LINEを重要時だけの予備として了承。LINE月間無料上限を尊重し、この段階でLINE実送信しない。Botトークン/Chat IDをChatGPTへ貼らせず、GitHubにも入れない。ConoHa保護ファイルで今後設定する。
- 既存Railway `v28_daily_status_report_line.py`/`v27_performance_report_line.py` は古い `v2_realtime_decisions` を集計し1点100円等の旧前提を含むため**V5実績として流用不可**。
- GitHub `v5/telegram_trial_transport.py` を追加：1通ずつのTelegram Bot API、DRY_RUNデフォルト、明示`--send`と`V5_TELEGRAM_SEND=YES`が揃わない限り絶対送信しない、429 retry_after制限、秘密値はログ非表示。`v5/telegram_trial_performance.py` を追加：V5専用の予想時点証拠と公式結果・払戻証拠があるJSONLだけを日次/月次に集計。未確定は母数から除外し表示、的中率/回収率/収支、仮想と実購入は別集計。元データ未連携では「算出不可」、偽の0%なし。`tests/test_v5_telegram_trial_reports.py` に隔離した9本のunittest追加。**GitHub作成のみ、テスト実行・ConoHa反映・Bot開設・実配信・レポート定期実行は未実施。** Ledger作成/配信条件実装は今後。想定配信：前日対象＋当月累計を毎朝約05時(JST)・前月確定分は毎月1日朝、未確定は暫定を明記。
- 10/20桐生6RはConoHa側で締切前17:30台の展示6/odds120を保存済み。ChatGPTへ未連携だった問題を解消すべく、配信をConoHa内で完結させる。
- **Next ONE task:** TermiusでConoHa `/opt/boat-ai-v5`のGitHub `main`を安全にfast-forwardし、`/opt/boat-ai-v5-venv/bin/python -m unittest discover -s tests -p test_v5_telegram_trial_reports.py -v` を読み取り専用で実施。修正が必要ならGitHubで直す。Bot開設はユーザー操作、実送信や秘密情報投入はテスト後の別作業。


## 2026-10-21 直近結果保存先の分離（確認済）
- ConoHa `railway` DBで10/07〜10/20の`v2_races`=1,860件、`v2_results`に結果1,570件、1,570/1,570件が`v2_race_entries`の6艇にjoin可能。一方、同期間の選手別`v2_result_entries`は**0行**。`official_k_file`の選手別結果は10/06まで422,544行・1,649選手。10/20の`v2_race_entries.recent_form`は864/864空。
- GitHubコード確認：日次オンライン収集`repair_month_all_pg.py`は`v2_results`へ保存。公式Kファイル由来の全6艇着順を`v2_result_entries`へ保存するのは**別経路**`save_k_day_results_pg.py`（対象1日・全6艇パース監査・明示書込ゲート）。現行ConoHa日次`daily_v5_safe.sh`は前者のみを呼ぶ。**実装と運用経路の未接続が原因候補**。バージョン差/引き継ぎ漏れだけが原因と断定しない。
- `research/historical_recent_form_backfill_pg.py`は公式Kの予測対象日より前の日付の記録のみで直近5走を再構成できるが、デフォルトread-only・書込は明示許可制。3連単上位3艇から4〜6着は捏造禁止。過去原本の後日取得を当時の締切前証拠に転用禁止。
- 次の1作業：ConoHaで10/07以降のKファイル**既存原本の有無をread-only確認**し、日別の公式K監査→不足日だけ安全な低負荷追加取得を検討。勝手なDB書込/大量取得/旧V5重み変更/実BUYは禁止。

## 2026-10-21 最新合意 — V5データ再編成を構築より先行
- ユーザー希望により**V5専用データ管理への再編成を最優先**とする。旧データを一括コピー・移動・削除するのではなく、ConoHa PostgreSQL内の独立した`v5_data`参照層/必要時だけ`v5_research`予測研究層を用意し、旧`public.v2_*`を引き続き正本として監査しながら安全移行する。
- 設計正本: `docs/V5_CANONICAL_STORAGE_REORGANIZATION_20261021.md`。DBにまだ新schemaを作成していない。追加課金/再起動/大量コピーなし。既存ConoHa `railway` DBと`boat_history_archive`、過去の暗号化Driveバックアップ・固定V5モデル/朝夜・Forward収集は保護。
- **Next ONE task:** ConoHaでread-onlyのschemaと主要テーブルの保存容量を棚卸しして、最小のVIEWベースのV5アクセス層DDLを決定する。DBのCREATE/ALTER/書込/削除は別の具体的承認後。

## 2026-10-21 V5データ専用参照層の実適用（スクリーンショット確認済）
- ConoHaローカル`railway` DB に`deploy/conoha/v5_data_views_v1.sql`→`v5_data`6非更新VIEW、`v5_data_views_v2.sql`→`v5_data`追加4 VIEWと`v5_research`1 VIEWがCOMMIT済み。`is_updatable=NO`全11。大量データCOPY/旧データ移動・削除なし。全DB 3414MB（作成時点）。
- 263MBの`v2_v24_motor2_forward_shadow`は`v5_research.motor2_legacy_shadow`で隔離。本番V5の`motor_stats`として採用しない。気象等4元表は`v5_data`参照別名のみ、締切前取得証明/モデル採用は未検証。
- 具体的設計: `docs/V5_CANONICAL_STORAGE_REORGANIZATION_20261021.md`。**Next ONE task:** 選手級別/履歴・モーター正本の元列と日時をConoHaでread-only確認、取得済み過去結果の空白（10/07以降K）を補完する方式を決める。既存モデル固定・タイマー/バックアップ/Railway保護。


## 2026-10-21 公式K結果の欠落13日・バッチ事前監査
- ConoHa `railway`: 10/20 K取り込み1日144R/864艇、通常着順850+事故14を`save_k_day_results_pg.py`で`v2_result_entries`へ保存・`v2_results`144件補完、SQLで144Rすべて6艇完備を確認。書込前`v2_results`単表ダンプ`/root/v2_results_pre_k_20261021.dump` 3.3MB、目録読める、完全復元試験ではない。
- 10/07〜19（13日間）の直近SQL：登録済レース全件に結果があるのは**9日**（10/07,09,10,11,12,13,14,18,19）、計**1344レース**。詳細選手結果はその13日間で0。結果不足は10/08=144、10/15=124、10/16=21、10/17=1、計**290**件。10/17レース数51、10/16は21で登録自体の完全性は未検証。
- GitHubに`deploy/conoha/k_results_batch_preflight_20261021.py`を追加（コード作成のみ）。対象の9日を1日ずつ公式K取得・全レース6艇/重複なし/パースエラーなし・`v2_races`と`v2_results`で公式ID完全一致・既存詳細0件を照合し、DBはread-only強制・無書込。**ユーザーConoHa実行はまだ未検証。** Next ONE task：TermiusでGitHub fast-forward後にこのスクリプトを実行しPASS/BLOCKの日付を報告。結果欠損の4日は自動DB登録禁止、別の収集保護タスク。成功9日への書込は再度別許可・バックアップ後に小分け実施。

## 2026-10-21 K一括事前監査9日 全PASS
- ConoHaで`deploy/conoha/k_results_batch_preflight_20261021.py`をユーザーが実行。`PREFLIGHT_DONE ready=9 blocked=0`：10/07,09,10,11,12,13,14,18,19の公式Kファイル9日1,344R（予定8,064艇）で全日公式レースIDと保存済み`v2_races`/`v2_results`一致・6艇完備・既存`v2_result_entries`=0、DB_WRITES=0。権限修正は対象py1ファイルだけchmod644済み。
- `save_k_day_results_pg.py`のGitHubコード確認: `CONFIRM_K_DB_WRITE=YES`必須、日別に既存v2_results全R確認、INSERTするのはv2_result_entries、v2_resultsは`coalesce`でNULL項目補完、transaction内POSTWRITE検査。**Next ONE task:** 9日一括書き込みに備えConoHaローカル`railway`の`v2_results`と`v2_result_entries`を新しい単一`pg_dump -Fc`としてバックアップ→pg_restore目録検査。直近の10/20用v2_results単表バックアップだけでは9日一括書込の保護として不足。バックアップ検証前はバッチ本番書込禁止。実書込9日は日別トランザクション/失敗時中断、データ転送によりライブ収集負荷を抑える。


## 2026-10-21 10:35 JST 公式K一括事前検査9日PASS
- ConoHa Termiusで `deploy/conoha/k_results_batch_preflight_20261021.py` をread-only実行。`PREFLIGHT_DONE ready=9 blocked=0` を2026-10-21 10:35 JSTにユーザー画面で確認。各日公式Kステータス200、レースIDが既存`v2_races`/`v2_results`と完全一致、6艇完備、parse不良/重複/既存`v2_result_entries`なし。対象9日（10/07,09,10,11,12,13,14,18,19）計1,344レース×6艇=8,064選手別詳細結果を補完可能と判定。**DB書込は未実施。**
- 初回は`postgres`から検査プログラムが`-rw------- root root`で読めずpermission denied、該当ファイルのみ`chmod 644`して解消。GitHub再アップロード不要。現行OSが再起動要求中だが再起動は未指示、勝手に実施しない。
- Next ONE task: **一括書込前にConoHaローカル`railway` DBの`public.v2_results`と`public.v2_result_entries`の一貫性ある安全なバックアップを確認/作成**（前回`/root/v2_results_pre_k_20261021.dump`は10/20補完前の単表3.3MBの目録検査だけ）。その後、対象日を1日ずつ`save_k_day_results_pg.py`で保存→各日6艇/既存結果/払い戻しの監査。保護条件を満たしてから9日を順次継続。結果自体が不足する10/08(144件)、10/15(124)、10/16(21)、10/17(1)は別工程・安全装置を解除しない。直近5走の`recent_form`はこのK保存だけでは埋まらず別途as-of検証が必要。

## 2026-10-21 13:51 JST K公式履歴補完の確定状況（旧逐次報告を圧縮）
- ConoHa `railway` 4表(`v2_races/v2_race_entries/v2_results/v2_result_entries`)事前保全: `/root/boat-v5-backups/k_recovery_4tables_20261021_123041.dump` 57MB、pg_restore目録4表+SHA256 PASS。前段2表保存`k_results_pre9_20261021_115208.dump`23MBも保護。完全復元試験/外部複製は未実施。
- 公式Kの2026-10-07,09,10,11,12,13,14,18,19の**9日/1,344R/8,064艇**は`v2_result_entries`保存済み。全日6艇整合性read-only監査PASS、重複保存は防止済み。直近5走`recent_form`は未補完。
- 4日(10/08,15,16,17)の初期DB登録済みレースの結果欠損**290R**(144,124,21,1)を確認。公式K比ではさらに10/16未登録135R・10/17未登録117Rが判明(計252R)、10/16戸田5R `20261016_02_05` 出走0艇を公式HTMLから6艇INSERT補完済。公式K各日は6艇/重複/parse監査PASS。後日HTML/K取得を締切前証拠として流用しない。
- 10/16の完全未登録17Rは安全な3表新規INSERTで回復。戸田6〜12R `20261016_02_06..12` + 江戸川1〜10R `20261016_03_01..10`。最初は1件、以降3件→6件→6件を個別atomic処理、全て公式6艇+3連単整合・DB readback PASS。**10/21 13:51実測**: 10/16 `v2_races=38, v2_race_entries=228, 異常6艇=0, v2_results=17`(`AFTER=38:228:0:17`)。従って公式K基準未登録残**235R**(10/16=118、10/17=117)。初期290の既存登録結果欠損は別工程で残存。新規17Rの`v2_result_entries`詳細着順は未補完。再実行禁止の既処理IDを尊重する。
- GitHub `deploy/conoha/k_missing_races_insert_only_20261021.py`: 公式K ID/6艇/3連単金額と当日公式HTML比較、既存4表に1件でもあれば対象外、新規のみ3表atomic INSERT、最大6R、明示`--apply`+`CONFIRM_V5_K_RACE_REPAIR=YES`、デフォルトread-only、1worker/2秒間隔。既存`repair_month_all_pg.py`は既存行upsertするため本用途に直接使わない。
- GitHubに`deploy/conoha/k_missing_races_bounded_runner_20261021.py`を**新規作成（commit c8c1d98）**。1〜2バッチ×6R、read-onlyデフォルト、明示書込二重ゲート、実行ロック、各バッチ前後のDB6艇/結果差分検査と異常停止。**ConoHaにはまだ反映せず、構文/ドライラン未検証、追加DB書込なし**。
- **Next ONE task:** Termiusで`/opt/boat-ai-v5` clean/git ff-only → bounded runner `py_compile` → `--day 2026-10-16`（`--apply`なし）のread-only動作検証。初回applyは結果確認後に別指示。ConoHa2GB、既存タイマー・バックアップ・固定V5重み・Railway無変更。費用抑制、公式取得は1worker。

## 2026-10-21 17:15 JST 10/16公式Kレース本体・出走表が全件完成
- ConoHa `railway` 10/16公式K156Rについて `v2_races=156 / v2_race_entries=936 / bad6=0 / v2_results=135`。Termius検証：`BEFORE=(152,912,0,131)`→`AFTER=(156,936,0,135)`、`DELTA=(4,24,0,4)`、最後の4R(24_09..12)それぞれ`DAY_RACE_PASS`、`BATCH_PASS wrote=4`、`BOUNDED_BATCH_PASS`、予定通り`PARTIAL_BATCH_STOP`、`BOUNDED_RUN_DONE`、`OCT16_RACES_COMPLETE`。10/16レースと出走艇登録は全件完成、登録済み21Rの結果欠損と全選手別詳細着順は別工程。
- 当初の10/16,17未登録レース252Rのうち**135R補完済み**（10/16全件）、**残117R（10/17のみ）**。初期登録済みレースの結果欠損合計290R（10/08=144、10/15=124、10/16=21、10/17=1）はまだ別工程。取得した歴史データを当時の締切前データと混同しない。
- 差分復旧は `deploy/conoha/k_missing_races_insert_only_20261021.py` と `deploy/conoha/k_missing_races_bounded_runner_20261021.py` のみ。K/HTML照合、既存4表ID保護、1R毎原子INSERT、最大6R×2バッチ、デフォルト読み取り専用、`--apply`+`CONFIRM_V5_K_RACE_REPAIR=YES`の二重書込ゲート、排他/6艇件数検査。既存の無条件upsertは禁止。
- 保護: 4表バックアップ`/root/boat-v5-backups/k_recovery_4tables_20261021_123041.dump`57MB+TOC/SHA256 PASS（復元試験未実施）。公式K詳細9日1,344R/8,064艇も検査済み。ConoHa2GB低負荷、既存自動収集/バックアップ/V5固定モデル/Railwayは変更しない。OS再起動要求が出ているが再起動は未実施。
- **Next ONE task:** 下記17:18 JST最新状態を参照。

## 2026-10-21 17:18 JST 10/17公式K read-only preview PASS
- Termiusで10/17の安全事前検査成功。DB `v2_races=51,v2_race_entries=306,bad6=0,v2_results=50`、公式K HTTP200・168R、`ABSENT_ALL_FOUR=117 ELIGIBLE_STANDARD=117`、dry-run候補 `20261017_03_12,04_07,04_08,04_09,04_10,04_11`。 `DRY_RUN_DONE_NO_DB_WRITES`, `BOUNDED_DRY_RUN_OK_NO_DB_WRITES`, `OCT17_PREVIEW_PASS`、DB変更なし。
- **Next ONE task:** 17:22の最新状態を優先する。

## 2026-10-21 19:18 JST 290結果欠損のread-only検査・誤日付修正（最新）
- 10/16,17未登録252Rと出走6艇情報は全件復旧済。日別v2_races LEFT JOIN v2_results read-only: 10/08=144/0/144、10/15=156/32/124、10/16=156/135/21、10/17=168/167/1（race/result/missing）、計結果欠損290R。
- 公式K vs DBの新read-only preflight初回は10/08で安全停止。`K=144 RACES=144 RESULTS=0 MISSING=144 K_ID_DIFF=288 BAD_ROSTERS=144`。ログのK側IDに`20260816_01_01`などがあり、元の`audit_k_day_all_pg.py`がグローバル`TARGET_DATE`(default 2026-08-16)でrace_idを生成するのに新preflightが日別に更新していなかったのが原因。**DB破損の証拠ではなく、初回はDB書込みなし**。
- `deploy/conoha/k_missing_results_preflight_20261021.py`を修正済（GitHub commit `0cb995e`）：K parse前に`ka.TARGET_DATE = day`、生成race_idが当日日付接頭辞であることを強制チェック。既存6艇/選手番号・DB結果衝突・非標準払戻検査、DB read-onlyを維持。**ConoHaには未反映・修正後は未実行**。旧`save_k_day_results_pg.py`は結果行の新規INSERTに使わない。
- ConoHa2GB・4表バックアップ57MB/SHA256+TOC PASS（復元試験未実施）、既存収集/バックアップ/V5固定ウェイト/Railwayの無断変更・停止・再起動・削除なし。後日取得を事前予想証拠へ混入させない。
- **Next ONE task:** Termiusで短い1行`git -C /opt/boat-ai-v5 pull --ff-only && cd /opt/boat-ai-v5 && runuser -u postgres -- env HTTP_TIMEOUT=20 /opt/boat-ai-v5-venv/bin/python deploy/conoha/k_missing_results_preflight_20261021.py`を一度だけ実行。期待K_ID_DIFF=0、TOTAL_MISSING=290。その他の不一致が残ればDBに書かずログを確認する。
