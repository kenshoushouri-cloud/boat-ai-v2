#!/usr/bin/env bash
# Local-only mock-job checks. Do not invoke production scripts, DB, or network.
set -euo pipefail
set +x
here="$(cd "$(dirname "$0")" && pwd)"
guard="$here/v5_serial_resource_guard.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
ok=0
expect() {
  local desc="$1" expected="$2" contains="$3"
  shift 3
  local code=0
  "$@" >"$work/output" 2>&1 || code=$?
  if [[ "$code" == "$expected" ]] && grep -Fq -- "$contains" "$work/output"; then
    ok=$((ok+1))
    printf 'PASS %s\n' "$desc"
  else
    printf 'FAIL %s exit:%s expected:%s\n' "$desc" "$code" "$expected" >&2
    cat "$work/output" >&2
    exit 1
  fi
}

bash -n "$guard"
expect 'baseline plan is read-only' 0 'V5_GUARD=PLAN_PASS_NO_JOB_STARTED' bash "$guard" --plan
expect 'execution prohibited by default' 78 'V5_GUARD=EXECUTION_DISABLED' bash "$guard" --execute -- bash -c 'printf SHOULD_NOT_RUN'
expect 'high memory floor holds' 76 'V5_GUARD=HOLD_LOW_MEMORY' env V5_MIN_AVAILABLE_MIB=999999999 bash "$guard" --plan
expect 'high disk floor holds' 76 'V5_GUARD=HOLD_LOW_DISK' env V5_MIN_ROOT_FREE_GIB=999999999 bash "$guard" --plan
expect 'bad timeout threshold blocked' 64 'V5_GUARD=INVALID_THRESHOLD' env V5_MAX_RUNTIME_SECONDS=0 bash "$guard" --plan
expect 'authorized harmless dummy completes' 0 'DUMMY_ONLY_OK' env V5_CONOHA_EXECUTION_ENABLED=YES V5_SERIAL_LOCK_FILE="$work/jobs.lock" V5_MIN_ROOT_FREE_GIB=10 bash "$guard" --execute -- bash -c 'printf DUMMY_ONLY_OK'
# Hold the lock from another process; the second job must be refused.
flock -x "$work/jobs.lock" -c 'sleep 2' & locker_pid=$!
sleep 0.2
expect 'overlapping dummy job refused' 75 'V5_GUARD=BUSY_SKIP_NO_SECOND_JOB' env V5_CONOHA_EXECUTION_ENABLED=YES V5_SERIAL_LOCK_FILE="$work/jobs.lock" V5_MIN_ROOT_FREE_GIB=10 bash "$guard" --execute -- bash -c 'printf SHOULD_NOT_RUN'
wait "$locker_pid"
expect 'slow dummy stopped by timeout' 124 'V5_GUARD=JOB_DONE status:124' env V5_CONOHA_EXECUTION_ENABLED=YES V5_SERIAL_LOCK_FILE="$work/jobs.lock" V5_MIN_ROOT_FREE_GIB=10 V5_MAX_RUNTIME_SECONDS=1 bash "$guard" --execute -- sleep 3
expect 'relative lock path blocked' 73 'V5_GUARD=INVALID_LOCK_PATH' env V5_CONOHA_EXECUTION_ENABLED=YES V5_SERIAL_LOCK_FILE='bad.lock' V5_MIN_ROOT_FREE_GIB=10 bash "$guard" --execute -- true
printf 'OFFLINE_TESTS=%s/9 PASS\n' "$ok"
