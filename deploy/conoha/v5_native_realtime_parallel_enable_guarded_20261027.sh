#!/usr/bin/env bash
# Turn on normal all-venue V5 realtime 5min collection ONLY AFTER a real
# native 6-family full snapshot exists in physical boat_data_stage.
# Old collector stays active independently. Does not turn on BUY/results.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--activate" || "$mode" == "--disable" ]] ||
 { echo "HOLD_MODE"; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "HOLD_ROOT_ONLY"; exit 2; }
timer="boat-v5-native-realtime.timer"
new="/opt/boat-ai-v5-native/releases/v5realtime-all-venues-f63bdf36c9d6ae41bba5ec828bd0a61fc7330ee3"
if [[ "$mode" == "--disable" ]]; then
 [[ "${V5_NATIVE_REALTIME_DISABLE_APPROVED:-NO}" == "YES" ]] ||
  { echo "HOLD_EXPLICIT_DISABLE_APPROVAL"; exit 2; }
 systemctl disable --now "$timer"
 echo "V5_NATIVE_REALTIME_TIMER_DISABLED_OLD_COLLECTION_UNCHANGED_NO_BUY"
 exit 0
fi
[[ "$(readlink -f /opt/boat-ai-v5-native/current)" == "$new" ]] ||
 { echo "HOLD_ALL_VENUES_REALTIME_RELEASE_NOT_INSTALLED"; exit 2; }
[[ "$(systemctl show "$timer" -p LoadState --value)" == "loaded" ]] ||
 { echo "HOLD_REALTIME_TIMER_NOT_INSTALLED"; exit 2; }
[[ "$(systemctl show boat-v5-forward-window.timer -p ActiveState --value)" == "active" ]] ||
 { echo "HOLD_OLD_FALLBACK_TIMER_NOT_ACTIVE"; exit 2; }
for name in core-morning core-night core-refresh results; do
 state="$(systemctl is-active "boat-v5-native-$name.timer" 2>/dev/null || true)"
 [[ "$state" != "active" ]] ||
  { echo "HOLD_OTHER_NATIVE_TIMER_ACTIVE_NEEDS_REVIEW_$name"; exit 2; }
done
echo "=== VERIFY ONE REAL NATIVE SIX-FAMILY PREDEADLINE SNAPSHOT ==="
raw="$(runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -F '|' \
  -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='10000ms';
WITH labels AS (
 SELECT e.race_id, e.snapshot_label, min(e.snapshot_at) AS observed
 FROM boat_data_stage.entry_snapshots e
 JOIN boat_data_stage.races r ON r.race_id=e.race_id
 WHERE e.source='official_beforeinfo_v5_native'
   AND e.race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
   AND e.snapshot_at>=now()-interval '90 minutes'
   AND e.snapshot_at < r.deadline_at::timestamptz-interval '180 seconds'
 GROUP BY e.race_id,e.snapshot_label
 ORDER BY observed DESC LIMIT 1
)
SELECT
 (SELECT count(*) FROM boat_data_stage.entry_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.exhibition_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.odds_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_odds3t_v5_native'
   AND s.snapshot_at < (SELECT r.deadline_at::timestamptz-interval '180 seconds'
                        FROM boat_data_stage.races r JOIN labels l ON r.race_id=l.race_id)),
 (SELECT count(*) FROM boat_data_stage.weather_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.race_condition_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_beforeinfo_v5_native'),
 (SELECT count(*) FROM boat_data_stage.racer_condition_snapshots s JOIN labels l
   ON (s.race_id,s.snapshot_label)=(l.race_id,l.snapshot_label)
   WHERE s.source='official_beforeinfo_v5_native');
ROLLBACK;
SQL
)"
counts="$(printf '%s\n' "$raw" | grep -E '^[0-9]+([|][0-9]+){5}$' || true)"
echo "V5_NATIVE_REALTIME_LIVE_PROOF=$counts"
[[ "$counts" == "6|6|120|1|1|6" ]] ||
 { echo "HOLD_NO_VERIFIED_SIX_FAMILY_LIVE_SNAPSHOT_KEEP_OLD_RUNNING"; exit 2; }
if [[ "$mode" == "--check" ]]; then
 echo "V5_NORMAL_REALTIME_PARALLEL_READY_NO_CHANGES_OLD_FALLBACK_ON"
 exit 0
fi
[[ "${V5_NATIVE_REALTIME_ENABLE_APPROVED:-NO}" == "YES" ]] ||
 { echo "HOLD_EXPLICIT_NATIVE_PARALLEL_APPROVAL"; exit 2; }
path="/etc/boat-ai-v5-native/canary.env"
[[ ! -e "$path" ]] ||
 { echo "HOLD_ENV_ALREADY_EXISTS_REVIEW_RATHER_THAN_OVERWRITE"; exit 2; }
install -d -m 0750 -o root -g postgres /etc/boat-ai-v5-native
tmp="$(mktemp /etc/boat-ai-v5-native/.realtime.XXXXXXXX)"
trap 'rm -f -- "$tmp"' EXIT
cat > "$tmp" <<'ENV'
V5_NATIVE_CORE_STAGE_WRITE_APPROVED=YES
V5_NATIVE_REALTIME_STAGE_APPROVED=YES
V5_SHARED_PRIMARY_MODE=CANARY
CONFIRM_V5_SHARED_PRIMARY_CANARY=YES
CONFIRM_LEGACY_WRITES_SEPARATELY=YES
V5_STAGE_DELTA_JOURNAL_VERIFIED=YES
BUY_ENABLED=0
AUTO_BUY=0
ENABLE_PURCHASE=0
ENV
chown root:postgres "$tmp"
chmod 0640 "$tmp"
mv "$tmp" "$path"
trap - EXIT
systemctl daemon-reload
systemctl enable --now "$timer"
echo "V5_NORMAL_REALTIME_ALL_VENUES_5MIN_TIMER_ENABLED_OLD_COLLECTION_STILL_RUNNING"
echo "VERIFY_NEW_NATIVE_REALTIME_JOURNAL_AFTER_NEXT_5MIN_SLOT_AND_DAILY_COVERAGE"
echo "DO_NOT_STOP_OLD_UNTIL_PREDICTION_READER_AND_RESULTS_VALIDATED_NO_BUY"
