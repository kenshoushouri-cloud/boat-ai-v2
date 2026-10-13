#!/usr/bin/env bash
# Offline, non-sensitive age encryption/decryption/tamper test.
set -euo pipefail
umask 077
for bin in age age-keygen sha256sum cmp python3 mktemp head; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "AGE_ROUNDTRIP=SKIPPED missing=$bin"; exit 77
  fi
done
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
age-keygen -o "$work/identity.txt" > /dev/null 2>&1
recipient="$(age-keygen -y "$work/identity.txt")"
[[ "$recipient" == age1* ]] || { echo 'AGE_ROUNDTRIP=FAIL invalid_recipient'; exit 1; }
{
  printf 'boat-ai-offline-test: NOT A REAL BACKUP\n'
  head -c 134000 /dev/urandom
} > "$work/plain.bin"
plain_sha="$(sha256sum "$work/plain.bin" | awk '{print $1}')"
age -r "$recipient" -o "$work/payload.age" "$work/plain.bin"
age -d -i "$work/identity.txt" -o "$work/recovered.bin" "$work/payload.age"
cmp -s "$work/plain.bin" "$work/recovered.bin" || { echo 'AGE_ROUNDTRIP=FAIL mismatch'; exit 1; }
recovered_sha="$(sha256sum "$work/recovered.bin" | awk '{print $1}')"
[[ "$plain_sha" == "$recovered_sha" ]] || { echo 'AGE_ROUNDTRIP=FAIL hash_mismatch'; exit 1; }
python3 - "$work/payload.age" "$work/tampered.age" <<'PY'
from pathlib import Path
import sys
b = bytearray(Path(sys.argv[1]).read_bytes())
assert len(b) > 0
b[-1] ^= 1
Path(sys.argv[2]).write_bytes(b)
PY
if age -d -i "$work/identity.txt" -o "$work/bad.bin" "$work/tampered.age" 2>/dev/null; then
  echo 'AGE_ROUNDTRIP=FAIL modified_ciphertext_was_accepted'; exit 1
fi
echo 'AGE_ROUNDTRIP=PASS sha256_equal=YES tampered_ciphertext_rejected=YES'
