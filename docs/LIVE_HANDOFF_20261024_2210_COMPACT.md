# 新競艇AI開発プロジェクトNo.2｜現行短縮引き継ぎ（2026-10-24 22:10 JST）

**これが最新の唯一のcompact引継ぎ。** 新チャットでは`docs/HANDOFF_LATEST.md`→本書→`docs/NEXT_CHAT_START_HERE.md`の3点のみ読む。古いhandoff/PROJECT_HISTORYを大量に読み込まない。作業は小さく、Termiusコピペ1回を基本に、GitHub内で実装・更新。Repository:`kenshoushouri-cloud/boat-ai-v2`。GitHub/Railway権限は使用可能な範囲だけ。ConoHa管理はユーザーのTermius実行が必要な場面がある。時刻/数値/進捗は必要時にlive再確認。

## 目的と優先順位
- V5主力の競艇予測AI。2025年7月以降の**すでに保有する全データを最大限再利用**。予測精度・回収率・実際の当時入手可否をウォークフォワードで研究。10月末は限定的な**非購入**運用を目標（未保証）。BUYはOFF、Railway Agent/AIは禁止、低CPU/RAM/Network、料金なるべく月$15以下。
- **最優先：共通領域へデータ複製→V5購入なしshadow並行稼働→既存共有VIEWでバックテスト先行→安全な読取先切替**。旧原本collectorは引き続き一つだけ公式データを取得。新旧で二重の外部収集はしない。複製遅延・欠落は全PK INSERT/UPDATE/DELETEで差分追込、取得可能な公式結果/Kは後日補完。変動オッズ/展示/気象の当時未取得値を偽装しない。
- 旧物理原本writerをV5へ移す本番切替は後工程。最初の切替は**V5 shadow読取先のみ**。V5用既存スコア/120券/前日13Counter/offline scorerの再利用を優先。

## 確定保存先と移行現況
- ConoHa DB`railway`：13物理原本`public.v2_*`、共通`boat_data.*`は13個の非更新VIEWで即read-only研究に利用可能。`boat_data_stage.venues`だけ24行コピー・差異0。残り12物理stageは未作成。**stage1/13、本番live物理切替0/13**。`v5_data.raw_*`は旧案であり使わない。
- 別履歴DB`boat_history_archive`：過去の保存資産。マップ`docs/V5_DATA_LOCATION_AND_CONSOLIDATION_BOARD_20261024.md`。`docs/V5_DUAL_RUN_SHADOW_SYNC_PLAN_20261024.md`が並行移行設計。保存先を毎チャット探索し直さない。
- ConoHa同一VPS`/var/backups`に10/23 main dump/10/24 history dump。10/24 21:11 SHA/bytes/pg_restore TOC両PASS、PG railway3482MB、history1069MB、WAL816MB、ディスク空き67717MB。独立外部復元はまだ未証明。Google Drive外部には10/19暗号化旧世代main/archive実在、復号/完全復元未検証、Drive新書込403 STOP。旧V3/V4保全は削除/上書き禁止。ConoHa OSの無断再起動禁止。
- 12空stage作成SQLの6/6合成テストPASS、ConoHaで12表CREATE+ROLLBACK実リハーサル20:13 PASS、**永続作成0**。新stage copierはデフォルトread-only。必要な独立バックアップ/全writer/差分同期・自動戻しgate前の本番DDL/COPY/タイマー切替はNO-GO。22:07 offsiteコード合成テスト8/8 PASS、実バックアップ復号なし。

## タイマー時刻（ユーザー要望を反映・LIVE設定ではない）
- GitHub source`deploy/conoha/boat-v5-forward-window.timer`は**07:00〜23:55 JST 5分間隔のみ**。展示・直前オッズの締切9〜24分前で6艇/120券不足を選択。深夜03:30には発火しない。実VPSの設置unit一致は未確認。
- 夜間収集は23:00、最大90分程度。結果補完`boat-v5-midnight-catchup.timer`現GitHub定義は**01:20, 02:20, 03:20 JST**の3回。補完serviceは最大30分、昨日のレース結果のPENDINGのみ再取得、公式未公開なら後続回へ再試行。
- **ユーザーは結果補完をもっと早める案を支持する方向**。安全な推奨時刻は **00:45／01:30／02:15 JST**（23:00夜jobが最大00:30終了→15分空ける、最後の補完は~02:45まで、03:30まで45分）。既存提案ファイル`deploy/conoha/boat-v5-midnight-catchup.timer.proposed-early-20261024`に保存済み。**ConoHaには未設置、旧設定の実際の稼働時刻と直近journalを読取確認し、競合・失敗時の戻しが確定してから適用**。誤ってGitHubの提案ファイルを本番として実行しない。
- 03:30〜04:00 JSTが将来の夜間無人reader-only切替候補。**2026-10-25 03:30の切替もまだ未予約**。01:20→候補02:15補完後、PENDINGと全関係workerを検査、差分/鮮度不一致なら元VIEWのまま自動HOLD。後日の切替に人手の夜間操作を求めない。

## 実データバックテストの境界
- 共通VIEWからread-onlyでモデル入力を作れば物理stage完成前でも研究を進められる。既存`v5/offline_mainline_inference.py`、`v5/offline_prior_day_factor_export.py`、`v5/offline_trifecta_shadow_ranking.py`、`v5/offline_day_shadow_pipeline.py`は合成/研究用。実sourceの5因子/直近5走/Counter適合/first-captureはまだ未認証。未来結果や事後最終オッズを予想入力に混ぜず、predecision original proof欠如はHOLD。実ROIやBUY可との誤称禁止。

## Next ONE task
**ユーザー希望の早期結果補完（00:45/01:30/02:15）について、ConoHa設置のsystemd timerと23:00 night、過去のcatchup journalをまずread-onlyで確認し、変更とrollbackを1回の安全コードにまとめる。** 同時にGitHubでV5既存scorerと13 VIEWをつなぐread-only小規模バックテスト入口を開発する。ユーザーが明示承認する前にtimer実更新・夜間自動読取切替予約・原本停止・物理DDL/COPY/BUY/Drive書込は行わない。
