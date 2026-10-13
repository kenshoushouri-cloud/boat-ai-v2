# GitHub Actions 長時間実行候補（2026-10-14 / 読取専用）

## 結論（原因確定ではない）
GitHub Free本人Billing画面の2026-10-01はLinux **1,858分**、10-04はLinux **1,850分**で、各日のgross相当額は約$11、**実請求は両日$0**。Actions storageはそれぞれ**31.36 GB-hr $0.01**／**46.43 GB-hr $0.02**程度。容量ファイルの大量削除より、**不要な長時間Runnerの調査・移行**が優先。ただしBillingの日別合算から具体的なworkflowへの帰属はまだ実証できない。

## mainのライブworkflow定義で見つかった候補
1. `.github/workflows/exhibition-st-forward-scheduled-collector.yml`
   - `schedule: cron '*/5 22,23,0-12 * * *'`（UTC 22-12時の15時間、5分間隔で起動要求）。
   - `EXH_ST_AUTOCAP_LOOP_SECONDS=5400`（**90分**の待機を含むwhileループ）、`EXH_ST_AUTOCAP_LOOP_SLEEP=120`、`timeout-minutes: 100`。
   - `concurrency.group=exhibition-st-forward-shadow`、`cancel-in-progress: false`、実collector `collect_exhibition_st_forward_shadow_pg.py`、RailwayのDB接続設定あり。**Forward用の観測を止めるとデータ取得と事前スナップショットが欠けるおそれ**。
2. `.github/workflows/racer-course-top3-forward-scheduled-collector.yml`
   - `schedule: cron '45 21 * * *'`（毎日1回）。
   - `RACER_COURSE_AUTOCAP_LOOP_SECONDS=7200`（**120分**）、`RACER_COURSE_AUTOCAP_LOOP_SLEEP=120`、`timeout-minutes: 130`。
   - `concurrency.group=racer-course-top3-forward-shadow`、`cancel-in-progress: false`、実collector `collect_racer_course_top3_forward_shadow_pg.py`。収集停止でForwardの時点固定証拠が欠け得る。
3. `.github/workflows/bao-forward-shadow-auto-capture.yml`
   - 2026-08-23〜25の日付範囲のcronが残っているが、内部gateは**2026-08-24／25 JST限定**。10月の長時間実行原因と推定しない。今後の整理候補にはなるが自動削除不可。
4. `.github/workflows/motor-guard05-forward-shadow.yml` 毎日07:20 JST相当、`timeout-minutes:25`。
5. `.github/workflows/candidate-discovery-v4-prospective-freeze.yml` 毎日08:16 JST相当、`timeout-minutes:15`。V4現行の依存確認を優先。

## 保護条件
- 調査は既存mainのYAMLファイルをGitHub接続で読み込んだだけ。**cron停止・編集・main commit・Railway wake・データ削除・Actions再実行は一切なし**。
- 10月1日／4日の高額相当は**実行時間の合計**。当該5workflowがその日の時間を占めたことは、Actions実run job durationsを集計するまで未証明。
- ConoHa VPS管理画面はサポート待ち。まず2GBで環境構築と負荷実測。GitHubはコード/履歴保持、ConoHaで収集・ジョブ管理へ段階移行。**2GBで足りずRailway費用削減済みなら本人の別承認で4GBを検討**。
- 移管時も欠測回避を最優先し、同時にGitHubとConoHaで二重writeしない。移行→Forwardデータ一致確認→GitHub schedule停止/削減は**別承認後**。
- 旧CMS暗号化artifact3件、復元鍵、V4本番、V5研究を保護。BUY HARD HOLD。

## Next ONE task
**該当する10/1／10/4付近のGitHub Actions Run/Job時間を読み取り専用で突き合わせ**、workflow別の実行分数を特定して停止候補と移行優先順位を決定する。履歴API制限で該当Run IDの直接取得が難しければ、ユーザーにSafariのGitHub Actions画面から実行履歴1件を指定してもらう。費用・機能維持を確認できるまで自動停止しない。

## 2026-10-14 追加調査：実行履歴との突き合わせ
- GitHub連携の利用可能なActionは既知`run_id`からのjobs取得で、**指定日のworkflow runs全件リスト/APIでの日時・duration取得は未対応**。公開REST/Action画面への外部アクセス試行も現在の実行環境ではアクセス不能。したがって10/1・10/4の各1,858/1,850分をworkflowごとに帰属することはまだできていない。
- 既知の`run_id=36812386066`（過去の暗号化parity artifact）はjob名`parity`・結論`success`と工程名を取得。**タイムスタンプや実行時間は返らないため、これ一件から日別利用量の原因は断定不可**。
- 調査するURL（iPhone Safari GitHubログイン後）: `https://github.com/kenshoushouri-cloud/boat-ai-v2/actions/workflows/exhibition-st-forward-scheduled-collector.yml?query=created%3A2026-10-01`。GitHub公式はworkflow run一覧の`created`日付フィルタ対応を案内。まずこのworkflowの10/1実行一覧（runリンク・時刻・durationがあれば）を1画面だけ確認し、その後10/4を比較する。
- **この調査でcronを変更/停止しない。** Forwardデータ欠落と二重取得を避ける。
