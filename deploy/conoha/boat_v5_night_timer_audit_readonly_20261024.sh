#!/usr/bin/env bash
# V5 ConoHa: installed systemd timers and collector journal, READ ONLY.
# Never starts/stops/reloads/enables units; no SQL/network/mutations.
set -u
export LC_ALL=C
export SYSTEMD_PAGER=cat

printf 'V5_TIMER_AUDIT_READ_ONLY %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')"
printf 'timezone='
timedatectl show -p Timezone --value 2>/dev/null || date '+%Z'

for unit in boat-v5-forward-window.timer boat-v5-midnight-catchup.timer boat-v5-daily@night.timer; do
  printf '\n[TIMER %s]\n' "$unit"
  systemctl show "$unit" --no-pager \
    -p LoadState -p ActiveState -p SubState -p UnitFileState \
    -p FragmentPath -p DropInPaths \
    -p NextElapseUSecRealtime -p LastTriggerUSec 2>&1 || true
  # Includes drop-in overrides and resets in unit precedence order.
  systemctl cat "$unit" --no-pager 2>/dev/null \
    | grep -E '^(# /|OnCalendar=|OnUnitActiveSec=|OnBootSec=|Persistent=|Unit=|AccuracySec=|RandomizedDelaySec=)' || true
done

for unit in boat-v5-forward-window.service boat-v5-midnight-catchup.service boat-v5-daily@night.service; do
  printf '\n[SERVICE %s]\n' "$unit"
  systemctl show "$unit" --no-pager \
    -p LoadState -p ActiveState -p SubState -p Result \
    -p ExecMainCode -p ExecMainStatus -p ActiveEnterTimestamp \
    -p InactiveEnterTimestamp 2>&1 || true
  printf '[recent selected journal lines, max 12]\n'
  journalctl -u "$unit" --since '48 hours ago' --no-pager -o short-iso 2>/dev/null \
    | grep -Ei 'start|stop|finish|fail|pending|skip|lock|complet|success|exit|timeout|result|race|error' \
    | sed -E '/(TOKEN|PASSWORD|SECRET|API.KEY|DATABASE_URL|postgres(ql)?:\/\/)/I s/.*/[REDACTED]/' \
    | tail -n 12 || true
done

printf '\nEND: read-only audit. NO SWITCH, NO TIMER CHANGE, BUY OFF.\n'
