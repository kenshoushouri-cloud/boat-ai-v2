#!/usr/bin/env bash
# Offline ONLY. NEVER connects to Railway or handles real credentials.
set -euo pipefail
script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/v3_to_artifact_encrypt.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
for app in psql pg_dump age; do
  cat > "$tmp/bin/$app" <<'APP'
#!/usr/bin/env bash
if [[ "${1:-}" == --version ]]; then
  printf '%s (PostgreSQL) 18.1\n' "$(basename "$0")"
  exit 0
fi
printf 'MOCK_MUST_NOT_CONNECT\n' >&2
exit 97
APP
  chmod +x "$tmp/bin/$app"
done
export PATH="$tmp/bin:$PATH"
assert_fail() {
  local label="$1" expected="$2"; shift 2
  local got
  if got="$("$@" 2>&1)"; then
    printf 'FAIL %s unexpectedly succeeded\n' "$label" >&2; exit 1
  fi
  [[ "$got" == *"V3_ARTIFACT_ABORT=$expected"* ]] || {
    printf 'FAIL %s wrong rejection: %s\n' "$label" "$got" >&2; exit 1
  }
  [[ "$got" != *'MOCK_MUST_NOT_CONNECT'* ]] || { echo 'FAIL attempted mock DB connection' >&2; exit 1; }
  printf 'PASS %s\n' "$label"
}

[[ "$(bash "$script")" == *'V3_ARTIFACT_STATUS=NOT_EXECUTED'* ]] || exit 1
printf 'PASS default_plan_has_no_side_effects\n'
assert_fail wrong_target target_must_be_v3 env V3_BACKUP_MODE=execute bash "$script"
assert_fail wrong_service v3_service_identity_not_approved env V3_BACKUP_MODE=execute V3_BACKUP_TARGET=v3 bash "$script"
service='03652c28-20fa-4807-aa8c-8e71b6f21d26'
assert_fail missing_approval backup_not_approved env V3_BACKUP_MODE=execute V3_BACKUP_TARGET=v3 V3_EXPECTED_SERVICE_ID="$service" GITHUB_ACTIONS=true GITHUB_RUN_ID=12345678 bash "$script"
assert_fail missing_cost_confirmation wake_and_network_cost_not_approved env V3_BACKUP_MODE=execute V3_BACKUP_TARGET=v3 V3_EXPECTED_SERVICE_ID="$service" GITHUB_ACTIONS=true GITHUB_RUN_ID=12345678 V3_BACKUP_EXECUTE_APPROVED=YES_SINGLE_V3_ENCRYPTED_SNAPSHOT bash "$script"
assert_fail missing_restore_confirmation recovery_key_test_not_confirmed env V3_BACKUP_MODE=execute V3_BACKUP_TARGET=v3 V3_EXPECTED_SERVICE_ID="$service" GITHUB_ACTIONS=true GITHUB_RUN_ID=12345678 V3_BACKUP_EXECUTE_APPROVED=YES_SINGLE_V3_ENCRYPTED_SNAPSHOT V3_CONFIRM_WAKE_AND_NETWORK_COST=YES bash "$script"

recipient='age1a0b123456789qwertyuio'
hash="$(printf '%s' "$recipient" | sha256sum | awk '{print $1}')"
export V3_BACKUP_TARGET=v3 V3_EXPECTED_SERVICE_ID="$service" GITHUB_ACTIONS=true GITHUB_RUN_ID=12345678
export V3_SOURCE_DATABASE_URL='postgresql://mock:mock@safe.example:46406/boatdb?sslmode=require'
export V3_EXPECTED_HOST=safe.example V3_EXPECTED_PORT=46406 V3_EXPECTED_DATABASE=boatdb
export V3_AGE_RECIPIENT="$recipient" V3_AGE_RECIPIENT_SHA256="$hash" RUNNER_TEMP="$tmp"
assert_fail wrong_port source_port_mismatch env V3_BACKUP_MODE=validate V3_EXPECTED_PORT=46407 bash "$script"
assert_fail bad_fingerprint recipient_pin_mismatch env V3_BACKUP_MODE=validate V3_AGE_RECIPIENT_SHA256="$(printf '%064d' 0)" bash "$script"
assert_fail insecure_ssl url_malformed_or_insecure env V3_BACKUP_MODE=validate V3_SOURCE_DATABASE_URL='postgresql://mock:mock@safe.example:46406/boatdb?sslmode=disable' bash "$script"
assert_fail wrong_host source_host_mismatch env V3_BACKUP_MODE=validate V3_EXPECTED_HOST=wrong.example bash "$script"
res="$(V3_BACKUP_MODE=validate bash "$script")"
[[ "$res" == *'V3_ARTIFACT_STATIC_PREFLIGHT=PASS'* && "$res" == *'V3_ARTIFACT_DB_CONNECTION=NOT_ATTEMPTED'* ]] || { echo "FAIL validate: $res" >&2; exit 1; }
printf 'PASS validate_has_no_db_connection\n'