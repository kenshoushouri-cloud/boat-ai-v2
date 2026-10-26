#!/usr/bin/env bash
# Prepare independent V5 native source and systemd units. NO activation.
# Default CHECK ONLY. Install requires V5_NATIVE_INSTALL_APPROVED=YES.
set -euo pipefail
umask 022
MODE="${1:---check}"
[[ "$MODE" == "--check" || "$MODE" == "--install-only" ]] ||
  { echo "HOLD_ONLY_CHECK_OR_INSTALL_ONLY"; exit 2; }
[[ "$(id -u)" == "0" ]] || { echo "HOLD_ROOT_REQUIRED"; exit 2; }
REPO="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2"
PIN="0bf54530e8b42df68552093722e71bdbacfa52e3"
BASE="/opt/boat-ai-v5-native"
RELEASE="$BASE/releases/$PIN"
UNITS=(boat-v5-native-core-morning boat-v5-native-core-night
       boat-v5-native-realtime boat-v5-native-results)
FILES=(v5/native_core_day_runner.py v5/native_realtime_due_runner.py
       v5/native_results_catchup_stage.py v5/native_official_stage_canary.py
       v5/native_official_index_preview.py v5/native_stage_race_entries_pg.py
       v5/native_official_realtime_stage_pg.py
       v5/direct_shared_primary_routes.py v5/offline_stage_batch_plan.py
       boat_shared_storage_contract.py official_odds3t_parser.py)
echo "V5_NATIVE_DEPLOY_PLAN mode=$MODE pin=$PIN"
echo "V5_OLD_COLLECTORS_WILL_NOT_CHANGE"
echo "V5_NEW_TIMERS_WILL_NOT_AUTO_START"
[[ -x /opt/boat-ai-v5-venv/bin/python ]] ||
  { echo "HOLD_V5_VENV_MISSING"; exit 2; }
[[ -f /opt/boat-ai-v5/repair_month_all_pg.py ]] ||
  { echo "HOLD_EXISTING_TESTED_OFFICIAL_PARSER_MISSING"; exit 2; }
if [[ "$MODE" == "--check" ]]; then
  for n in "${UNITS[@]}"; do echo "PREPARE_ONLY|$n.service|$n.timer"; done
  echo "V5_NATIVE_INSTALL_CHECK_OK_NO_WRITES_NO_UNIT_CHANGES"; exit 0
fi
[[ "${V5_NATIVE_INSTALL_APPROVED:-NO}" == "YES" ]] ||
  { echo "HOLD_EXPLICIT_INSTALL_APPROVAL_REQUIRED"; exit 2; }
[[ ! -e "$RELEASE" ]] || { echo "HOLD_RELEASE_ALREADY_PRESENT"; exit 2; }
for n in "${UNITS[@]}"; do
  for ext in service timer; do
    [[ ! -e "/etc/systemd/system/$n.$ext" ]] ||
      { echo "HOLD_EXISTING_NEW_NATIVE_UNIT_$n.$ext"; exit 2; }
  done
done
temp="$(mktemp -d /tmp/v5-native-install.XXXXXXXX)"
trap 'rm -rf -- "$temp"' EXIT
mkdir -p "$temp/source/v5" "$temp/units"
touch "$temp/source/v5/__init__.py"
for path in "${FILES[@]}"; do
  mkdir -p "$temp/source/$(dirname "$path")"
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 20 \
    "$REPO/$PIN/$path" -o "$temp/source/$path"
done
for n in "${UNITS[@]}"; do
  for ext in service timer; do
    curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 20 \
      "$REPO/$PIN/deploy/conoha/native_units/$n.$ext" \
      -o "$temp/units/$n.$ext"
  done
done
/opt/boat-ai-v5-venv/bin/python - "$temp/source" <<'PY'
import ast, pathlib, sys
files=list(pathlib.Path(sys.argv[1]).rglob("*.py"))
for f in files: ast.parse(f.read_text(encoding="utf-8"),filename=str(f))
print("V5_NATIVE_SOURCE_AST_PASS",len(files))
PY
systemd-analyze verify "$temp/units/"*.service >/dev/null
mkdir -p "$BASE/releases" /etc/boat-ai-v5-native
mv "$temp/source" "$RELEASE"
for n in "${UNITS[@]}"; do
  for ext in service timer; do
    install -m 0644 "$temp/units/$n.$ext" "/etc/systemd/system/$n.$ext"
  done
done
ln -s "$RELEASE" "$BASE/.next-$PIN"
mv -Tf "$BASE/.next-$PIN" "$BASE/current"
systemctl daemon-reload
echo "V5_NATIVE_PREPARED_UNITS_INSTALLED_BUT_TIMERS_NOT_ENABLED"
echo "NEXT_VERIFY_0305_SYNC_CANARY_AND_STAGE_READERS_BEFORE_ACTIVATION"
echo "NO_OLD_STOP_NO_BUY_NO_DATA_DELETE"
