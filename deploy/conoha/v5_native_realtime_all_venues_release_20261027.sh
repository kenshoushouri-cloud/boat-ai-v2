#!/usr/bin/env bash
# Install corrected V5-native realtime collector for ALL venues and races.
# This is NOT a Karatsu-specific artifact. It changes only an immutable
# V5-native source release. Old collectors / old tables / BUY are untouched.
# Default --check runs offline tests and read-only six-family PG schema audit.
set -euo pipefail
umask 077
mode="${1:---check}"
[[ "$mode" == "--check" || "$mode" == "--install-only" ]] ||
 { echo "HOLD_CHECK_OR_INSTALL_ONLY"; exit 2; }
[[ "$(id -u)" -eq 0 ]] || { echo "HOLD_ROOT_ONLY"; exit 2; }
root="/opt/boat-ai-v5-native"
old="$root/releases/v5corefix-056503ca3f774c86156c563e64fe08d8f7d4193c"
ref="f63bdf36c9d6ae41bba5ec828bd0a61fc7330ee3"
new="$root/releases/v5realtime-all-venues-$ref"
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo "HOLD_NATIVE_CURRENT_RELEASE_UNEXPECTED"; exit 2; }
[[ -x /opt/boat-ai-v5-venv/bin/python ]] ||
 { echo "HOLD_V5_PYTHON_MISSING"; exit 2; }
[[ ! -e "$new" ]] || { echo "HOLD_RELEASE_ALREADY_EXISTS"; exit 2; }
for name in core-morning core-night core-refresh realtime results; do
  unit="boat-v5-native-$name.timer"
  state="$(systemctl is-active "$unit" 2>/dev/null || true)"
  [[ "$state" != "active" && "$state" != "activating" ]] ||
   { echo "HOLD_NATIVE_TIMER_CURRENTLY_RUNNING_$name"; exit 2; }
done
work="$(mktemp -d /tmp/v5-all-venues-upgrade.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT
chmod 755 "$work"
mkdir -p "$work/release/tests"
cp -a "$old/." "$work/release/"
raw="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/$ref"
for path in \
 v5/native_official_realtime_stage_pg.py \
 v5/native_realtime_due_runner.py \
 v5/native_results_catchup_stage.py \
 tests/test_v5_native_official_realtime_stage_pg.py \
 tests/test_v5_native_transition_20261027.py; do
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
   "$raw/$path" -o "$work/release/$path"
  chmod 644 "$work/release/$path"
done
echo "=== V5 ALL-VENUE NATIVE REALTIME OFFLINE TESTS ==="
(
 cd "$work/release"
 env -u DATABASE_URL -u V5_NATIVE_REALTIME_STAGE_APPROVED \
     -u V5_SHARED_PRIMARY_MODE -u CONFIRM_V5_SHARED_PRIMARY_CANARY \
     -u CONFIRM_LEGACY_WRITES_SEPARATELY \
     PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work/release" \
     python3 -m unittest discover -s tests -p 'test_v5_native_*.py' -v
)
echo "V5_ALL_VENUES_REALTIME_OFFLINE_PASS"
echo "=== V5 SIX-FAMILY PHYSICAL STAGE SCHEMA READ ONLY ==="
chmod 755 "$work/release" "$work/release/v5"
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
 PYTHONPATH="$work/release:/opt/boat-ai-v5" \
 /opt/boat-ai-v5-venv/bin/python - <<'PY'
from psycopg import connect
from v5.native_official_realtime_stage_pg import COLUMN_SETS,SNAPSHOT_KEYS
with connect("postgresql:///railway",connect_timeout=5,autocommit=True) as db:
    with db.transaction():
        with db.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SET LOCAL statement_timeout='6000ms'")
            for family, cols in COLUMN_SETS.items():
                rel="boat_data_stage."+family
                c.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",(rel,))
                kind=c.fetchone()
                if not kind or kind[0] not in ("r","p"):
                    raise RuntimeError("HOLD_NOT_PHYSICAL_"+family)
                c.execute("""SELECT attname,attnotnull,atthasdef,attidentity,
                                      attgenerated,atttypid
                    FROM pg_attribute WHERE attrelid=to_regclass(%s)
                      AND attnum>0 AND NOT attisdropped""",(rel,))
                catalog=c.fetchall()
                existing={x[0] for x in catalog}
                required=[x[0] for x in catalog
                          if x[1] and not (x[2] or x[3] or x[4])
                          and x[0] not in cols]
                if required or not set(cols)<=existing:
                    raise RuntimeError("HOLD_REQUIRED_STAGE_COLUMNS_"+family+":"+str(required))
                c.execute("""SELECT array_agg(a.attname ORDER BY j.ord)
                    FROM pg_index i JOIN LATERAL unnest(i.indkey)
                        WITH ORDINALITY j(num,ord) ON j.ord<=i.indnkeyatts
                    JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=j.num
                    WHERE i.indrelid=to_regclass(%s) AND i.indisunique
                      AND i.indisvalid AND i.indpred IS NULL AND i.indexprs IS NULL
                    GROUP BY i.indexrelid""",(rel,))
                unique_keys={tuple(z[0]) for z in c.fetchall()}
                if tuple(SNAPSHOT_KEYS[family]) not in unique_keys or ("id",) not in unique_keys:
                    raise RuntimeError("HOLD_UNIQUE_KEY_"+family)
                print("NATIVE_STAGE_SCHEMA_OK|"+family,flush=True)
print("V5_ALL_VENUES_REALTIME_SIX_SCHEMA_PASS_NO_WRITES",flush=True)
PY
if [[ "$mode" == "--check" ]]; then
 echo "V5_ALL_VENUES_REALTIME_SOURCE_CHECK_PASS_NO_INSTALL_NO_TIMERS_NO_BUY"
 exit 0
fi
[[ "${V5_NATIVE_REALTIME_GLOBAL_INSTALL_APPROVED:-NO}" == "YES" ]] ||
 { echo "HOLD_EXPLICIT_INSTALL_APPROVAL"; exit 2; }
[[ "$(readlink -f "$root/current")" == "$old" ]] ||
 { echo "HOLD_RELEASE_CHANGED_DURING_TEST"; exit 2; }
for name in core-morning core-night core-refresh realtime results; do
  [[ "$(systemctl is-active "boat-v5-native-$name.timer" 2>/dev/null || true)" != "active" ]] ||
   { echo "HOLD_NATIVE_TIMER_STARTED_DURING_TEST"; exit 2; }
done
mv "$work/release" "$new"
ln -s "$new" "$root/.next-all-venues-$$"
mv -Tf "$root/.next-all-venues-$$" "$root/current"
echo "V5_NATIVE_REALTIME_ALL_VENUES_RELEASE_INSTALLED_TIMERS_STILL_DISABLED"
echo "OLD_COLLECTORS_UNCHANGED_OLD_DATA_UNTOUCHED_NO_BUY"
echo "NEXT_RUN_1R_NATIVE_REALTIME_CAPTURE_TO_PROVE_LIVE_140_ROWS_BEFORE_ENABLING_TIMER"
