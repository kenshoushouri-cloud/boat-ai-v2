# V5早期稼働・一日停止を回避する方針（2026-10-26 JST）

## 優先判断
- ユーザーはV5を早期主力化し、Kファイルや確定結果の補完をV4→V5へ繰り返しコピーする無駄を廃止する意向。
- **今日一日の収集全面停止は行わない。** 後日再取得可能な確定結果と違い、展示・レース直前の変動オッズ・風/水面・当時の取得時刻は復元できないことがある。
- V5を二段階で開始する。**A: READ ONLY / shadow / paper / BUY OFF**は現行 `boat_data.*` VIEWを用いて原本writerを変更せず先行できる。これは実モデルの前向きROIや本番V5予測サービス稼働の証明ではなく、入力/実データ線の検査から開始する。
- **B: V5 OWNED writer**は `boat_data_stage.*` を正式書込先とする本番切替。リーダー/ライター/全timer/子workerを監査し、復旧可能なバックアップと試験済みrollbackを証明してから短い深夜窓で実施する。原本とstageの同時writer分裂禁止。丸一日の停止は不要。
- 旧収集1系統のみ継続し、外部公式サイトへの二重収集を避ける。V5非購入評価は独立して開始可能だが、現行collectorと平行して二重に外部情報を取るのは避ける。
- 10/25初回13系統COPY完了、10/26 03:16 JST全13系統の**表ごと**差分反映はPASS。CDCではないので現時点のstage鮮度を保証しない。次の読み取り専用検査 `deploy/conoha/v5_fast_start_shadow_freshness_readonly_20261026.sql`（GitHub登録済）で今日のraces原本／stage ID集合と13系統VIEW/物理stageを確認。実ConoHaでは未実行。
- 今後の公式K詳細は対象8日1295レース=7770艇分。10/21江戸川12Rおよび10/25若松12Rは中止で、架空の着順を挿入しない。今後はKの正本をV5 stageへ直接投入する専用処理に整理する。**現行の `save_k_day_results_pg.py` は旧原本Kおよび結果へ書込むため、無検証では再利用しない。**
- V5 stage Kの一日分ガードをGitHubで設計済みだが、現時点では独立した当日データ世代の復旧試験が未合格。新鮮バックアップを確保してからDB write pilot。10/19 Drive暗号データでは10/26までの保護とならない。
- 費用削減：ConoHa既存DBを再利用。Railway有料サービス・Agent/AIや追加常駐複製ジョブを増やさない。古い原表や貴重なsnapshotsは復旧gate通過後の別承認までは削除しない。

## 実装の短期順序
1. 当日race-IDのstage鮮度をread-only検査し、shadowが参照すべきVIEWとstageを判断。モデル未完成なら未完成と表示する。
2. V5 **read-only**入力チェック・予測モデル/評価ハーネス起動の実動検査を行い、結果は仮スコア扱い、BUY無効。
3. 今日の変動スナップショット収集を止めず、V5 OWNED writerの対象全SQL・依存サービス・sequence/default/GRANTを列挙する。
4. 最新世代暗号バックアップのVPS外保全と独立リストア実証を行う。旧Drive保全の上書き/無理な403リトライはしない。
5. V5 stageへKを直接挿入する1日pilot（旧原本結果に触れない）。残7日をゲート付き処理で追加し、各日6艇の完全性を確認。
6. 深夜の短い管理窓で全writer停止/最終差分/等価性照合/切替/監視/即時切戻しを実施。条件不一致なら元のcollectorを再開、全日欠損を発生させない。

**現状：AのV5本番予測サービスが起動している証拠はまだない。Bの正式物理writer切替は0/13。BUY OFF。**

## 実装追加（2026-10-26）
- `deploy/conoha/v5_k_detail_dual_backfill_guarded_20261026.py` に `--stage-only` を追加（commit `672460c735b830b85ac2f52db88592db57591119`）。新しいモードでは書込先を `boat_data_stage.racer_results` のみに限定し、原本 `public.v2_result_entries` と `public.v2_results` を変更しない。書込後は公式Kの全race_id×lane×rawとステージ行を同一トランザクション内で照合、異常ならrollback。
- このモードはGitHubに実装しただけで、実DBへの補完・コンテナ/VPSでの実行テストはまだ実施していない。既定はread-only preview。`--apply --stage-only` は直近世代バックアップの独立復元の管理証拠や明示env等のゲートを依然必須とする。K補完実行コマンドは現段階で発行しない。
