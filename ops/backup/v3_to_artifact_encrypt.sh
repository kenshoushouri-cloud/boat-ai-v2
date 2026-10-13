#!/usr/bin/env bash
# PREPARED / NOT WIRED TO A WORKFLOW. Never runs automatically.
# V3 only: Railway public TCP -> PostgreSQL 18 pg_dump -> age-encrypted local artifact.
# Intended for ephemeral GitHub Actions runner ONLY after specific user approval.
# No plaintext dump is written to disk; no DB writes; no Railway service changes.
set -euo pipefail
umask 077

fail() { printf 'V3_ARTIFACT_ABORT=%s\n' "$1" >&2; exit 1; }

mode="${V3_BACKUP_MODE:-plan}"
case "$mode" in
  plan)
    printf 'V3_ARTIFACT_STATUS=NOT_EXECUTED\n'
    printf 'V3_ARTIFACT_NEXT=separate_approval_and_recovery_key_required\n'
    exit 0 ;;
  validate|execute) ;;
  *) fail 'invalid_mode' ;;
esac

# All human-approval gates are evaluated BEFORE reading credentials or dialing a DB.
[[ "${V3_BACKUP_TARGET:-}" == v3 ]] || fail 'target_must_be_v3'
[[ "${V3_EXPECTED_SERVICE_ID:-}" == '03652c28-20fa-4807-aa8c-8e71b6f21d26' ]] \
  || fail 'v3_service_identity_not_approved'
[[ "${GITHUB_ACTIONS:-}" == true ]] || fail 'github_actions_runner_required'
[[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]{7,}$ ]] || fail 'github_run_id_required'
if [[ "$mode" == execute ]]; then
  [[ "${V3_BACKUP_EXECUTE_APPROVED:-}" == 'YES_SINGLE_V3_ENCRYPTED_SNAPSHOT' ]] \
    || fail 'backup_not_approved'
  [[ "${V3_CONFIRM_WAKE_AND_NETWORK_COST:-}" == YES ]] \
    || fail 'wake_and_network_cost_not_approved'
  [[ "${V3_RECOVERY_KEY_VERIFIED_OFFLINE:-}" == YES ]] \
    || fail 'recovery_key_test_not_confirmed'
fi

: "${V3_SOURCE_DATABASE_URL:?private database URL must be set as runner secret}"
: "${V3_EXPECTED_HOST:?independently approved Railway V3 proxy host required}"
: "${V3_EXPECTED_PORT:?independently approved Railway V3 proxy port required}"
: "${V3_EXPECTED_DATABASE:?independently approved V3 DB name required}"
: "${V3_AGE_RECIPIENT:?user-owned age public recipient required}"
: "${V3_AGE_RECIPIENT_SHA256:?independently verified recipient hash required}"
: "${RUNNER_TEMP:?GitHub runner ephemeral temp dir required}"
[[ -d "$RUNNER_TEMP" ]] || fail 'runner_temp_unavailable'
[[ "$V3_EXPECTED_PORT" =~ ^[0-9]{1,5}$ ]] || fail 'expected_port_invalid'
(( 10#$V3_EXPECTED_PORT >= 1 && 10#$V3_EXPECTED_PORT <= 65535 )) \
  || fail 'expected_port_out_of_range'
[[ "$V3_AGE_RECIPIENT" =~ ^age1[0-9a-z]+$ ]] || fail 'recipient_format_invalid'
[[ "$V3_AGE_RECIPIENT_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail 'recipient_pin_format_invalid'
actual_recipient_sha="$(printf '%s' "$V3_AGE_RECIPIENT" | sha256sum | awk '{print $1}')"
[[ "$actual_recipient_sha" == "$V3_AGE_RECIPIENT_SHA256" ]] || fail 'recipient_pin_mismatch'

# Check the URL in-memory. NEVER echo URI, username, passwords or full env.
source_identity="$(python3 - <<'PY'
import os, sys
from urllib.parse import urlsplit, parse_qs, unquote
try:
    url = urlsplit(os.environ['V3_SOURCE_DATABASE_URL'])
    if url.scheme not in ('postgresql', 'postgres') or not url.hostname or not url.username:
        raise ValueError()
    if url.password is None or not url.path or url.path == '/':
        raise ValueError()
    port = url.port
    if port is None or not 1 <= port <= 65535:
        raise ValueError()
    sslmode = parse_qs(url.query).get('sslmode', [None])[-1]
    if sslmode not in (None, 'require', 'verify-ca', 'verify-full'):
        raise ValueError()
    print(f'{url.hostname}|{port}|{unquote(url.path.lstrip("/"))}')
except (ValueError, KeyError, TypeError):
    sys.exit(2)
PY
)" || fail 'url_malformed_or_insecure'
IFS='|' read -r actual_host actual_port actual_db <<< "$source_identity"
[[ "$actual_host" == "$V3_EXPECTED_HOST" ]] || fail 'source_host_mismatch'
[[ "$actual_port" == "$V3_EXPECTED_PORT" ]] || fail 'source_port_mismatch'
[[ "$actual_db" == "$V3_EXPECTED_DATABASE" ]] || fail 'source_database_mismatch'
unset source_identity actual_host actual_port actual_db

for cmd in python3 pg_dump psql age sha256sum awk; do
  command -v "$cmd" >/dev/null 2>&1 || fail "missing_tool_$cmd"
done
[[ "$(pg_dump --version)" == *' 18.'* ]] || fail 'pg_dump_18_required'
[[ "$(psql --version)" == *' 18.'* ]] || fail 'psql_18_required'

printf 'V3_ARTIFACT_STATIC_PREFLIGHT=PASS\n'
if [[ "$mode" == validate ]]; then
  printf 'V3_ARTIFACT_DB_CONNECTION=NOT_ATTEMPTED\n'
  exit 0
fi

# The first line after this point may contact (and wake) old V3. No automatic workflow calls this script.
export PGSSLMODE=require
export PGOPTIONS='-c default_transaction_read_only=on'
db_identity="$(psql "$V3_SOURCE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -F '|' \
  -c "SELECT current_database(), current_setting('server_version_num'), pg_is_in_recovery()")" \
  || fail 'read_only_db_connection_failed'
IFS='|' read -r db_name db_version in_recovery <<< "$db_identity"
[[ "$db_name" == "$V3_EXPECTED_DATABASE" ]] || fail 'connected_db_identity_mismatch'
[[ "$db_version" =~ ^18[0-9]{4}$ ]] || fail 'connected_pg18_required'
[[ "$in_recovery" == f ]] || fail 'source_is_not_primary'
unset db_identity db_name db_version in_recovery

outdir="$RUNNER_TEMP/boat-ai-v3-encrypted"
mkdir -p -m 700 -- "$outdir"
runstamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="boat-ai-current-v3-${runstamp}-${GITHUB_RUN_ID:-manual}.dump.age"
staged="$outdir/${filename}.partial"
completed="$outdir/$filename"
cleanup() { rm -f -- "$staged"; }
trap cleanup EXIT

# pg_dump is read-only. Encrypted data only is written to the runner's ephemeral directory.
pg_dump "$V3_SOURCE_DATABASE_URL" --format=custom --compress=gzip:6 --no-owner --no-acl \
  | age -r "$V3_AGE_RECIPIENT" > "$staged" \
  || fail 'encrypted_pipeline_failed'
[[ -s "$staged" ]] || fail 'encrypted_output_empty'
mv -- "$staged" "$completed"
encrypted_sha="$(sha256sum -- "$completed" | awk '{print $1}')"
printf '%s  %s\n' "$encrypted_sha" "$filename" > "${completed}.sha256"
chmod 600 -- "$completed" "${completed}.sha256"
printf 'V3_ARTIFACT_ENCRYPTED_ONLY=YES\n'
printf 'V3_ARTIFACT_OUTPUT_DIR=%s\n' "$outdir"
printf 'V3_ARTIFACT_RESTORE_VERIFIED=NO\n'
printf 'V3_ARTIFACT_DO_NOT_DELETE_SOURCE=YES\n'