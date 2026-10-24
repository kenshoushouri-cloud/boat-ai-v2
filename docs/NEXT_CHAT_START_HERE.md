# 新チャット最小起点 — 新競艇AI開発No.2（2026-10-24）

@GitHub

repo `kenshoushouri-cloud/boat-ai-v2`。1. `docs/HANDOFF_LATEST.md`、2. そこで指定された`docs/LIVE_HANDOFF_20261024_OFFSITE_RECOVERY_COMPACT.md`、3. 本ファイルの3点のみを読む。古い長いhandoffやPROJECT_HISTORYを大量参照しない。

目的：V5主力・2025年7月以降・10月末限定非購入運用目標。旧原本`railway.public.v2_*`13表／`boat_data.*`VIEW13／`boat_data_stage.venues`24行、残り物理stage未作成、本番切替0。前向き締切前証明・費用最小・安全停止復帰優先。Drive10/19暗号化V5バックアップは存在するが復号/独立restore未検証。10/23-24ローカルバックアップ2件は同一VPSのみで確認。Drive新書込403 STOP、03:30切替未予約、BUY OFF。

**Next ONE task:** ユーザー意向：既存原本collectorが稼働中、オッズ/展示/気象は既に収集されるため、日中source→stage複製・夜間03:30に最終差分→V5の**readerだけshadow切替**し、元writerは並行維持する。5分間隔timer/01:20 catchup終了は直前チェック。結果等は事後補完可、当時取り損ねた動的スナップショットまで復元保証なし。まずGitHubの既存V5 scorer/inference/backtest入口とVIEW read-only契約を狭く確認し、今すぐpaper-only real-data pilotを開発。物理stage12未作成/本番writer切替は別gate、03:30タイマー未予約、BUY OFF、Drive403 STOP。
