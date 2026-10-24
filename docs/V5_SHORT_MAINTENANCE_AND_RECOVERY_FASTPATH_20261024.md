# V5データ統合：短時間停止＋事後補完の高速移行計画（2026-10-24）

## ユーザー提案と取り扱い
17:55 JST：ユーザーより「移行時の現行収集コード短時間停止はやむを得ない。欠落は過去データとして取得し、集約を早める」方針提案。**短時間計画停止を選択肢として採用**。ただし本日その場でSTOP/物理切替の実行を承認した意味にはしない。自動停止・再開も未予約。

## 今回の根拠
- 17:55 Termius `deploy/conoha/v5_stage_13_batch_gate_readonly_20261024.sql` 正常：`13 rows`, DB `railway`約3479MB、`boat_data_stage.venues`実表(r)、`boat_data.venues`VIEW(v)、`ROLLBACK`, `V5_13_SOURCE_BATCH_GATE_READONLY_DONE_NO_COPY`, `V5_13_BATCH_GATE_FINISHED`。同じ画面の行では一部`v5_data.raw_*`はABSENT。**すべてのphysical target不在を実画面から推論しない**。本番切替0/13、venues隔離stage1/13のまま。
- 固定13ソースマップ：`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`。毎チャット旧保存先を探し直さない。
- 6日標本で古い2025/07〜2026/07の大多数の展示6艇shapeが既存main DBに存在。10/20はforward28＋検査probe1。ソースがあるなら再取得より再利用が先。ラベル時刻は初回取得証明にならない。

## 移行高速化：運用停止を**最後の短い区間だけ**にする
1. **旧収集稼働中**：V5本体の既存VIEW接続アダプタとモデル安全性は並列開発。13表同時メタ監査は完了。移動対象テーブルごとにPK/UNIQUE、schema、default/sequence/FK/INDEX、trigger、writerを認証し、**1つのオンライン移行バッチ計画**としてまとめる。孤立した毎回1表調査は避ける。venues 24件stageを再作成・再コピーしない。追加physical stage作成・多表コピーは、適切なバックアップ/roll-forward/rollbackと追加承認の後。
2. **稼働中オンラインCOPY**：既存collector/writerが`public.v2_*`へ書き続ける間、低負荷小チャンクで許可済みV5新規実表にコピー。WAL/IO/容量を監視し、行数＋checksum/キー＋timestamp/source列で差分検証。insertだけでなくupdate/deleteも再現できる設計を必須にする。**停止して一括大量COPYより短い最終停止を優先**。
3. **計画停止ウィンドウ（個別実行承認）**：当日の全レース/official K/結果取込/catchupの完了と次タイマーまでの残り時間を確認。DB独立復元可能なバックアップ、旧writer全経路・子processの認証、復帰コマンド/担当者、停止時間上限と自動復帰経路が事前に明確なときだけ、影響するtimers/servicesを限定停止。Systemd timerだけでなく実行中worker、cron/手動補完も確認。DBの長期LOCKを避ける。
4. **final delta＋canary**：停止後の挿入/更新/削除差分（重複/NULL/制約含む）を正しく同期、元と新の整合チェック。all-gates PASSかつ個別承認がある場合にのみread/writeルートを一括で切替。BUYは常にOFF。1件ずつの限定nonbuyエンドツーエンド試験。異常/時間超過は**旧経路を維持または事前定義済みの戻しを実施して収集を直ちに再開**。復帰確認まで保守終了とは記録しない。
5. **事後補完（欠落の種類でgate）**：
   - 公式出走/確定結果/K/選手・モーター履歴：既存archive/メインDB/公式再取得で不足を補う。source・取得日時・バックフィル由来を記録する。
   - 展示値：過去保存ラベルに原本があれば流用。後日の公式再取得が可能なときは`RETROSPECTIVE_BACKFILL`（当時観測証拠ではない）としてのみ研究用に分離。
   - 締切直前3連単オッズや風水面、展示の初回リアルタイム時刻：必ずしも再取得不可。事後の最終値で上書きせず`UNKNOWN_AT_DECISION`/HOLDとして実Forward/ROI・自動購入検証の母集団に紛れ込ませない。合成研究と本当に前向き取得した検証は分ける。
6. **完了後**：旧原表は残し一定期間並行監査。V5本体＋共有原本をV3/V4とは別の外部保全へ（Drive403解消／復元検証が先）、削除は後日の独立承認。

## 夜間の完全自動切替スケジュール案（2026-10-24）
- ユーザー要望：**深夜の手動操作は不可能。サーバー上で安全な無人実行・無人切戻しが必要**。ChatGPTの時刻通知ではVPSを操作できないため、必要ならConoHaの`systemd` one-shot unit＋timerと独立したgate/rollbackを構築する。**まだインストールも起動予約も行っていない**。
- **候補窓：03:30〜04:00 JST（準備完了した後の将来日程）**。01:20結果補完の終了/未確定結果=0を必ず実測し、07:00朝タイマーの前に復帰確認する。今夜2026-10-25 03:30の本番自動切替はNO-GO。時刻到達だけでは起動しない。
- 日中：既存収集稼働のままonline低負荷stage＋全13writer/DDL経路認証・独立バックアップ復元・差分insert/update/delete再現・リハーサル・本番の承認条件をすべて確立。承認前のunit有効化禁止。
- 実施時の自動ガード：予約世代と事前承認の一致、バックアップ外部復元済み、last-run/catchup正常、K/結果PENDING0、全旧writer service/child worker/cron識別済み、メンテナンス窓30分以内、容量/WAL余裕、元・stageのキー/ハッシュ/列/制約/索引互換、原表復帰コマンド既定・リハーサル済み、BUY強制無効、V5 nonbuy canary。
- **いずれか1つでも失敗すれば旧収集を停止させない／途中なら事前に実証した切戻しを実施して旧収集を再開**。rollback不能のgate未承認状態ならスケジュール無効。原本は削除せず、欠損や過去補完もas-of証明に混入させない。
- 2026-10-24 18:13 ユーザー要望に合わせ`deploy/conoha/v5_cutover_writer_inventory_readonly_20261024.sh`をGitHubに追加。現時点でこちらは**監査専用、停止/切替コードではない**。

## 2026-10-24 一括準備コード
- `deploy/conoha/v5_cutover_one_command_prepare_20261024.sh`をGitHubにアップロード。コマンド1回でread-only 13関係・writer/cron/PGの監査、ローカルバックアップ候補一覧、ステージの波分け、03:30夜間切替gateを**保全先`/var/backups/v5_prepare_*/`へレポート出力**。
- 作業は新規ローカルファイル書込のみでDB/VIEW/systemdの変更・自動切替の予約・大量COPYはしない。日中のonline-copy/差分追込・独立バックアップ復元・全writer証明・自動切戻しが今後の開発工程。03:30-04:00は**候補時刻**であり今夜の予約ではない。

## 直近1作業
**4timerは18:06、writer/cron/DB瞬間監査は18:20に確認済み**。forward 18:10/以後5分ごと、night 23:00、catchup翌01:20、morning翌07:00。停止前の残課題はtimer以外のworker/cron/DB writer・未確定結果・独立復元・復旧実行方法。次は実行中writer/DB接続をコマンド行・秘密値を表示せずread-only棚卸し。 書込停止前のバックアップは同VPS保全と外部独立保全の違いを厳格に扱う。stop/start/disable/mask/kilI/write migrationはまだ行わない。

## 常設禁止
定時を過ぎたからという理由だけで停止しない。DB/COPY/DDLやサービスSTOPをread-only点検コードに混在させない。Drive新規書込連続再試行、Railway Agent/AI、V3/V4バックアップ上書き、BUY、過去データ削除禁止。コスト下限志向。
