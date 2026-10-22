#!/usr/bin/env bash
# One-shot ConoHa bulk staging at 02:00 JST on 2026-10-23.
# Root runs this once. It does not change services, switch V5/V6 routing,
# re-run itself, or delete public source tables. Abort on failed preflight.
set -euo pipefail
REPO=/opt/boat-ai-v5
PY=/opt/boat-ai-v5-venv/bin/python
TARGET_JST='2026-10-23 02:00:00'
UNIT='boat-shared-bulk-stage-20261023'

[[ "$(id -u)" -eq 0 ]] || { echo 'STOP: requires root' >&2; exit 1; }
[[ -f "$REPO/deploy/conoha/boat_shared_bulk_stage_20261023.py" ]] || {
    echo 'STOP: staging script missing' >&2; exit 1;
}
cd "$REPO"
echo '=== OFFLINE COPY SAFETY TESTS ==='
PYTHONDONTWRITEBYTECODE=1 "$PY" -m unittest discover -s tests -p test_boat_shared_bulk_stage_20261023.py -q

echo '=== CATALOG/DISK PREVIEW (NO DB WRITES) ==='
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
    PYTHONDONTWRITEBYTECODE=1 "$PY" \
    "$REPO/deploy/conoha/boat_shared_bulk_stage_20261023.py"

target_epoch="$(TZ=Asia/Tokyo date -d "$TARGET_JST" +%s)"
now_epoch="$(date +%s)"
delay="$((target_epoch - now_epoch))"
if (( delay < 60 )); then
    echo 'STOP: target 02:00 JST already passed or too close; nothing scheduled.' >&2
    exit 1
fi
if systemctl list-unit-files "$UNIT.service" "$UNIT.timer" --no-legend 2>/dev/null | grep -q "$UNIT"; then
    echo 'STOP: one-time staging unit already exists; no duplicate scheduling.' >&2
    exit 1
fi
echo "=== SCHEDULE ONLY: ${UNIT}.timer at ${TARGET_JST} JST (after 01:20 catchup) ==="
systemd-run --unit="$UNIT" --on-active="${delay}s" --collect \
    --property=CPUQuota=40% --property=Nice=10 \
    --property=IOSchedulingClass=idle --property=MemoryMax=1536M \
    /usr/sbin/runuser -u postgres -- /usr/bin/env \
    DATABASE_URL=postgresql:///railway \
    CONFIRM_BOAT_BULK_STAGE=YES PYTHONDONTWRITEBYTECODE=1 \
    "$PY" "$REPO/deploy/conoha/boat_shared_bulk_stage_20261023.py" --apply

echo 'STAGING_SCHEDULED_ONLY_NO_CUTOVER_NO_SOURCE_DELETES'
echo "Later inspect: journalctl -u ${UNIT}.service -n 80 --no-pager"
