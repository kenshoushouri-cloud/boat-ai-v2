#!/usr/bin/env bash
# ConoHa 2GB candidate host diagnostics; no configuration, connection, or writes.
# Use only AFTER the user gains authorized VPS access. Never stores credentials.
set -euo pipefail
set +x

abort() { printf 'PREFLIGHT_ABORT=%s\n' "$1" >&2; exit 2; }
for bin in awk df uname grep; do
  command -v "$bin" >/dev/null 2>&1 || abort "missing_tool_${bin}"
done
[[ -r /proc/meminfo ]] || abort 'meminfo_not_readable'
[[ -r /etc/os-release ]] || abort 'os_release_not_readable'

# Only resource numbers and OS metadata are reported: no hostname, IP, user,
# process listing, environment variables, tokens, DB URL or SSH material.
mem_total_kib="$(awk '$1=="MemTotal:" {print $2; exit}' /proc/meminfo)"
mem_avail_kib="$(awk '$1=="MemAvailable:" {print $2; exit}' /proc/meminfo)"
swap_total_kib="$(awk '$1=="SwapTotal:" {print $2; exit}' /proc/meminfo)"
[[ "$mem_total_kib" =~ ^[0-9]+$ && "$mem_total_kib" -gt 0 ]] || abort 'memory_total_invalid'
[[ "$mem_avail_kib" =~ ^[0-9]+$ ]] || abort 'memory_available_invalid'
[[ "$swap_total_kib" =~ ^[0-9]+$ ]] || abort 'swap_total_invalid'

root_free_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
[[ "$root_free_kib" =~ ^[0-9]+$ ]] || abort 'root_disk_free_invalid'
os_id="$(awk -F= '$1=="ID" {gsub(/"/,"",$2); print $2; exit}' /etc/os-release)"
os_version="$(awk -F= '$1=="VERSION_ID" {gsub(/"/,"",$2); print $2; exit}' /etc/os-release)"
[[ "$os_id" =~ ^[A-Za-z0-9._-]{1,40}$ ]] || abort 'os_id_invalid'
[[ "$os_version" =~ ^[A-Za-z0-9._-]{1,40}$ ]] || abort 'os_version_invalid'
architecture="$(uname -m)"
[[ "$architecture" =~ ^[A-Za-z0-9._-]{1,40}$ ]] || abort 'architecture_invalid'

cpu_count=0
if command -v nproc >/dev/null 2>&1; then
  cpu_count="$(nproc)"
elif [[ -r /proc/cpuinfo ]]; then
  cpu_count="$(grep -c '^processor[[:space:]]*:' /proc/cpuinfo || true)"
fi
[[ "$cpu_count" =~ ^[0-9]+$ ]] || abort 'cpu_count_invalid'

mem_total_mib=$((mem_total_kib / 1024))
mem_available_mib=$((mem_avail_kib / 1024))
swap_total_mib=$((swap_total_kib / 1024))
root_free_gib=$((root_free_kib / 1024 / 1024))

printf 'CONOHA_PREFLIGHT_MODE=READ_ONLY\n'
printf 'OS_ID=%s\nOS_VERSION=%s\nARCHITECTURE=%s\n' "$os_id" "$os_version" "$architecture"
printf 'CPU_COUNT=%s\nMEMORY_TOTAL_MIB=%s\nMEMORY_AVAILABLE_MIB=%s\n' "$cpu_count" "$mem_total_mib" "$mem_available_mib"
printf 'SWAP_TOTAL_MIB=%s\nROOT_FREE_GIB=%s\n' "$swap_total_mib" "$root_free_gib"

warnings=0
if [[ "$os_id" != ubuntu || "$os_version" != 24.04 ]]; then
  printf 'CHECK_OS=REVIEW_NOT_UBUNTU_24_04\n'; warnings=$((warnings+1))
else
  printf 'CHECK_OS=EXPECTED_UBUNTU_24_04\n'
fi
if (( mem_total_mib < 1536 )); then
  printf 'CHECK_MEMORY=LOW_FOR_2GB_PLAN\n'; warnings=$((warnings+1))
elif (( mem_available_mib < 384 )); then
  printf 'CHECK_MEMORY=LOW_AVAILABLE_MEMORY\n'; warnings=$((warnings+1))
else
  printf 'CHECK_MEMORY=BASELINE_OK_NOT_LOAD_TESTED\n'
fi
if (( root_free_gib < 35 )); then
  printf 'CHECK_DISK=REVIEW_BEFORE_RESTORE\n'; warnings=$((warnings+1))
else
  printf 'CHECK_DISK=BASELINE_OK_ROOT_ONLY\n'
fi
if (( cpu_count < 2 )); then
  printf 'CHECK_CPU=REVIEW_BEFORE_MIGRATION\n'; warnings=$((warnings+1))
else
  printf 'CHECK_CPU=BASELINE_OK_NOT_LOAD_TESTED\n'
fi
if (( swap_total_mib == 0 )); then
  printf 'CHECK_SWAP=NOT_CONFIGURED_NO_AUTOMATIC_CHANGE\n'
else
  printf 'CHECK_SWAP=PRESENT_NOT_PERFORMANCE_TESTED\n'
fi
printf 'PREFLIGHT_WARNING_COUNT=%s\n' "$warnings"
printf 'V5_PRODUCTION_READINESS=NOT_ASSESSED\n'
printf 'BACKUP_RESTORE_VERIFIED=NO\n'
printf 'RAILWAY_SHUTDOWN_APPROVED=NO\n'
printf 'BUY=HARD_HOLD\n'
