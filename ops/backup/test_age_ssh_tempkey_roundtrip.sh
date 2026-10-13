#!/usr/bin/env bash
# Isolated, real age compatibility test using a THROWAWAY Ed25519 SSH key.
# Never accepts user-supplied private keys, DB URLs or network configuration.
# Not a production restore test. This file creates no persistent key.
set +x
set -euo pipefail
umask 077

fail() { printf 'AGE_COMPAT_ABORT=%s\n' "$1" >&2; exit 1; }
for bin in age ssh-keygen python3 cmp mktemp; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    printf 'AGE_COMPAT=NOT_TESTED_MISSING_TOOL\nMISSING_TOOL=%s\n' "$bin"
    exit 69
  fi
done

tmp="$(mktemp -d)" || fail 'tempdir_unavailable'
trap 'rm -rf -- "$tmp"' EXIT

# No passphrase is used for this disposable key; the owner's real key is NEVER loaded.
ssh-keygen -q -t ed25519 -N '' -C age-offline-disposable \
  -f "$tmp/disposable_key" </dev/null >"$tmp/keygen.log" 2>&1 \
  || fail 'temp_ssh_key_generation_failed'
[[ -s "$tmp/disposable_key" && -s "$tmp/disposable_key.pub" ]] \
  || fail 'temporary_ssh_key_missing'

python3 - "$tmp/plain" <<'PY'
from pathlib import Path
import os
import sys
Path(sys.argv[1]).write_bytes(b"Boat AI isolated age test / not a database backup\n" + os.urandom(4096))
PY

# Only the disposable public key may be used to encrypt.
age -R "$tmp/disposable_key.pub" -o "$tmp/encrypted.age" "$tmp/plain" \
  >"$tmp/encrypt.log" 2>&1 || fail 'ssh_ed25519_age_encryption_failed'
[[ -s "$tmp/encrypted.age" ]] || fail 'encrypted_output_empty'

age -d -i "$tmp/disposable_key" -o "$tmp/restored" "$tmp/encrypted.age" \
  >"$tmp/decrypt.log" 2>&1 || fail 'ssh_ed25519_age_decryption_failed'
cmp -s "$tmp/plain" "$tmp/restored" || fail 'plaintext_mismatch'

# Flip a byte in the ciphertext payload, not in the file header. Authenticated
# decryption MUST fail, rather than silently accepting modified bytes.
python3 - "$tmp/encrypted.age" "$tmp/tampered.age" <<'PY'
from pathlib import Path
import sys
content = bytearray(Path(sys.argv[1]).read_bytes())
if len(content) < 100:
    raise SystemExit('encrypted payload unexpectedly short')
content[-1] ^= 0x01
Path(sys.argv[2]).write_bytes(content)
PY
if age -d -i "$tmp/disposable_key" -o "$tmp/tampered_restored" "$tmp/tampered.age" \
    >"$tmp/tamper.log" 2>&1; then
  fail 'tampered_ciphertext_accepted'
fi

printf 'AGE_COMPAT_TEST=PASS_TEMPORARY_SSH_ED25519\n'
printf 'AGE_COMPAT_DECRYPT=PASS_BIT_IDENTICAL\n'
printf 'AGE_COMPAT_TAMPERING=REJECTED\n'
printf 'AGE_OWNER_PRIVATE_KEY_USED=NO\n'
printf 'AGE_REAL_DB_BACKUP_VERIFIED=NO\n'
printf 'AGE_REAL_OWNER_RECOVERY_VERIFIED=NO\n'
