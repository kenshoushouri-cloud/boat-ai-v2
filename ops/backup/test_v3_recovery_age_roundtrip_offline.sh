#!/usr/bin/env bash
# ONLY run on a user's trusted machine with age installed and the separately
# passphrase-protected recovery SSH Ed25519 private key available.
# No Railway, Google, GitHub API, network calls, or production data.
set -euo pipefail
umask 077

fail() { printf 'RECOVERY_TEST_ABORT=%s\n' "$1" >&2; exit 1; }
command -v age >/dev/null || fail 'age_not_installed'
command -v sha256sum >/dev/null || fail 'sha256sum_missing'
command -v cmp >/dev/null || fail 'cmp_missing'

: "${RECOVERY_PRIVATE_KEY_FILE:?Set only the private key FILE PATH on the trusted local host; never paste key data}"
[[ -f "$RECOVERY_PRIVATE_KEY_FILE" ]] || fail 'recovery_private_key_file_missing'

base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pub="$base/keys/v3_recovery_recipient_20261013.pub"
[[ -f "$pub" ]] || fail 'v3_recipient_public_key_missing'

recipient="$(tr -d '\r\n' < "$pub")"
[[ "$recipient" =~ ^ssh-ed25519[[:space:]]+[A-Za-z0-9+/]+={0,2}[[:space:]]+boat-ai-recovery$ ]] \
  || fail 'unexpected_public_recipient_format'
expected_pin='da094443ccc50f1e0d253d02c670c52bedeb64ac2c479888659a62e05d978234'
got_pin="$(printf '%s' "$recipient" | sha256sum | awk '{print $1}')"
[[ "$got_pin" == "$expected_pin" ]] || fail 'public_recipient_mismatch'
unset recipient got_pin

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
printf 'Boat AI restore key check: public key belongs to locally held private key.\n' > "$tmp/plain"
age -R "$pub" -o "$tmp/test.age" "$tmp/plain" || fail 'age_encrypt_failed'
[[ -s "$tmp/test.age" ]] || fail 'encrypted_file_empty'
# Will ask for the user's private key passphrase locally if necessary.
age -d -i "$RECOVERY_PRIVATE_KEY_FILE" -o "$tmp/roundtrip" "$tmp/test.age" \
  || fail 'private_key_decrypt_failed'
cmp -s "$tmp/plain" "$tmp/roundtrip" || fail 'roundtrip_content_mismatch'
printf 'RECOVERY_ROUNDTRIP_OK=YES\n'
printf 'RECOVERY_DATABASE_BACKUP_VERIFIED=NO\n'
printf 'RECOVERY_KEYS_LEAVE_TRUSTED_DEVICE=NO\n'
