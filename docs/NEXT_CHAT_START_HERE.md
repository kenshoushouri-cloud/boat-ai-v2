# 新チャット最小起点 — 新競艇AI開発No.2（2026-10-24）

@GitHub

repo `kenshoushouri-cloud/boat-ai-v2`。1. `docs/HANDOFF_LATEST.md`、2. そこで指定された`docs/LIVE_HANDOFF_20261024_OFFSITE_RECOVERY_COMPACT.md`、3. 本ファイルの3点のみを読む。古い長いhandoffやPROJECT_HISTORYを大量参照しない。

目的：V5主力・2025年7月以降・10月末限定非購入運用目標。旧原本`railway.public.v2_*`13表／`boat_data.*`VIEW13／`boat_data_stage.venues`24行、残り物理stage未作成、本番切替0。前向き締切前証明・費用最小・安全停止復帰優先。Drive10/19暗号化V5バックアップは存在するが復号/独立restore未検証。10/23-24ローカルバックアップ2件は同一VPSのみで確認。Drive新書込403 STOP、03:30切替未予約、BUY OFF。

**Next ONE task:** 新`v5/offsite_encrypted_dump_verify.py`および`tests/test_v5_offsite_encrypted_dump_verify.py`（8件、未実行）のオフライン合成試験。実際の暗号化バックアップはGitHubにアップせず、鍵を表示・共有しない。その後独立試験環境の復号・PG実restore及び現行バックアップno-overwrite別世代確保に進む。今は本番DDL/COPY/停止・夜間タイマーはNO-GO。
