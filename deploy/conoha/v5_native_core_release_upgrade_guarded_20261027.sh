#!/usr/bin/env bash
# Immutable core hotfix release upgrade after official one-race stage INSERT proof.
# Default --check: no FS/DB writes. --install-only swaps symlink to an
# upgraded copy; native timers must remain disabled; old collectors untouched.
set -euo pipefail
umask 022
MODE="${1:---check}"
[[ "$MODE" == "--check" || "$MODE" == "--install-only" || "$MODE" == "--rollback" ]] || { echo "HOLD_VALID_MODES_ONLY"; exit 2; }
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
ROOT="/opt/boat-ai-v5-native"
BASE_RELEASE="$ROOT/releases/e7625e53792fd1e7a7899d1bb7dd3f65f433cdef"
NEW_RELEASE="$ROOT/releases/v5corefix-056503ca3f774c86156c563e64fe08d8f7d4193c"
REF="056503ca3f774c86156c563e64fe08d8f7d4193c"
RAW="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$REF"
ACTIVE="$(readlink -f "$ROOT/current" || true)"
echo "V5_NATIVE_CORE_RELEASE_UPGRADE mode=$MODE active=$ACTIVE"
for n in core-morning core-night realtime results; do
  unit="boat-v5-native-$n.timer"
  state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  if [[ "$state" == "active" || "$state" == "activating" ]]; then
    echo "HOLD_NATIVE_TIMER_ALREADY_RUNNING_$unit"; exit 2
  fi
done
if [[ "$MODE" == "--rollback" ]]; then
  [[ "${V5_NATIVE_CORE_ROLLBACK_APPROVED:-NO}" == "YES" ]] || { echo "HOLD_ROLLBACK_APPROVAL_REQUIRED"; exit 2; }
  [[ -d "$BASE_RELEASE" && "$ACTIVE" == "$NEW_RELEASE" ]] || { echo "HOLD_UNEXPECTED_ROLLBACK_SOURCE"; exit 2; }
  ln -s "$BASE_RELEASE" "$ROOT/.rollback-$$"
  mv -Tf "$ROOT/.rollback-$$" "$ROOT/current"
  echo "V5_NATIVE_CORE_RELEASE_ROLLBACK_COMPLETE_NEW_TIMERS_STILL_OFF"; exit 0
fi
[[ "$ACTIVE" == "$BASE_RELEASE" ]] || { echo "HOLD_OLD_NATIVE_RELEASE_MISMATCH"; exit 2; }
[[ -d "$BASE_RELEASE" ]] || { echo "HOLD_OLD_RELEASE_MISSING"; exit 2; }
[[ ! -e "$NEW_RELEASE" ]] || { echo "HOLD_NEW_RELEASE_ALREADY_PRESENT"; exit 2; }
echo "=== REQUIRE SINGLE-RACE V5 PHYSICAL WRITE PROOF, READ ONLY ==="
raw_proof="$(runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -F "|" -d railway <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT (SELECT count(*) FROM boat_data_stage.races
         WHERE race_id='20261027_01_01' AND created_at IS NOT NULL),
       (SELECT count(*) FROM boat_data_stage.entries
         WHERE race_id='20261027_01_01' AND id<0
           AND created_at IS NOT NULL AND updated_at IS NOT NULL),
       (SELECT count(DISTINCT lane) FROM boat_data_stage.entries
         WHERE race_id='20261027_01_01' AND id<0);
ROLLBACK;
SQL
)"
# psql may display transaction command tags; extract numeric 3-field SELECT only.
# Reject missing, duplicate, or unequal proof records.
row="$(printf '%s\n' "$raw_proof" | grep -E '^[0-9]+[|][0-9]+[|][0-9]+$' || true)"
echo "V5_NATIVE_CORE_PROOF=$row"
[[ "$row" == "1|6|6" ]] || { echo "HOLD_V5_CORE_NEW_INSERT_NOT_CONFIRMED"; exit 2; }
work="$(mktemp -d /tmp/v5-core-upgrade.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/release/tests"
cp -a "$BASE_RELEASE/." "$work/release/"
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "$RAW/v5/native_stage_race_entries_pg.py" -o "$work/release/v5/native_stage_race_entries_pg.py"
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "$RAW/tests/test_v5_native_stage_race_entries_pg.py" -o "$work/release/tests/test_v5_native_stage_race_entries_pg.py"
echo "=== RUN CORE FIX UNIT TESTS AGAINST UPGRADE CANDIDATE, NO DB/HTTP ==="
(
 cd "$work/release"
 env -u DATABASE_URL -u V5_NATIVE_CORE_STAGE_WRITE_APPROVED \
     -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
     -u V5_STAGE_DELTA_JOURNAL_VERIFIED \
     PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work/release" \
     python3 -m unittest discover -s tests -p test_v5_native_stage_race_entries_pg.py -v
)
echo "V5_NATIVE_CORE_UPGRADE_CANDIDATE_OFFLINE_PASS"
if [[ "$MODE" == "--check" ]]; then
 echo "V5_NATIVE_CORE_RELEASE_UPGRADE_CHECK_PASS_NO_FILES_CHANGED"; exit 0
fi
[[ "${V5_NATIVE_CORE_RELEASE_UPGRADE_APPROVED:-NO}" == "YES" ]] || { echo "HOLD_EXPLICIT_UPGRADE_APPROVAL"; exit 2; }
for n in core-morning core-night realtime results; do
  unit="boat-v5-native-$n.timer"
  state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  [[ "$state" != "active" && "$state" != "activating" ]] || { echo "HOLD_TIMER_STARTED_DURING_CHECK_$unit"; exit 2; }
done
[[ "$(readlink -f "$ROOT/current")" == "$BASE_RELEASE" ]] || { echo "HOLD_SYMLINK_CHANGED_DURING_CHECK"; exit 2; }
install -d -m 0755 "$ROOT/releases"
mv "$work/release" "$NEW_RELEASE"
ln -s "$NEW_RELEASE" "$ROOT/.next-corefix-$$"
mv -Tf "$ROOT/.next-corefix-$$" "$ROOT/current"
echo "V5_NATIVE_CORE_RELEASE_UPGRADED_SOURCE_ONLY_NATIVE_TIMERS_STILL_DISABLED"
echo "OLD_COLLECTION_UNCHANGED_NO_BUY_NO_DATA_DELETE"
