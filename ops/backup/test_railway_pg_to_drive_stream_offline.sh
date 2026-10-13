#!/usr/bin/env bash
# Hermetic, fake-credential tests; never connects to Railway / Google Drive.
set -euo pipefail
set +x
base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
script="$base/railway_pg_to_drive_stream.sh"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/bin"
for cmd in psql pg_dump age rclone; do
  cat > "$tmp/bin/$cmd" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == --version && ("${0##*/}" == psql || "${0##*/}" == pg_dump) ]]; then
  printf '%s (PostgreSQL) 18.1\n' "${0##*/}"
  exit 0
fi
printf 'MOCK_MUST_NOT_CONNECT=%s\n' "${0##*/}" >&2
exit 97
EOF
  chmod +x "$tmp/bin/$cmd"
done
export PATH="$tmp/bin:$PATH"
pass=0
check() {
  local name="$1" want_code="$2" want_text="$3"
  shift 3
  local code=0
  "$@" >"$tmp/out" 2>&1 || code="$?"
  if [[ "$code" == "$want_code" ]] && grep -Fq -- "$want_text" "$tmp/out" \
    && ! grep -Fq 'MOCK_MUST_NOT_CONNECT' "$tmp/out"; then
    pass=$((pass+1))
    printf 'PASS %s\n' "$name"
  else
    printf 'FAIL %s code:%s expected:%s\n' "$name" "$code" "$want_code" >&2
    cat "$tmp/out" >&2
    exit 1
  fi
}
bash -n "$script" || exit 1
check 'default plan requires no credentials, DB or OAuth' 0 'BACKUP_CONNECTION=NOT_ATTEMPTED' bash "$script"
check 'execute rejects missing approvals before reading secrets' 1 'BACKUP_ABORT=connection_not_approved' \
  env BACKUP_MODE=execute BACKUP_TARGET=v3 bash "$script"
check 'preflight rejects connection before reading secrets' 1 'BACKUP_ABORT=connection_not_approved' \
  env BACKUP_MODE=preflight BACKUP_TARGET=v3 bash "$script"
check 'preflight requires wake and network cost approval' 1 'BACKUP_ABORT=network_cost_not_approved' \
  env BACKUP_MODE=preflight BACKUP_TARGET=v3 BACKUP_CONNECT_APPROVED=YES bash "$script"
check 'execute requires approval beyond connection costs' 1 'BACKUP_ABORT=execution_not_approved' \
  env BACKUP_MODE=execute BACKUP_TARGET=v3 BACKUP_CONNECT_APPROVED=YES BACKUP_NETWORK_COST_APPROVED=YES bash "$script"
check 'execute requires real owner recovery test' 1 'BACKUP_ABORT=recovery_key_test_not_confirmed' \
  env BACKUP_MODE=execute BACKUP_TARGET=v3 BACKUP_CONNECT_APPROVED=YES BACKUP_NETWORK_COST_APPROVED=YES BACKUP_EXECUTE_APPROVED=YES bash "$script"
check 'invalid target rejected' 1 'BACKUP_ABORT=BACKUP_TARGET_must_be_v3_v4_v5_or_archive' \
  env BACKUP_MODE=validate BACKUP_TARGET=other bash "$script"
pub="$(tr -d '\r\n' < "$base/keys/v3_recovery_recipient_20261013.pub")"
pin="$(printf %s "$pub" | sha256sum | awk '{print $1}')"
export SOURCE_DATABASE_URL='postgresql://mock:mock@proxy.example:46406/boatdb?sslmode=require'
export SOURCE_EXPECTED_HOST=proxy.example SOURCE_EXPECTED_PORT=46406 SOURCE_EXPECTED_DATABASE=boatdb
export DRIVE_EXPECTED_FOLDER_ID=mockFolder1234567890
export AGE_RECIPIENT="$pub" AGE_EXPECTED_RECIPIENT_SHA256="$pin"
check 'valid pinned SSH recipient offline static pass' 0 'BACKUP_STATIC_PREFLIGHT=PASS' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 bash "$script"
check 'wrong public key with matching wrong hash rejected' 1 'BACKUP_ABORT=v3_recipient_not_preapproved' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 AGE_RECIPIENT='age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq' AGE_EXPECTED_RECIPIENT_SHA256="$(printf %s age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq | sha256sum | awk '{print $1}')" bash "$script"
check 'wrong port rejected before network' 1 'BACKUP_ABORT=source_port_mismatch' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 SOURCE_EXPECTED_PORT=46407 bash "$script"
check 'wrong DB rejected before network' 1 'BACKUP_ABORT=source_database_name_mismatch' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 SOURCE_EXPECTED_DATABASE=notboatdb bash "$script"
check 'insecure TLS rejected before network' 1 'BACKUP_ABORT=source_url_malformed_or_missing_port' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 SOURCE_DATABASE_URL='postgresql://mock:mock@proxy.example:46406/boatdb?sslmode=disable' bash "$script"
check 'missing TLS rejected before network' 1 'BACKUP_ABORT=source_url_malformed_or_missing_port' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 SOURCE_DATABASE_URL='postgresql://mock:mock@proxy.example:46406/boatdb' bash "$script"
check 'recipient hash mismatch rejected' 1 'BACKUP_ABORT=age_recipient_fingerprint_mismatch' \
  env BACKUP_MODE=validate BACKUP_TARGET=v3 AGE_EXPECTED_RECIPIENT_SHA256="$(printf '%064d' 0)" bash "$script"
! grep -Fq 'pg_dump "$SOURCE_DATABASE_URL"' "$script" || exit 1
! grep -Fq 'psql "$SOURCE_DATABASE_URL"' "$script" || exit 1
grep -Fq 'export PGDATABASE="$SOURCE_DATABASE_URL"' "$script" || exit 1
grep -Fq 'set +x' "$script" || exit 1
printf 'PASS secret_argument_and_shell_trace_guards\n'
printf 'OFFLINE_TESTS=%s/14 PASS\n' "$pass"
