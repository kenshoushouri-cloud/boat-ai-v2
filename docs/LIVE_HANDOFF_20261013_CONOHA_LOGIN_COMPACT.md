# 新競艇AI No.2 — current compact handoff (2026-10-14 JST)

## 運用・引き継ぎ原則
Repo `kenshoushouri-cloud/boat-ai-v2`、作業branch `feature/v5-prior-day-counter-test-20261011`。**main/V4本番の変更禁止**。開始時は`docs/HANDOFF_LATEST.md`→本ファイル→`docs/NEXT_CHAT_START_HERE.md`のみ。旧handoff/PROJECT_HISTORY/長いworkflow/ログは大量参照せず、必要時に末尾の個別資料を読む。**1回1作業・短い結果・所要時間の目安・少数tool call**。SHA/run/DB容量は必要な場面だけlive再取得。利用者は**iPhone SafariとiSHのみ**。本書は追記で肥大化させず毎回古い進捗を置換する。

## 目的・構成
- **強化型V5を主力**に公式出走/選手/級別/調子/コース/モーター（交換直後は小標本に注意）・展示/ST・気象・オッズを収集。採用する特徴量は2025-07-01以降のバックテストで精度/ROI改善を検証。不採用データも将来のため保管する。V4判定を無検証で転用しない。
- 正確な締切前証拠の凍結→V5予測→競走後の結果監査→67週OOSバックテスト→実Forward検証の順。**自動購入は最後に別承認（BUY HARD HOLD）**、LINE仮候補通知不要。月利益目標+5万円は**未立証**。
- 最終構成は**購入済みConoHa VPS 2GBにV5のDB・公式収集・予測・cron・監視・低負荷バックテストを一元化**、GitHubはコード/履歴、VPS外に暗号化バックアップ。旧Railway/Actions収集障害の個別修理を優先しない。RailwayのV4本番と4DB原本は安全な移行完了まで保護。

## 現状・確定した保留点（10/14）
- **ConoHa**：10/13に2GBサービス申込完了・支払確認メールあり。Safariログイン後も申込/支払い画面に戻り、管理画面/OS/IP/SSH/実機容量**未確認**。サポートへ連絡済、10/14 Gmail再確認でも返信未着。**再購入/再チャージ禁止**。Ubuntu24.04LTSは推奨であり実際のOSは不明。
- **V5の精度**：2025-07-01〜2026-10-10の67週間OOS計画は**実行0/67、実ROI/収益未検証**。7/2の180レースでオッズ238券不足、PENDING。締切後に取得した展示/オッズ・日付だけ同じ履歴を締切前観測と偽らない。欠測/返還不明/NO_BUY/PENDINGを勝手に埋めたり母数から外したりしない。
- **実装準備のみ**：`ops/conoha/v5_offline_dag.py`論理DAG20/20 PASS、`ops/conoha/v5_serial_resource_guard.sh`の重複起動/時間/資源9/9＋権限/シンボリックリンク11/11 PASS。GitHub既存writer/cron候補11ファイル・28コード根拠を静的照合し、`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`へ記録。**現行Railwayの稼働cron、V5 writer結線、VPS実機運用は未確認**。featureに`ops/conoha/v5_writer_lock_static_check.py`＋`test_v5_writer_lock_static_check.py`を追加、ローカルoffline 18/18 PASS。**宣言JSON上のwriter argvだけ検査**し、実cronや宣言漏れは未検証。既存PRE通知/旧v25 final入口をV5に丸ごと流用しない。
- **バックアップ**：4DB暗号化取得スクリプト既定無通信、モック75件＋中断11件＋ローカル3点(.dump.age/.sha256/.ready)照合21件PASS。すべて**オフライン模擬検査のみ**。現行4DBの実暗号化外部バックアップ**0/4**、独立フル復元**0/4**。archive/V4/V5用復元鍵の固定照合未完→実バックアップHOLD。本人の実`age`復号も未検証。iSHは独自Alpine3.14リポジトリに`age`がなくインストール失敗；OS/取得先を無理に変更しない。
- **旧CMS資産**：10/1の暗号化GitHub artifact3件は12/30失効予定。うち約302.7MBの1件を本人がDrive Aへコピー済、SHA/独立復元未検証。**現在の4DBバックアップを代替しない**。Railway `archive-restore-key-20261001` とCMS秘密鍵/過去artifactを保護。

## Railway 4DB / 外部保管先（取り違え禁止）
|対象|原本サービス|暗号化コピー先|
|---|---|---|
|旧V3（休止・wake費注意）|`postgres-hobby-fullhistory-candidate-v3`|非共有Google A / V3専用|
|履歴archive（公開TCP無し）|`postgres-history-archive`|非共有Google A / archive専用|
|**V4本番**（公開TCP無し）|`Postgres-EKp2`|非共有Google A / V4専用|
|**V5研究**（サービス名はv4）|`postgres-hobby-fullhistory-candidate-v4`|非共有Google B / V5専用|

Google A/Bのrclone OAuthは未完（iSH Safari localhost callback失敗）。**元DB/cron/秘密鍵サービス停止・削除禁止**。まず各DBの全量暗号化コピー→再取得SHA照合→本人鍵で全体復号→**独立した隔離PG18への全復元/同時点データ照合**→ユーザー個別承認。2025-07-01以降の原本を保全。復元用Ed25519秘密鍵・passphraseは本人iPhone/iSH/iCloud側のみ、公開鍵だけGitHub；秘密/DB URL/OAuth tokenをチャットやGitHubへ貼らない。

## 工程と目安（T0＝既存ConoHa VPSのアクセス復旧日）
**当初の2026年10月中旬運用開始目標は、未復旧/未バックアップ/未OOSのため確約不可。** 下記は依存条件が満たされた場合の暫定見込み。
1. **T0前（現在）**：GitHub feature上でV5 writer/cron共通ロックの静的検査・無課金offline testsを実施。ConoHaサポート回答待ち。
2. **T0〜1日程度**：既存2GBのOS/SSH/CPU/RAM/diskを`ops/conoha/v5_host_preflight_readonly.sh`で実測、本人承認で初期設定。安全なホストで一時鍵による実`age`往復→本人鍵のローカル復号確認。
3. **T0後、数日〜容量/認証次第**：Drive A/B本人OAuth、4DBを**1DBずつ**暗号化退避、外部全体SHA＋隔離フル復元。同期間のRailway停止なし、通信費/起動も事前承認。
4. **バックアップ検証後、数日〜数週間**：V5出走→締切前公式情報/オッズ→証拠gate→shadow予想→公式結果→監査を直列化し、2025-07以降67週OOS・Forward精度/ROI・負荷を測定。欠測はそのまま扱う。リアルタイム取得と重いバックテストを同時実行しない。
5. **十分な検証後**：費用/復旧性/精度を確認、別承認でRailwayの段階縮退。4GB増強は**2GBの実測とRailway費解消後**に必要なら別承認。自動購入は最後。

## 費用と絶対HOLD
ChatGPT＋Railwayは理想月5,000円以下、目安上限6,000円；Railwayは可能なら月$10〜12、$15警戒、$20超回避。**ConoHa/外部保存/二重稼働も総額で評価**。CPU/RAM/Network/WAL/CIを節約、Railway Agent/AI禁止。無承認のmainマージ・V4本番変更・本番cron変更・DB wake/接続/転送・課金・4DB原本/旧CMS鍵削除・BUY禁止。

## Next ONE task
**ConoHaサポート返信をまず確認**。復旧なら**再購入せず**read-only VPS診断。未復旧なら既存のwriter/cron静的監査と新チェッカーの**宣言JSON入力範囲・漏れリスク**をfeature内で読取専用照合する1作業。実cronの設定確認・writer結線・DB/Secrets/外部通信/BUYは触らない。

## 詳細資料（必要時だけ）
`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`、`docs/V5_CONOHA_SERIAL_DAG_CONTRACT_20261014.md`、`docs/V5_CONOHA_2GB_RAILWAY_MOVE_PREFLIGHT_20261013.md`、`ops/backup/BACKUP_SAFE_MODES_20261014.md`、`ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`、`ops/backup/ISH_AGE_OFFLINE_OWNER_TEST_20261014.md`。
