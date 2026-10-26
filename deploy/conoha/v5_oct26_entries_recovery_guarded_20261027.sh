#!/usr/bin/env bash
# One date and one table ONLY: 2026-10-26 missing boat_data_stage.entries.
# Requires explicit V5_APPLY_OCT26_REPAIR=YES to insert; otherwise preview only.
# Does not stop collectors or timers, backdate snapshots, delete or overwrite.
set -euo pipefail
umask 077
ref="cd85c71dde624008ca5adacdd5f0b39db7b01ac6"
url="https://raw.githubusercontent.com/kenshoushouri-cloud/boat-ai-v2/${ref}/deploy/conoha/v5_oct26_entries_targeted_recovery_20261027.py"
work="$(mktemp /tmp/v5-oct26-stage-recovery.XXXXXXXX.py)"
trap 'rm -f -- "$work"' EXIT
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 8 --max-time 15 \
  "$url" -o "$work"
if [[ ! -x /opt/boat-ai-v5-venv/bin/python ]]; then
  echo "HOLD_V5_PYTHON_VENV_NOT_FOUND"; exit 2
fi
/opt/boat-ai-v5-venv/bin/python - "$work" <<'PY'
import ast, pathlib, sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print("V5_OCT26_RECOVERY_PYTHON_SYNTAX_OK")
PY
echo "V5_OCT26_RECOVERY_PREVIEW_BEFORE_APPLY"
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
  /opt/boat-ai-v5-venv/bin/python "$work"
if [[ "${V5_APPLY_OCT26_REPAIR:-NO}" != "YES" ]]; then
  echo "V5_OCT26_RECOVERY_PREVIEW_COMPLETE_NO_WRITES"; exit 0
fi
echo "V5_OCT26_RECOVERY_ONE_TABLE_INSERT_ONLY_APPLY"
runuser -u postgres -- env DATABASE_URL=postgresql:///railway \
  V5_OCT26_ENTRIES_REPAIR_APPROVED=YES \
  /opt/boat-ai-v5-venv/bin/python "$work" --apply
echo "V5_OCT26_RECOVERY_END_OLD_SOURCE_UNTOUCHED_NO_BUY"
