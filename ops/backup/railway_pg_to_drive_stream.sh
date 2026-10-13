#!/usr/bin/env bash
# ONE-SHOT V4 or V5 PostgreSQL 18 logical backup, encrypted to Google Drive.
# NOT a cron. No backup is stored in a Railway PostgreSQL volume.
# Requires separately configured rclone remotes:
#   boat-drive-v4 -> Google account A, root_folder_id = V4 private folder
#   boat-drive-v5 -> Google account B, root_folder_id = V5 private folder
# Do not put DATABASE_URL, OAuth tokens, private age keys or rclone.conf in GitHub/chat.
set -euo pipefail
umask 077

fail() { printf 'BACKUP_ABORT=%s\n' "$1" >&2; exit 1; }
mode="${BACKUP_MODE:-preflight}"
target="${BACKUP_TARGET:-}"
case "$target" in
  v4) remote='boat-drive-v4' ;;
  v5) remote='boat-drive-v5' ;;
  *) fail 'BACKUP_TARGET_must_be_v4_or_v5' ;;
esac
case "$mode" in preflight|execute) ;; *) fail 'invalid_BACKUP_MODE' ;; esac

# Execute mode fails before any connection unless separately authorized.
if [[ "$mode" == execute ]]; then
  [[ "${BACKUP_EXECUTE_APPROVED:-}" == YES ]] || fail 'execution_not_approved'
fi

: "${SOURCE_DATABASE_URL:?Set source Railway DB URL in secret variables}"
: "${SOURCE_EXPECTED_HOST:?Independently verify the approved DB host for this target}"
: "${DRIVE_EXPECTED_FOLDER_ID:?Set the approved private Drive folder ID}"
: "${AGE_RECIPIENT:?Set public age1 recipient; NEVER the private key}"
[[ "$AGE_RECIPIENT" =~ ^age1[0-9a-z]+$ ]] || fail 'invalid_age_recipient'
[[ "$DRIVE_EXPECTED_FOLDER_ID" =~ ^[A-Za-z0-9_-]{12,}$ ]] || fail 'invalid_drive_folder_id'
for bin in pg_dump psql age rclone sha256sum mkfifo python3 tee awk grep; do
  command -v "$bin" >/dev/null || fail "missing_tool_${bin}"
done
[[ "$(pg_dump --version)" == *' 18.'* ]] || fail 'pg_dump_18_required'
[[ "$(psql --version)" == *' 18.'* ]] || fail 'psql_18_required'
# Check DB URI host without printing credentials from SOURCE_DATABASE_URL.
actual_host="$(python3 - <<'PY'
import os
from urllib.parse import urlsplit
try:
    parsed = urlsplit(os.environ['SOURCE_DATABASE_URL'])
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname:
        raise ValueError('invalid URI')
    print(parsed.hostname)
except (ValueError, KeyError):
    raise SystemExit(11)
PY
)" || fail 'source_url_malformed'
[[ "$actual_host" == "$SOURCE_EXPECTED_HOST" ]] || fail 'source_host_mismatch'

rclone listremotes | grep -Fxq "${remote}:" || fail 'matching_rclone_remote_not_configured'
# config show can contain OAuth secrets; capture in memory, NEVER print.
remote_config="$(rclone config show "$remote")" || fail 'rclone_config_unreadable'
configured_folder="$(printf '%s\n' "$remote_config" | awk -F '=' '
  /^[[:space:]]*root_folder_id[[:space:]]*=/ {
    sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2); print $2
  }
')"
unset remote_config
[[ "$configured_folder" == "$DRIVE_EXPECTED_FOLDER_ID" ]] || fail 'drive_root_folder_mismatch'

# Read-only connection test (does not count rows or scan application tables).
export PGOPTIONS='-c default_transaction_read_only=on'
db_version="$(psql "$SOURCE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 \
  -c "select current_setting('server_version_num')")" || fail 'db_readonly_preflight_failed'
[[ "$db_version" =~ ^18[0-9]{4}$ ]] || fail 'source_postgres_18_required'
rclone lsf "${remote}:" --max-depth 1 >/dev/null || fail 'drive_folder_not_accessible'
printf 'BACKUP_PREFLIGHT_OK target=%s pg_major=18 root_folder_confirmed=YES\n' "$target"

if [[ "$mode" == preflight ]]; then
  printf 'BACKUP_TRANSFER=NOT_STARTED\n'
  exit 0
fi
# pg_dump -Fc is internally gzip-compressed; globals (roles/tablespaces)
# are NOT included and require a separate verified inventory. age encrypts the complete stream.
# A FIFO records SHA-256 of ciphertext without writing any dump to a volume.
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="boat-ai-${target}-${stamp}.dump.age"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT
mkfifo "$tmpdir/hash-fifo"
sha256sum < "$tmpdir/hash-fifo" > "$tmpdir/sha256" &
sha_pid=$!

if pg_dump "$SOURCE_DATABASE_URL" --format=custom --compress=gzip:6 \
    --no-owner --no-acl \
  | age -r "$AGE_RECIPIENT" \
  | tee "$tmpdir/hash-fifo" \
  | rclone rcat "${remote}:${filename}" --drive-chunk-size 16M; then
  wait "$sha_pid" || fail 'sha256_failed'
else
  wait "$sha_pid" || true
  fail 'dump_encrypt_or_upload_failed; remote_partial_possible'
fi

checksum="$(awk '{print $1}' "$tmpdir/sha256")"
[[ "$checksum" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid_checksum'
printf '%s  %s\n' "$checksum" "$filename" \
  | rclone rcat "${remote}:${filename}.sha256"
rclone lsf "${remote}:" --files-only | grep -Fxq "$filename" \
  || fail 'remote_backup_file_not_listed'
printf 'BACKUP_UPLOAD_DONE target=%s encrypted_file=%s local_sha256=%s\n' "$target" "$filename" "$checksum"
printf 'REMOTE_BYTES_CHECKED=NO; RESTORE_VERIFIED=NO; DO_NOT_DELETE_SOURCE_OR_STOP_PRODUCTION\n'
