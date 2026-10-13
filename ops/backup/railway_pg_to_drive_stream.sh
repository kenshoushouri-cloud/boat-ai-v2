#!/usr/bin/env bash
# ONE-SHOT V3/V4/V5/archive PostgreSQL 18 logical backup, encrypted to Google Drive.
# NOT a cron. No backup is stored in a Railway PostgreSQL volume.
# Requires separately configured rclone remotes and private folder IDs:
#   boat-drive-v4      -> Google account A, V4 folder
#   boat-drive-v3      -> Google account A, independent V3 folder
#   boat-drive-archive -> Google account A, independent history-archive folder
#   boat-drive-v5      -> Google account B, V5 folder
# Same Google account A does NOT mean reusing V4's private folder.
# Do not put DATABASE_URL, OAuth tokens, private age keys or rclone.conf in GitHub/chat.
set -euo pipefail
umask 077

fail() { printf 'BACKUP_ABORT=%s\n' "$1" >&2; exit 1; }
mode="${BACKUP_MODE:-preflight}"
target="${BACKUP_TARGET:-}"
case "$target" in
  v4)      remote='boat-drive-v4' ;;
  v3)      remote='boat-drive-v3' ;;
  archive) remote='boat-drive-archive' ;;
  v5)      remote='boat-drive-v5' ;;
  *) fail 'BACKUP_TARGET_must_be_v3_v4_v5_or_archive' ;;
esac
case "$mode" in preflight|execute) ;; *) fail 'invalid_BACKUP_MODE' ;; esac

# Execute mode fails before any connection unless separately authorized.
if [[ "$mode" == execute ]]; then
  [[ "${BACKUP_EXECUTE_APPROVED:-}" == YES ]] || fail 'execution_not_approved'
fi

: "${SOURCE_DATABASE_URL:?Set source Railway DB URL in secret variables}"
: "${SOURCE_EXPECTED_HOST:?Independently verify the approved DB host for this target}"
: "${SOURCE_EXPECTED_DATABASE:?Independently verify the approved DB name for this target}"
: "${DRIVE_EXPECTED_FOLDER_ID:?Set the approved private Drive folder ID}"
: "${AGE_RECIPIENT:?Set public age1 recipient; NEVER the private key}"
: "${AGE_EXPECTED_RECIPIENT_SHA256:?Pin independently verified recovery public key fingerprint}"
[[ "$AGE_RECIPIENT" =~ ^age1[0-9a-z]+$ ]] || fail 'invalid_age_recipient'
[[ "$AGE_EXPECTED_RECIPIENT_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid_expected_age_fingerprint'
recipient_fingerprint="$(printf '%s' "$AGE_RECIPIENT" | sha256sum | awk '{print $1}')"
[[ "$recipient_fingerprint" == "$AGE_EXPECTED_RECIPIENT_SHA256" ]] || fail 'age_recipient_fingerprint_mismatch'
# This fingerprint must be documented separately from the AGE_RECIPIENT
# env var; otherwise a simultaneous accidental change could pass the check.
[[ "$DRIVE_EXPECTED_FOLDER_ID" =~ ^[A-Za-z0-9_-]{12,}$ ]] || fail 'invalid_drive_folder_id'
for bin in pg_dump psql age rclone sha256sum md5sum mkfifo python3 tee awk grep; do
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
# Keep OAuth tokens in memory and never log the remote config.
configured_folder="$(printf '%s\n' "$remote_config" | awk -F '=' '
  /^[[:space:]]*root_folder_id[[:space:]]*=/ {
    sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2); print $2
  }
')"
configured_client_id="$(printf '%s\n' "$remote_config" | awk -F '=' '
  /^[[:space:]]*client_id[[:space:]]*=/ {
    sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2); print $2
  }
')"
configured_scope="$(printf '%s\n' "$remote_config" | awk -F '=' '
  /^[[:space:]]*scope[[:space:]]*=/ {
    sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2); print $2
  }
')"
configured_type="$(printf '%s\n' "$remote_config" | awk -F '=' '
  /^[[:space:]]*type[[:space:]]*=/ {
    sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2); print $2
  }
')"
unset remote_config
[[ "$configured_type" == drive ]] || fail 'remote_backend_not_google_drive'
[[ "$configured_folder" == "$DRIVE_EXPECTED_FOLDER_ID" ]] || fail 'drive_root_folder_mismatch'
# The rclone shared client_id is being retired in 2026.
[[ "$configured_client_id" == *.apps.googleusercontent.com ]] \
  || fail 'private_oauth_client_id_required'
# Existing user-created folders are not accessible using drive.file by default.
# This scope grants access to all Drive files in the chosen dedicated account.
[[ "$configured_scope" == drive ]] || fail 'drive_scope_must_be_explicitly_full'

# Read-only connection test (does not count rows or scan application tables).
export PGOPTIONS='-c default_transaction_read_only=on'
db_identity="$(psql "$SOURCE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -F '|' \
  -c "select current_database(), current_setting('server_version_num')")" \
  || fail 'db_readonly_preflight_failed'
IFS='|' read -r actual_database db_version <<< "$db_identity"
[[ "$actual_database" == "$SOURCE_EXPECTED_DATABASE" ]] || fail 'source_database_name_mismatch'
[[ "$db_version" =~ ^18[0-9]{4}$ ]] || fail 'source_postgres_18_required'
rclone lsf "${remote}:" --max-depth 1 >/dev/null || fail 'drive_folder_not_accessible'
printf 'BACKUP_PREFLIGHT_OK target=%s pg_major=18 root_folder_confirmed=YES\n' "$target"

if [[ "$mode" == preflight ]]; then
  printf 'BACKUP_TRANSFER=NOT_STARTED\n'
  exit 0
fi
# pg_dump -Fc is internally compressed, age encrypts the whole stream.
# An incomplete or unverified transfer MUST NOT appear under a normal backup name.
# A failed .uploading file may remain; never auto-delete remote data.
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_id="$(python3 -c 'import secrets; print(secrets.token_hex(5))')"
filename="boat-ai-${target}-${stamp}-${run_id}.dump.age"
staged="${filename}.uploading"
tmpdir="$(mktemp -d)"
trap 'rm -rf -- "$tmpdir"' EXIT
mkfifo "$tmpdir/hash-fifo" "$tmpdir/md5-fifo"
sha256sum < "$tmpdir/hash-fifo" > "$tmpdir/sha256" &
sha_pid=$!
md5sum < "$tmpdir/md5-fifo" > "$tmpdir/md5" &
md5_pid=$!

# Neither source database nor its attached volume receives a backup file.
# On pipeline failure, pipefail forces a nonzero exit; no promotion occurs.
if pg_dump "$SOURCE_DATABASE_URL" --format=custom --compress=gzip:6 \
    --no-owner --no-acl \
  | age -r "$AGE_RECIPIENT" \
  | tee "$tmpdir/hash-fifo" "$tmpdir/md5-fifo" \
  | rclone rcat "${remote}:${staged}" --drive-chunk-size 16M; then
  wait "$sha_pid" || fail 'local_sha256_failed'
  wait "$md5_pid" || fail 'local_md5_failed'
else
  wait "$sha_pid" || true
  wait "$md5_pid" || true
  fail 'pipeline_failed; unverified_uploading_file_may_remain'
fi

checksum="$(awk '{print $1}' "$tmpdir/sha256")"
local_md5="$(awk '{print $1}' "$tmpdir/md5")"
[[ "$checksum" =~ ^[0-9a-f]{64}$ ]] || fail 'invalid_local_sha256'
[[ "$local_md5" =~ ^[0-9a-f]{32}$ ]] || fail 'invalid_local_md5'

# Google Drive provides an MD5 checksum for binary files. Compare it against
# the local encrypted stream without downloading gigabytes a second time.
# MD5 here is an accidental-transfer-corruption check, NOT a substitute for
# authenticated age decryption and a separate, complete restore drill.
remote_md5="$(rclone md5sum "${remote}:${staged}" | awk 'NR == 1 {print $1}')" \
  || fail 'remote_md5_unavailable; staging_not_promoted'
[[ "$remote_md5" == "$local_md5" ]] \
  || fail 'remote_md5_mismatch; staging_not_promoted'

# Write checksum metadata BEFORE promoting the encrypted backup.
printf '%s  %s\n' "$checksum" "$filename" \
  | rclone rcat "${remote}:${filename}.sha256" \
  || fail 'checksum_upload_failed; staging_not_promoted'

rclone moveto "${remote}:${staged}" "${remote}:${filename}" \
  || fail 'promotion_failed; check_staging_and_final_paths'
rclone lsf "${remote}:" --files-only | grep -Fxq "$filename" \
  || fail 'promoted_backup_not_listed'

printf 'BACKUP_UPLOAD_DONE target=%s encrypted_file=%s local_sha256=%s\n' "$target" "$filename" "$checksum"
printf 'REMOTE_MD5_MATCH=YES; REMOTE_SHA256_VERIFIED=NO; RESTORE_VERIFIED=NO\n'
printf 'DO_NOT_DELETE_SOURCE_OR_STOP_PRODUCTION\n'
