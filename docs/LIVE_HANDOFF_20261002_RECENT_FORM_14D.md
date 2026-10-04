# Live Handoff — Mid-October Launch Critical Path

## 1. システム構築の目的
- 競艇AIを、Productionデータ・予測・通知・学習・検証・バックテストまで安全に一貫運用できる状態へ完成させる。
- **2026年10月中旬の運用開始**を目標とする。
- historical reconstructionはバックテスト用。Prospective V4/V5 gateへ加算しない。

## 2. 最優先タイムライン
1. historical不足データを全て補完
2. read-onlyでcoverage / leakage / integrityを最終確認
3. バックテスト実施
4. 結果確認・運用方式確定
5. バックテスト完了後に古い過去データをarchive/移行し、Production保持量を最適化
6. 運用開始レビュー

非重要な整理・研究は、このcritical path完了後。

## 3. 現在状態
- GitHub `main` = code SoT
- Production data SoT = `postgres-hobby-fullhistory-candidate-v4`
- Railway plan = Hobby
- candidate-v4 RAM cap = **1GB**
- candidate-v3 = SLEEPING、volume/dataは保護
- history archive / escrow key / active writers / reports / backtest / historical / TOTOを保護
- Historical Recent Form方式 = Official K prior-day only / fill-missing-only
- 必須条件 = `SAME_DAY_RESULT_USED=0`, `FUTURE_RESULT_USED=0`, `FILL_MISSING_ONLY=1`
- Recent Form完了 = **2026-08-05**
- 最新成功batch = 2026-07-23..08-05 / run `37171659569` / 12,887 rows / PASS
- 次の固定batch = **2026-08-06..08-19**
- workflow = `.github/workflows/historical-recent-form-backfill.yml`
- 実行command = Issue #42へ `/railway historical-recent-form-next`

## 4. 容量・コスト
- Volume上限 = 5GB
- 最新storage診断: current size **4450.64MB / 5000MB**
- 最新WAL = **184,549,376 bytes**
- replication slots = 0
- 各14日batch後にDisk/WALを確認し、危険なら次を止める
- candidate-v4 1GB capで代表batchは複数回PASS、直近確認も `oom=0 / oom_kill=0`
- Railway運用コスト hard target = **月額USD 20以下**
- コスト削減だけを理由にProduction/backtest/live-test/learning/data/restore-safetyを削らない
- Railway Agent / Railway AIは使用禁止
- 新しい常時稼働service / DB / replica / volume追加やplan変更は、月額影響と安価な代替を示して明示承認が必要

## 5. 次の1作業
1. liveで historical backfill が重複実行中でないことを確認
2. 次の14日 **2026-08-06..08-19** を1回だけ実行
3. SUCCESS後、PASS / leakage条件 / OOM / Disk-WALだけ確認
4. 安全なら次の14日へ即進む
5. historical不足データ完了後、寄り道せず最終coverage確認→バックテストへ移る

## 6. 作業ルール
- 1回に1作業
- read-only確認を先に行う
- destructive/config変更は明示承認が必要
- `list_variables`禁止
- purchase / plan / volume resize禁止
- TOTO staged patchに触れない
- Issue #42全コメント取得禁止。latest run/job logs、必要なら末尾だけ読む
- 古いhandoffは特定の過去判断が必要な場合だけ読む
- SHA / run / 件数 / 容量は固定値とせず、必要なものだけlive再取得
- 出力は短くする

## 7. V5
- V5はresearch-only。ProductionはV4のまま。
- V5 gate = V4 >=20 resolved FORMAL_AVAILABLE days + S03_M2 >=100 official observations + clean evidence contract
- historical reconstructionでgateを水増ししない

`MID_OCT_LAUNCH / RECENT_FORM_14D / BACKTEST_NEXT / HOBBY / RAM_1GB / COST_LE_20 / NO_RAILWAY_AGENT`
