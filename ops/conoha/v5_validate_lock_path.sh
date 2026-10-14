#!/usr/bin/env bash
# ConoHa V5 lock path guard. Local check only: never creates lock files.
# Intended to be called just before the main runner opens its lock.
set +x
set -euo pipefail
umask 077
fail() { printf 'V5_LOCK_CHECK=%s\n' "$1" >&2; exit 73; }
(($# == 1)) || fail 'INVALID_ARGUMENTS'
lock_file="$1"
[[ "$lock_file" == /* && "$lock_file" != *$'\n'* ]] || fail 'INVALID_LOCK_PATH'
for tool in stat id dirname; do
  command -v "$tool" >/dev/null 2>&1 || fail 'MISSING_TOOL'
done
lock_dir="$(dirname -- "$lock_file")"
[[ -d "$lock_dir" && -w "$lock_dir" && ! -L "$lock_dir" && ! -L "$lock_file" ]] \
  || fail 'LOCK_DIRECTORY_UNAVAILABLE'
uid="$(id -u)"
dir_uid="$(stat -c '%u' -- "$lock_dir")" || fail 'LOCK_DIR_STAT_ERROR'
dir_mode="$(stat -c '%a' -- "$lock_dir")" || fail 'LOCK_DIR_STAT_ERROR'
[[ "$uid" =~ ^[0-9]+$ && "$dir_uid" =~ ^[0-9]+$ && "$dir_mode" =~ ^[0-7]{3,4}$ ]] \
  || fail 'LOCK_DIR_STAT_INVALID'
(( 10#$dir_uid == 10#$uid && (8#$dir_mode & 8#022) == 0 )) \
  || fail 'LOCK_DIRECTORY_INSECURE'
if [[ -e "$lock_file" ]]; then
  [[ -f "$lock_file" && ! -L "$lock_file" ]] || fail 'LOCK_FILE_NOT_REGULAR'
  file_uid="$(stat -c '%u' -- "$lock_file")" || fail 'LOCK_FILE_STAT_ERROR'
  file_mode="$(stat -c '%a' -- "$lock_file")" || fail 'LOCK_FILE_STAT_ERROR'
  link_count="$(stat -c '%h' -- "$lock_file")" || fail 'LOCK_FILE_STAT_ERROR'
  [[ "$file_uid" =~ ^[0-9]+$ && "$file_mode" =~ ^[0-7]{3,4}$ && "$link_count" =~ ^[0-9]+$ ]] \
    || fail 'LOCK_FILE_STAT_INVALID'
  (( 10#$file_uid == 10#$uid && (8#$file_mode & 8#022) == 0 && 10#$link_count == 1 )) \
    || fail 'LOCK_FILE_INSECURE'
fi
printf 'V5_LOCK_CHECK=PASS_NO_FILE_CREATED\n'
