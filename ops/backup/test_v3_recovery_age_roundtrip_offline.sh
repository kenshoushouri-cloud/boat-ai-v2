#!/usr/bin/env bash
# ONLY run on the owner's trusted LOCAL machine with age installed.
# This is not a production DB or backup restore test. Never transfer keys here.
# No network, Railway, Drive, GitHub API, or production data is accessed.
set +x
set -euo pipefail
umask 077

fail() { printf 'RECOVERY_TEST_ABORT=%s\n' "$1" >&2; exit 1; }
for tool in age sha256sum cmp mktemp python3; do
  command -v "$tool" >/dev/null 2>&1 || fail 'required_local_tool_missing'
done

# Pass ONLY a private key PATH, not its content, via this variable.
[[ -n "${RECOVERY_PRIVATE_KEY_FILE:-}" ]] || fail 'local_private_key_path_required'
private_key_path="$RECOVERY_PRIVATE_KEY_FILE"
unset RECOVERY_PRIVATE_KEY_FILE

# Metadata only: never read or print private key material.  This rejects
# noncanonical paths, symlinked parent directories or key, insecure modes,
# swapped owners, hardlinked keys, and paths in writable parent directories.
# Fail closed on filesystems where these identity properties cannot be checked.
python3 - "$private_key_path" <<'PY' || fail 'untrusted_local_private_key_path'
import os
import pathlib
import stat
import sys

value = sys.argv[1]
if (not value.startswith('/') or value == '/' or '\x00' in value or
        '\n' in value or '\r' in value or '//' in value or
        os.path.normpath(value) != value):
    raise SystemExit(1)
uid = os.geteuid()
current = pathlib.Path('/')
parts = pathlib.PurePosixPath(value).parts[1:]
try:
    for index, component in enumerate(parts):
        current = current / component
        st = os.lstat(current)
        if stat.S_ISLNK(st.st_mode):
            raise ValueError('symbolic_link')
        if index < len(parts) - 1:
            if (not stat.S_ISDIR(st.st_mode) or st.st_uid not in (0, uid)
                    or st.st_mode & 0o022):
                raise ValueError('untrusted_parent_directory')
        else:
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid
                    or st.st_mode & 0o077 or st.st_nlink != 1
                    or st.st_size == 0):
                raise ValueError('untrusted_private_key_metadata')
except (OSError, ValueError):
    raise SystemExit(1)
PY

base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pub="$base/keys/v3_recovery_recipient_20261013.pub"
[[ -f "$pub" && ! -L "$pub" ]] || fail 'v3_recipient_public_key_missing_or_linked'

recipient="$(tr -d '\r\n' < "$pub")"
[[ "$recipient" =~ ^ssh-ed25519[[:space:]]+[A-Za-z0-9+/]+={0,2}[[:space:]]+boat-ai-recovery$ ]] \
  || fail 'unexpected_public_recipient_format'
expected_pin='da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234'
got_pin="$(printf '%s' "$recipient" | sha256sum | awk '{print $1}')"
[[ "$got_pin" == "$expected_pin" ]] || fail 'public_recipient_mismatch'
unset recipient got_pin

tmp="$(mktemp -d)" || fail 'temporary_directory_unavailable'
trap 'rm -rf -- "$tmp"' EXIT
printf 'Boat AI local recovery key format compatibility test.\n' > "$tmp/plain"
age -R "$pub" -o "$tmp/test.age" "$tmp/plain" \
  > "$tmp/encrypt.log" 2>&1 || fail 'age_encrypt_failed'
[[ -s "$tmp/test.age" ]] || fail 'encrypted_file_empty'
# age may ask for the key passphrase on the owner's trusted local console.
age -d -i "$private_key_path" -o "$tmp/roundtrip" "$tmp/test.age" \
  > "$tmp/decrypt.log" 2>&1 || fail 'private_key_decrypt_failed'
cmp -s "$tmp/plain" "$tmp/roundtrip" || fail 'roundtrip_content_mismatch'
printf 'RECOVERY_ROUNDTRIP_OK=YES\n'
printf 'RECOVERY_DATABASE_BACKUP_VERIFIED=NO\n'
printf 'RECOVERY_KEYS_LEAVE_TRUSTED_DEVICE=NO\n'
