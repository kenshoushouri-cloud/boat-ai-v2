# V5独立・非購入判定記録 v0.1（オフライン設計、2026-10-24）

## 目的と現状
2026-10-24 15:23 JST のConoHa監査では、指定したV5本体・collector・var/lib候補から名称に `*decision*.jsonl` / `*predict*.jsonl` / `*ledger*.jsonl` / `*freeze*.jsonl` といったJSONL・SQLiteのファイルは見つからなかった。これは探索条件下の「未発見」であり、V5判断記録が全システムに存在しないという断定ではない。DBのV5系名称 inventory も0候補だった。旧 `public.v2_realtime_decisions` はV5独立台帳には流用禁止。

目的は、**V5で実際に行った判断時点と、その時点で参照可能だった情報の証拠**を監査可能にし、非購入（shadow）の限定運用が完了してから初めて実ROI/自動購入を検討すること。データ収集の成功や`snapshot_at<deadline_at`だけでは、情報の初回観測や最終予測時点の可用性は証明できない。

## 既存の資産は再利用し、重複実装しない
- `v5/offline_asof_eligibility.py`, `v5/offline_first_write_attestation.py` は**合成/オフライン検証器**。これらの結果を実一次情報の証明と見なさない。
- `v5/offline_day_shadow_pipeline.py` は合成スコア入力の**オフライン**検証。実予測器/本番許可ではない。
- `v5/telegram_trial_performance.py`, `v5/ntfy_trial_performance_report.py` は**外部で固定済みの検証可能V5 JSONL ledgerの読取/集計**のみ。予測を生成しない。
- `v5/conoha_realtime_window_pg.py` は公式直前情報の取得器であり、予測決定器ではない。現行タイマー/collector変更なし。

## 2026-10-24 再利用優先監査（先に既存実装を保護）
GitHubの調査により、**前の「記録器なし」は不正確**と判明。インストール先に一致する保存済みファイルがないことと、記録機能のコードがないことは別。
- `v5/offline_mainline_inference.py`：研究用の6艇1着確率計算（現実データ使用の正当性未認証）
- `v5/offline_trifecta_shadow_ranking.py`：3連単120通りのPlackett-Luce仮定によるshadow順位付け
- `v5/offline_v5_freeze_bridge.py`：研究用スコア→paper-shadow freezeの接続（`build_paper_shadow_freeze`）
- `v5/forward_shadow_freeze.py`：**既存の**`prepare_candidate`（締切・6艇展示・120点オッズ・ハッシュ形状検査）と、`append_once`（0600、排他ロック、race重複拒否、fsync）を用いたローカルshadow記録器。ネットワークや購入動作なし。**元配信の最初の観測真正性・買い目収益率を保証しない**。
- `v5/offline_day_shadow_pipeline.py`：合成1日単位の集計。既存テスト例`tests/test_v5_offline_day_real_modules.py`。
- 研究段階の正式なV5候補仕様は**未統一**。2026-09-27の`docs/V5_RESEARCH_SCOPE_LOCK_20260927.md`（旧V4系基準、T=2.20）とstrong-core`offline_mainline_inference.py`（5 factor、T=1.00）には差異がある。`docs/V5_FREEZE_READINESS_AUDIT_20261009.md`も未解決のscope conflictとして明記。どちらかを黙って本番採用しない。
- 既存`forward_shadow_freeze.py`の`stake_per_ticket_yen`は**仮想金額**であり、実支出0と明示しなければならない。設計内の`stake_yen=0`と混同禁止。

**採用方針：既存のV5研究・合成検証コードを再利用し、実データ時刻・証拠・本番入力アダプタと監査機能の欠落だけを補う。並列に重複したスコア計算器・shadow記録器を作らない。**

## 既存コードとの差分監査（10/24）
読取対象：`v5/forward_shadow_freeze.py`（`prepare_candidate`/`append_once`）、`v5/offline_v5_freeze_bridge.py`、対応する2件の`tests/test_v5_*.py`。**現在の記録器・スコア計算器を置換せず再利用する。**

- 初回取得の原本真正性：6展示/120オッズ、自己申告`captured_at`とSHA256文字列の形状は検査される。しかし生データの初回HTTP受信完了・永続化・生バイトの独立ハッシュは証明しない。
- as-of：bridgeは判定cutoffから`now`まで0–60秒、freezeは`now`から締切まで180秒以上を要求するが、**`captured_at <= decision_cutoff_at`は未検査**。cutoff後かつnow以前に取得された情報が合成チェックを通る余地がある。`recorded_at`は保存時刻相当であり実際の独立decision receiptとは異なる。
- モデル固定：strong-core `MODEL_VERSION`、5 factor・T=1.00の入力ハッシュはあるが、モデルartifact/policy versionの実行時固定はない。9/27 scope lockのT=2.20系とのモデル選択不一致は未解決。
- 金額：`hypothetical_stake_yen`は仮想投資額。実支出0・購入権限なしを独立証拠として明示する必要がある。`buy_eligible=false`は維持。
- 記録：`append_once`は排他lock・0600・同raceの重複拒否・fsync・合成テストを備える。外部バックアップ復元・独立読み戻し・配信真正性の証拠はない。
- 今回は静的コード監査であり、新しい自動テストは実行していない。DB、タイマー、公式collectorは変更していない。

**次のONE task:** 既存処理の再利用を保ち、オフライン合成のas-of境界検査（cutoff後の展示/オッズはHOLD）をテストから小さく追加する。実配信・実予測・BUYなし。

## 候補記録の契約（まだ実装・有効化しない）
別プロセス（購入権限なし、外部APIなし）からのみ、レース単位の`shadow`候補を受け取る。
1. **識別**：`race_id`, `model_version`, `model_artifact_sha256`, `policy_version`, `run_id`。同一`race_id+model_version+decision_type`の複数確定記録禁止。
2. **時刻**：`deadline_at`, `decision_cutoff_at`, `decision_at` は時差付き。実現には独立の取得開始/完了/永続化時刻と時計校正記録が別途必要。すべて`decision_at<deadline_at`、必要に応じ安全な購入停止バッファを課す。
3. **根拠**：各出走/展示/風水面/オッズ/Kなどについて、source種別、元のraw受信bytesのSHA256、独立に記録されたHTTP応答完了時刻・保存完了時刻、`snapshot_label`, 読取元と元データの凍結証拠。**`snapshot_at`だけの記録、事後再構築、後から付けたダイジェストは`UNVERIFIED_SOURCE`**。
4. **判定**：特徴量入力ハッシュ、V5スコア結果と採否（`SHADOW_PREDICTION`または`HOLD`）、理由コード、買い目案（あれば）。`purchase_enabled=false`、`stake_yen=0`（支出なし）、`buy_eligible=false`を強制し自動購入には接続しない。未証拠/欠損/決定後のソースは`HOLD`。
5. **証拠固定**：canonical JSON bytes SHA256、追記専用のsequence・previous hash・fsync・同一race重複拒否、独立読取監査で固定内容を照合。ハッシュチェーンや自己申告時刻**単独**は取得真正性の証拠ではない。現行ConoHaとの別場所に新世代を保全し、復元試験が通るまで`INDEPENDENT_BACKUP_UNVERIFIED`。

## 実装順序と境界
**第一段階（read-only差分監査済み）**：既存の`prepare_candidate`/`append_once`/`build_paper_shadow_freeze`と不足証拠を比較済み。**次の1作業**は合成テストから`captured_at`と`decision_cutoff_at`の厳格なas-of境界を検証する最小補強。実初回観測証明とは分離。DB・HTTP・本番JSONL書込・通知・BUY・systemd変更なし。

**第二段階（別ゲート）**：研究候補モデル・重み・selectorの相互矛盾を合意済み証拠で解消し、実データの独立初回観測と`append_once`既存writerの安全性を再検証。受入れ条件、独立外部バックアップ・復元検証後にのみ新規の非購入shadow journalを許可。旧DB表上書き・既存データ削除禁止。

**第三段階**：shadow予測と実結果/払戻/返還の公式原本を独立照合。外部検証できる凍結receiptが無ければ性能・利益率は`未検証`。実購入は別承認まで禁止。

## 現状のNO-GO
共通stage複製1/13・本番物理正本切替0/13、DriveへのV5独立バックアップ書込はHTTP403 RATE_LIMITで未達。取得頻度の増加・別サイトの短間隔収集・Drive書込の連続再試行・BUY・旧V2/V4の実績流用は行わない。
