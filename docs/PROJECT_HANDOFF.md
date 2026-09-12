# boat-ai-v2 Project Handoff

更新: 2026-09-12 JST

この文書は**現在地だけを短く共有するための引き継ぎ**です。個別PRの経緯、日次件数、長い実験結果はここへ追記しません。

再開時は、この文書の数値やPR番号を最新値と決めつけず、必ず GitHub `main`、open PR、Railway read-only health を確認してください。

## 再開時の指示

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/PROJECT_HANDOFF.md` を読み、現在の `main`、open PR、Railway Production の read-only health を確認してから続行してください。GitHub `main` をコードの Source of Truth、Railway PostgreSQL を本番データの Source of Truth としてください。安全な監査・研究・Draft PR・CI・文書整理は継続可、Production変更は明示承認まで実施しないでください。

## Source of Truth

- Repository: `kenshoushouri-cloud/boat-ai-v2`
- Code: GitHub `main`
- Production DB: Railway PostgreSQL
- Railway service構成: `docs/RAILWAY_SERVICE_MAP.md`
- 判断履歴: `docs/PROJECT_HISTORY.md`
- 詳細研究ログ: `docs/DEVELOPMENT_STATUS.md` と各PR
- Railway監査ログ: Issue #42

GitHubは `branch → Draft PR → CI → review → merge` を基本とし、mainを直接編集しません。

## Production変更の承認境界

以下は明示承認が必要です。

- PRのProduction反映を伴うmerge
- Railway Production設定・Variables・Cron・service変更
- DB schema作成、Production DB書込み・削除・VACUUM等
- モデル、係数、閾値、Production判定ロジック変更
- LINE実送信に関わる変更
- Forward予測の実保存開始
- 自動購入
- 有料データ契約・外部問い合わせ送信

安全なread-only監査、研究コード、Draft PR、CI、文書整理は確認なしで進めてよいです。

## 現行Productionの要点

主軸は競艇です。Production予想は概ね次の2段階です。

1. PRE: `run_window_pipeline_pg.py` 系
2. FINAL: `run_final_pg.py` → realtime collection → v22判定 → LINE通知

自動購入はありません。Shadow / Forward研究はProduction BUY/WATCH/SKIP・LINEから隔離したまま扱います。

正しい出走表テーブル名は `v2_race_entries` です。

## 2026-09-12 時点の重要な現在地

### 1. 精度向上研究

- Opponent Pressure V2 は自然CronでForward観測中。Production昇格は未承認。
- Racer Course 0.50 は有望な研究結果があるが、欠損laneをneutral扱いするForward Shadow設計を含め、まだ研究段階。
- Shadow成功だけでProductionへ昇格しない。自然Forward日数・タイミング整合・独立評価を優先する。

### 2. PRE LINE周辺

- PRE用LINE上限変数のalias差異と、重複通知防止機能が未有効である点を研究中。
- Production Variables、dedupe schema、通知仕様はまだ変更しない。

### 3. Railway / DB容量

容量圧迫は確認済みです。ただし、**安全性を優先して削除・VACUUM・Cron停止は未実施**です。

重要な結論:
- `v2_odds_trifecta` の大半は実データで、単純な削除対象ではない。
- `learning_all` と `final_ab` は大きく重複するが、`learning_all` のオッズが FINAL の previous-odds / drift / steam 特徴へ間接的に使われるため、単純停止はProduction出力に影響し得る。
- したがって `cron-learning-all` の全面停止や既存 `learning_all` 行削除は現在ブロック。
- 容量対策は、Production意味を維持する設計を研究してから承認を取る。
- DB削除を検討する場合は、直前のread-only再監査と新しい復元可能バックアップが必要。

## 現在の優先順位

1. 競艇Productionの自然運用とread-only health監視を維持する。
2. Opponent Pressure / Racer Course等のForward証拠を自然データで蓄積する。
3. DB容量対策は、予測・学習・LINEへ影響しないことを証明してから進める。
4. Draft研究を整理し、Production変更候補は承認単位を小さく分ける。
5. 競艇の実戦投入・収益性を最優先とし、他競技は容量・データ取得・期待収益を見て採否判断する。

## open PRの扱い

再開時にopen PRを必ず一覧取得してください。2026-09-12時点では、主に以下の研究Draftがあります。

- Course / Opponent Pressure のpre-production timing研究
- Racer Course neutral-missing Forward Shadow設計
- PRE LINE limit / dedupe契約研究
- Storage retention / duplicate-load研究
- `learning_all` の安全な負荷削減研究

これらは**Draft研究であり、存在だけを理由にmerge・deployしません**。

## この文書の更新ルール

`PROJECT_HANDOFF.md` には次だけ残します。

- 現在のProduction境界
- 重要な未解決事項
- 現在の優先順位
- 次の担当者が知らないと危険な事項

個別PR番号ごとの長い説明、日次ログ、検証の全数値、過去に完了した経緯は追記せず、`PROJECT_HISTORY.md`、`DEVELOPMENT_STATUS.md`、各PR本文へ残してください。

目安として、引き継ぎ本文は**短く読み切れる長さを維持し、追記ではなく古い記述を置き換える**運用にします。
