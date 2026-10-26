#!/usr/bin/env bash
# Generic V5 all-venues official exhibition parser hotfix.
# Offline-test then atomically select a NEW immutable native release;
# do not stop/restart existing native or old timers, never BUY.
set -euo pipefail
umask 077
export TZ=Asia/Tokyo
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--install-only" ]] ||
 { echo "HOLD_MODE_CHECK_OR_INSTALL_ONLY"; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "HOLD_ROOT_ONLY"; exit 2; }
root="/opt/boat-ai-v5-native"
old="$root/releases/v5realtime-all-venues-f63bdf36c9d6ae41bba5ec828bd0a61fc7330ee3"
ref="058b5e3a89debc13c7ce394812037281cdb51d82"
new="$root/releases/v5exhibition-structured-$ref"
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo "HOLD_CURRENT_NATIVE_RELEASE_CHANGED"; exit 2; }
[[ -d "$old" && ! -e "$new" ]] ||
 { echo "HOLD_RELEASE_PATH_NOT_READY"; exit 2; }
[[ -x /opt/boat-ai-v5-venv/bin/python ]] ||
 { echo "HOLD_NATIVE_PYTHON_MISSING"; exit 2; }
work="$(mktemp -d /tmp/v5-exhibition-upgrade.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
chmod 0755 "$work"
cp -a "$old" "$work/release"
mkdir -p "$work/release/tests"
url="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$ref"
for path in \
 v5/native_official_realtime_stage_pg.py \
 tests/test_v5_native_official_realtime_stage_pg.py \
 historical_beforeinfo_parser_v3.py; do
 curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "$url/$path" -o "$work/release/$path"
 chmod 0644 "$work/release/$path"
done
chmod 0755 "$work/release" "$work/release/v5" "$work/release/tests"
echo "V5_EXHIBITION_ALL_VENUES_OFFLINE_TEST_BEGIN"
(
 cd "$work/release"
 env -u DATABASE_URL -u V5_NATIVE_REALTIME_STAGE_APPROVED \
     PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work/release" \
     python3 -m unittest discover -s tests \
     -p test_v5_native_official_realtime_stage_pg.py -v
)
echo "V5_EXHIBITION_ALL_VENUES_TEST_PASS"
runuser -u postgres -- env PYTHONDONTWRITEBYTECODE=1 \
 PYTHONPATH="$work/release:/opt/boat-ai-v5" \
 /opt/boat-ai-v5-venv/bin/python -c \
 "from historical_beforeinfo_parser_v3 import inspect_exhibition_time_page; from v5.native_official_realtime_stage_pg import official_structured_exhibition; print('V5_EXHIBITION_PRODUCTION_IMPORT_PASS')"
if [[ "$mode" == "--check" ]]; then
 echo "V5_EXHIBITION_ALL_VENUES_CHECK_PASS_NO_INSTALL_NO_BUY"
 exit 0
fi
[[ "${V5_EXHIBITION_UPGRADE_APPROVED:-NO}" == "YES" ]] ||
 { echo "HOLD_EXPLICIT_UPGRADE_APPROVAL"; exit 2; }
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo "HOLD_NATIVE_RELEASE_CHANGED_DURING_TEST"; exit 2; }
state="$(systemctl is-active boat-v5-native-realtime.service 2>/dev/null || true)"
[[ "$state" != "active" && "$state" != "activating" ]] ||
 { echo "HOLD_NATIVE_REALTIME_SERVICE_CURRENTLY_RUNNING"; exit 2; }
mv "$work/release" "$new"
ln -s "$new" "$root/.next-exhibition-$$"
mv -Tf "$root/.next-exhibition-$$" "$root/current"
echo "V5_EXHIBITION_ALL_VENUES_RELEASE_INSTALLED_NATIVE_TIMERS_UNCHANGED"
echo "OLD_COLLECTION_UNCHANGED_STAGE_ONLY_BUY_OFF"
echo "NEXT_NATIVE_REALTIME_FIVE_MIN_TICK_USES_STRUCTURED_EXHIBITION"
