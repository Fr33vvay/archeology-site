#!/usr/bin/env bash
# Synchronize this project's backup cron with .env for the current user.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/backup-config.sh"

# Quote paths for cron's shell. Percent signs are special to cron even in quotes.
if [[ "$ROOT$BACKUP_LOG" == *'%'* || "$ROOT$BACKUP_LOG" == *$'\n'* ]]; then
  echo 'Cron paths must not contain percent signs or newlines' >&2
  exit 1
fi
printf -v ROOT_Q '%q' "$ROOT"
printf -v SCRIPT_Q '%q' "$ROOT/scripts/backup.sh"
printf -v LOG_Q '%q' "$BACKUP_LOG"

# Read first so a crontab read failure cannot silently erase unrelated jobs.
CURRENT="$(mktemp)"
trap 'rm -f "$CURRENT" "$CURRENT.err"' EXIT
if ! LC_ALL=C crontab -l >"$CURRENT" 2>"$CURRENT.err"; then
  if ! LC_ALL=C grep -qi 'no crontab for' "$CURRENT.err"; then
    cat "$CURRENT.err" >&2
    exit 1
  fi
fi
# Remove legacy and current entries only for this checkout, not other projects.
FILTERED="$(awk -v script="$ROOT/scripts/backup.sh" -v quoted="$SCRIPT_Q" \
  'index($0, script) == 0 && index($0, quoted) == 0' "$CURRENT")"
{
  if [[ -n "$FILTERED" ]]; then
    printf '%s\n' "$FILTERED"
  fi
  if [[ "$BACKUP_ENABLED" == 1 ]]; then
    printf '%s cd %s && /bin/bash %s >>%s 2>&1\n' \
      "$BACKUP_CRON" "$ROOT_Q" "$SCRIPT_Q" "$LOG_Q"
  fi
} | crontab -

if [[ "$BACKUP_ENABLED" == 1 ]]; then
  echo "Cron бэкапа: $BACKUP_CRON ($BACKUP_SCHEDULE; часовой пояс cron на ВМ)."
else
  echo 'Бэкапы выключены (BACKUP_ENABLED=0); cron бэкапа удалён.'
fi
