#!/usr/bin/env bash
# No service, database, network or production changes.
set +x
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
check="$here/v5_validate_lock_path.sh"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
ok=0
expect() {
  local label="$1" exit_expected="$2" marker="$3"; shift 3
  local code=0
  "$@" > "$work/output" 2>&1 || code=$?
  [[ "$code" -eq "$exit_expected" ]] && grep -Fq "$marker" "$work/output" || {
    printf 'FAIL %s code:%s expected:%s\n' "$label" "$code" "$exit_expected" >&2
    cat "$work/output" >&2; exit 1;
  }
  ok=$((ok+1))
  printf 'PASS %s\n' "$label"
}
mkdir -m 700 "$work/secure"
expect 'secure directory no existing file' 0 'PASS_NO_FILE_CREATED' bash "$check" "$work/secure/jobs.lock"
[[ ! -e "$work/secure/jobs.lock" ]] || { echo 'FAIL check created file' >&2; exit 1; }
: > "$work/secure/jobs.lock"
chmod 600 "$work/secure/jobs.lock"
expect 'secure existing file' 0 'PASS_NO_FILE_CREATED' bash "$check" "$work/secure/jobs.lock"
chmod 666 "$work/secure/jobs.lock"
expect 'group writable existing lock rejected' 73 'LOCK_FILE_INSECURE' bash "$check" "$work/secure/jobs.lock"
chmod 600 "$work/secure/jobs.lock"
chmod 777 "$work/secure"
expect 'world writable directory rejected' 73 'LOCK_DIRECTORY_INSECURE' bash "$check" "$work/secure/jobs.lock"
chmod 700 "$work/secure"
ln -s "$work/secure/jobs.lock" "$work/secure/linked.lock"
expect 'symlink rejected' 73 'LOCK_DIRECTORY_UNAVAILABLE' bash "$check" "$work/secure/linked.lock"
mkdir -m 700 "$work/other"
ln -s "$work/secure" "$work/shortcut"
expect 'symlink directory rejected' 73 'LOCK_DIRECTORY_UNAVAILABLE' bash "$check" "$work/shortcut/jobs.lock"
mkdir "$work/secure/directory-as-lock"
expect 'nonregular lock rejected' 73 'LOCK_FILE_NOT_REGULAR' bash "$check" "$work/secure/directory-as-lock"
ln "$work/secure/jobs.lock" "$work/secure/hardlink.lock"
expect 'hardlinked lock rejected' 73 'LOCK_FILE_INSECURE' bash "$check" "$work/secure/jobs.lock"
rm "$work/secure/hardlink.lock"
expect 'relative lock path rejected' 73 'INVALID_LOCK_PATH' bash "$check" 'jobs.lock'
expect 'missing directory rejected' 73 'LOCK_DIRECTORY_UNAVAILABLE' bash "$check" "$work/none/jobs.lock"
expect 'missing argument rejected' 73 'INVALID_ARGUMENTS' bash "$check"
printf 'OFFLINE_TESTS=%s/11 PASS\n' "$ok"
