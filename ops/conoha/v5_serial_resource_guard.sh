#!/usr/bin/env bash
# V5 / ConoHa 2GB: local resource gate and single-job lock.
# Default --plan is read-only. --execute is NOT deployed or scheduled by this file.
set -euo pipefail
set +x
umask 077

usage() {
  printf 'USAGE: %s [--plan | --execute -- command [args...]]\n' "$0" >&2
  exit 64
}
mode=plan
if (($# > 0)); then
  case "$1" in
    --plan) (($# == 1)) || usage ;;
    --execute)
      mode=execute
      shift
      (($# >= 2)) && [[ "$1" == -- ]] || usage
      shift
      (($# > 0)) || usage
      ;;
    *) usage ;;
  esac
fi

# Separate deployment/operations approval required before enabling execute mode.
if [[ "$mode" == execute && "${V5_CONOHA_EXECUTION_ENABLED:-NO}" != YES ]]; then
  printf 'V5_GUARD=EXECUTION_DISABLED\n' >&2
  exit 78
fi

is_positive_int() { [[ "$1" =~ ^[0-9]{1,9}$ ]] && ((10#$1 > 0)); }
min_memory_mib="${V5_MIN_AVAILABLE_MIB:-768}"
min_root_free_gib="${V5_MIN_ROOT_FREE_GIB:-25}"
max_runtime_sec="${V5_MAX_RUNTIME_SECONDS:-1800}"
for value in "$min_memory_mib" "$min_root_free_gib" "$max_runtime_sec"; do
  is_positive_int "$value" || { printf 'V5_GUARD=INVALID_THRESHOLD\n' >&2; exit 64; }
done
((min_memory_mib >= 512 && min_root_free_gib >= 10 && max_runtime_sec <= 7200)) || {
  printf 'V5_GUARD=UNSAFE_THRESHOLD\n' >&2; exit 64;
}

for tool in awk df; do
  command -v "$tool" >/dev/null 2>&1 || { printf 'V5_GUARD=MISSING_TOOL\n' >&2; exit 69; }
done
[[ -r /proc/meminfo ]] || { printf 'V5_GUARD=MEMINFO_UNAVAILABLE\n' >&2; exit 69; }
mem_available_kib="$(awk '$1=="MemAvailable:" {print $2; exit}' /proc/meminfo)"
root_free_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
[[ "$mem_available_kib" =~ ^[0-9]+$ && "$root_free_kib" =~ ^[0-9]+$ ]] || {
  printf 'V5_GUARD=RESOURCE_READ_ERROR\n' >&2; exit 69;
}
mem_available_mib=$((mem_available_kib / 1024))
root_free_gib=$((root_free_kib / 1024 / 1024))
printf 'V5_GUARD_MODE=%s\n' "$mode"
printf 'AVAILABLE_MEMORY_MIB=%s\nROOT_FREE_GIB=%s\n' "$mem_available_mib" "$root_free_gib"
printf 'REQUIRED_MEMORY_MIB=%s\nREQUIRED_ROOT_FREE_GIB=%s\n' "$min_memory_mib" "$min_root_free_gib"
if ((mem_available_mib < min_memory_mib)); then
  printf 'V5_GUARD=HOLD_LOW_MEMORY\n'
  exit 76
fi
if ((root_free_gib < min_root_free_gib)); then
  printf 'V5_GUARD=HOLD_LOW_DISK\n'
  exit 76
fi
if [[ "$mode" == plan ]]; then
  printf 'V5_GUARD=PLAN_PASS_NO_JOB_STARTED\n'
  printf 'V5_PRODUCTION_READINESS=NOT_ASSESSED\n'
  exit 0
fi

for tool in flock timeout dirname; do
  command -v "$tool" >/dev/null 2>&1 || { printf 'V5_GUARD=MISSING_EXEC_TOOL\n' >&2; exit 69; }
done
lock_file="${V5_SERIAL_LOCK_FILE:-/run/boat-ai-v5/jobs.lock}"
[[ "$lock_file" == /* && "$lock_file" != *$'\n'* ]] || {
  printf 'V5_GUARD=INVALID_LOCK_PATH\n' >&2; exit 73;
}
lock_dir="$(dirname -- "$lock_file")"
[[ -d "$lock_dir" && -w "$lock_dir" && ! -L "$lock_file" ]] || {
  printf 'V5_GUARD=LOCK_DIRECTORY_UNAVAILABLE\n' >&2; exit 73;
}
# The directory must be created and owned by the dedicated systemd user before deployment.
exec 9>"$lock_file"
if ! flock -n 9; then
  printf 'V5_GUARD=BUSY_SKIP_NO_SECOND_JOB\n'
  exit 75
fi
# Check again AFTER taking the lock, so queued/overlapping jobs cannot
# bypass the gate based on a stale reading.
mem_available_kib="$(awk '$1=="MemAvailable:" {print $2; exit}' /proc/meminfo)"
root_free_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
[[ "$mem_available_kib" =~ ^[0-9]+$ && "$root_free_kib" =~ ^[0-9]+$ ]] || exit 69
if ((mem_available_kib / 1024 < min_memory_mib || root_free_kib / 1024 / 1024 < min_root_free_gib)); then
  printf 'V5_GUARD=HOLD_RESOURCE_CHANGED\n'
  exit 76
fi
printf 'V5_GUARD=RUNNING_WITH_LOCK\n'
# Do not echo command or environment: they could contain private connection data.
set +e
timeout --signal=TERM --kill-after=10s "${max_runtime_sec}s" "$@"
exit_code=$?
set -e
printf 'V5_GUARD=JOB_DONE status:%s\n' "$exit_code"
exit "$exit_code"
