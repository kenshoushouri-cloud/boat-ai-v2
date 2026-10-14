# 新競艇AI No.2 — current compact handoff (2026-10-14 JST)

## 運用・引き継ぎ原則
Repo `kenshoushouri-cloud/boat-ai-v2`、作業branch `feature/v5-prior-day-counter-test-20261011`。**main/V4本番の変更禁止**。開始時は`docs/HANDOFF_LATEST.md`→本ファイル→`docs/NEXT_CHAT_START_HERE.md`のみ。旧handoff/PROJECT_HISTORY/長いworkflow/ログは大量参照せず、必要時に末尾の個別資料を読む。**1回1作業・短い結果・所要時間の目安・少数tool call**。SHA/run/DB容量は必要な場面だけlive再取得。利用者は**iPhone SafariとiSHのみ**。本書は追記で肥大化させず毎回古い進捗を置換する。

## 目的・構成
- **強化型V5を主力**に公式出走/選手/級別/調子/コース/モーター（交換直後は小標本に注意）・展示/ST・気象・オッズを収集。採用する特徴量は2025-07-01以降のバックテストで精度/ROI改善を検証。不採用データも将来のため保管する。V4判定を無検証で転用しない。
- 正確な締切前証拠の凍結→V5予測→競走後の結果監査→67週OOSバックテスト→実Forward検証の順。**自動購入は最後に別承認（BUY HARD HOLD）**、LINE仮候補通知不要。月利益目標+5万円は**未立証**。
- 最終構成は**購入済みConoHa VPS 2GBにV5のDB・公式収集・予測・cron・監視・低負荷バックテストを一元化**、GitHubはコード/履歴、VPS外に暗号化バックアップ。旧Railway/Actions収集障害の個別修理を優先しない。RailwayのV4本番と4DB原本は安全な移行完了まで保護。

## 現状・確定した保留点（10/14）
- **ConoHa 10/14 ブラウザーコンソール進捗**：VPS Ver.3.0既存`boat-ai-v5-main`1台**起動中/2GB/CPU3Core/SSD100GB**、本人画像から**Ubuntu 24.04.3 LTS tty1**表示確認。本人がrootパスワードを設定済み、**コンソールにパスワードを入力し「完了」と報告**したが、**シェルの`root@...#`表示はまだ未確認**（認証成功を確定しない）。次は本人がshellプロンプトを確認できた場合のみread-only `free -h`を1回実行、結果はMem/Swap値だけ報告。`login:`/`Password:`/`Login incorrect`なら実行せず状態報告。IP・UUID・ホスト名・鍵・パスワード・会員情報はGitHub/チャットに記載しない。ConoHa有効期限11/13・自動更新ON・自動バックアップOFFは無変更。VPS負荷/ディスク・SSH・復元未検証。追加課金・再起動/再構築禁止。
- **V5の精度**：2025-07-01〜2026-10-10の67週間OOS計画は**実行0/67、実ROI/収益未検証**。7/2の180レースでオッズ238券不足、PENDING。締切後に取得した展示/オッズ・日付だけ同じ履歴を締切前観測と偽らない。欠測/返還不明/NO_BUY/PENDINGを勝手に埋めたり母数から外したりしない。
- **実装準備のみ**：`ops/conoha/v5_offline_dag.py`論理DAG20/20 PASS、`ops/conoha/v5_serial_resource_guard.sh`の重複起動/時間/資源9/9＋権限/シンボリックリンク11/11 PASS。GitHub既存writer/cron候補11ファイル・28コード根拠を静的照合し、`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`へ記録。**現行Railwayの稼働cron、V5 writer結線、VPS実機運用は未確認**。featureにwriter共通ロック静的checker＋18件のテスト定義を追加（本ターンの実テスト実行なし）。`docs/V5_CONOHA_CRON_ACTIONS_ENTRYPOINT_SCOPE_20261014.md`でworkflow345件中関連11件を限定静的照合：**旧研究のschedule付きwriter2経路はmain/feature同一、DRY_RUN=0、ConoHa共通flock不使用**。10/12〜14 UTCのmain定期runは対象計**10件（展示ST7・選手コース3）、全件failure**、各11〜18秒/合計144秒はメタデータ経過時間。直近2件はStep6 DB URL取得失敗→収集Step7 skipped。repo public＋標準Ubuntu runnerのため**Actions runner分の追加料金0**（artifact等別）。根本原因/実DB書込は未検証、V5本番HOLD。`docs/V5_PREDEADLINE_FREEZE_ENTRY_STATIC_AUDIT_20261014.md`：beforeinfo**HTTP前HOLD**、6艇肯定出走証拠なし・prewrite gateも拒否。racelist/K保存も前時点証明なし、Forward=False。`v5/test_capture_entry_forward_hold_offline.py`は**隔離Python 3.13で16/16実動作PASS**（初回7件のモック例外設計不備を修正、原本/テストのGit blob一致）。AST入口＋fake HTTP/DB限定で、実取得・DB格納やROIは未検証。本番未配線。旧PRE/旧v25 finalをV5へ流用しない。
- **バックアップ**：4DB暗号化取得スクリプト既定無通信、モック75件＋中断11件＋ローカル3点(.dump.age/.sha256/.ready)照合21件PASS。すべて**オフライン模擬検査のみ**。現行4DBの実暗号化外部バックアップ**0/4**、独立フル復元**0/4**。archive/V4/V5用復元鍵の固定照合未完→実バックアップHOLD。本人の実`age`復号も未検証。iSHのAlpine3.14独自repoでは`age`導入失敗；環境改変禁止。V3本人鍵テストを安全強化（ローカル鍵パス/権限/リンク拒否/trace禁止）、`test_v3_recovery_key_local_guard_offline.py`のダミー鍵模擬**16/16 PASS**。`docs/V3_OWNER_AGE_RECOVERY_KEY_OFFLINE_REVIEW_20261014.md`に記録。V3公開鍵SHA固定一致、本人秘密鍵/実age復号は未検証（iSH ageなし）。archive/V4/V5の公開鍵ピン、Drive A/B OAuth、独立PG18/同時点照合未了（4DB実退避/復元0/4）。
- **旧CMS Drive転送preflight（10/14）**：GitHub暗号化CMS ZIPは未失効**4件**、Google A非共有V3フォルダに1件/302,656,753bytesあり、未保全候補**3件907,134,932bytes**。Drive A全体残容量はconnectorから不明、本人確認が必要。約300MB/件のGitHub→Drive直接受渡し/費用は未実証のため転送HOLD。**旧CMS ZIPサイズ/SHA256照合のローカルread-onlyツール**`ops/backup/verify_legacy_cms_zip_offline.py`を追加、ダミー**14/14 PASS**（GitHub保存blob一致）、**実ZIP 0件照合**。ZIP照合≠CMS復号/復元/Drive遠隔一致。4DB実バックアップ/復元**0/4**。詳細`docs/LEGACY_CMS_ARTIFACT_TRANSFER_PREFLIGHT_20261014.md`。 **V5追加試験**：`v5/test_first_write_readback_failclosed_offline.py`を追加、GitHubの実readback関数AST＋ダミー行で**19/19 offline PASS**、SHA一致。時刻矛盾/重複/内容・digest衝突を拒否し、正常でもForward不可。SQL executor本体は未動作検証（`docs/V5_PREDEADLINE_FREEZE_ENTRY_STATIC_AUDIT_20261014.md`）。

## Railway 4DB / 外部保管先（取り違え禁止）
|対象|原本サービス|暗号化コピー先|
|---|---|---|
|旧V3（休止・wake費注意）|`postgres-hobby-fullhistory-candidate-v3`|非共有Google A / V3専用|
|履歴archive（公開TCP無し）|`postgres-history-archive`|非共有Google A / archive専用|
|**V4本番**（公開TCP無し）|`Postgres-EKp2`|非共有Google A / V4専用|
|**V5研究**（サービス名はv4）|`postgres-hobby-fullhistory-candidate-v4`|非共有Google B / V5専用|

Google A/Bのrclone OAuthは未完（iSH Safari localhost callback失敗）。**元DB/cron/秘密鍵サービス停止・削除禁止**。まず各DBの全量暗号化コピー→再取得SHA照合→本人鍵で全体復号→**独立した隔離PG18への全復元/同時点データ照合**→ユーザー個別承認。2025-07-01以降の原本を保全。復元用Ed25519秘密鍵・passphraseは本人iPhone/iSH/iCloud側のみ、公開鍵だけGitHub；秘密/DB URL/OAuth tokenをチャットやGitHubへ貼らない。

## 工程と目安（T0＝既存ConoHa VPSのアクセス復旧日）
**当初の2026年10月中旬運用開始目標は、VPS実機未確認/未バックアップ/未OOSのため確約不可。** 下記は依存条件が満たされた場合の暫定見込み。
1. **現在（ConoHa Ubuntu 24.04.3 LTS・2GB/3Core/SSD100GBの画面確認済）**：次は安全な本人ログイン方式の確認のみ。既存コンソールは`login:`待ち、コマンド未実行。実機資源のread-only診断は認証・正しい既存VPSとの照合と別承認後。V5/バックアップはoffline継続。
2. **T0〜1日程度**：既存2GBのOS/SSH/CPU/RAM/diskを`ops/conoha/v5_host_preflight_readonly.sh`で実測、本人承認で初期設定。安全なホストで一時鍵による実`age`往復→本人鍵のローカル復号確認。
3. **T0後、数日〜容量/認証次第**：Drive A/B本人OAuth、4DBを**1DBずつ**暗号化退避、外部全体SHA＋隔離フル復元。同期間のRailway停止なし、通信費/起動も事前承認。
4. **バックアップ検証後、数日〜数週間**：V5出走→締切前公式情報/オッズ→証拠gate→shadow予想→公式結果→監査を直列化し、2025-07以降67週OOS・Forward精度/ROI・負荷を測定。欠測はそのまま扱う。リアルタイム取得と重いバックテストを同時実行しない。
5. **十分な検証後**：費用/復旧性/精度を確認、別承認でRailwayの段階縮退。4GB増強は**2GBの実測とRailway費解消後**に必要なら別承認。自動購入は最後。

## 費用と絶対HOLD
ChatGPT＋Railwayは理想月5,000円以下、目安上限6,000円；Railwayは可能なら月$10〜12、$15警戒、$20超回避。**ConoHa/外部保存/二重稼働も総額で評価**。CPU/RAM/Network/WAL/CIを節約、Railway Agent/AI禁止。無承認のmainマージ・V4本番変更・本番cron変更・DB wake/接続/転送・課金・4DB原本/旧CMS鍵削除・BUY禁止。

## Next ONE task
**次ONE task：** 本人がConoHaブラウザーコンソールで**`root@...#`等のシェルプロンプトを確認**し、ログイン成功の場合のみ`free -h`を1回実行して**Mem/Swapの行のみ**共有。ログイン画面のままなら認証手順の問題としてSTOP。続いてディスク空き`df -h /`等を1件ずつread-only診断予定。Railway4DB/main/V4/cron/BUY、旧CMS未保存3件907MB転送、Google Drive A残量未確認、設定変更/SSH/有料操作HOLD。

## 詳細資料（必要時だけ）
`docs/V5_CONOHA_WRITER_CRON_STATIC_AUDIT_20261014.md`、`docs/V5_CONOHA_SERIAL_DAG_CONTRACT_20261014.md`、`docs/V5_CONOHA_2GB_RAILWAY_MOVE_PREFLIGHT_20261013.md`、`ops/backup/BACKUP_SAFE_MODES_20261014.md`、`ops/backup/RESTORE_VERIFICATION_RUNBOOK_20261013.md`、`ops/backup/ISH_AGE_OFFLINE_OWNER_TEST_20261014.md`。
