#!/usr/bin/env bash
# Shared settings for backup.sh and setup-backup-cron.sh. ROOT is set by caller.
# Parse only known .env keys as data; never execute .env or expose its secrets.
BACKUP_SETTINGS="$(python3 - "$ROOT/.env" <<'PY'
import os
from pathlib import Path
import shlex
import sys

keys = {
    "BACKUP_ENABLED", "BACKUP_SCHEDULE", "BACKUP_DIR", "BACKUP_KEEP",
    "BACKUP_RCLONE_REMOTE", "BACKUP_RCLONE_PATH", "BACKUP_ALERT_TO",
    "BACKUP_LOG", "POSTGRES_USER", "POSTGRES_DB",
}
path = Path(sys.argv[1])
settings = {}
if path.is_file():
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        key = key.strip()
        if not sep or key not in keys or key in os.environ:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            sys.exit(f"Invalid .env quoting for {key}")
        if len(parts) > 1:
            sys.exit(f"Quote spaces in .env setting {key}")
        settings[key] = parts[0] if parts else ""
for key, value in settings.items():
    print(f"{key}={shlex.quote(value)}")
PY
)" || return 1
# Assignments are generated exclusively with shlex.quote above.
eval "$BACKUP_SETTINGS"
unset BACKUP_SETTINGS

BACKUP_ENABLED="${BACKUP_ENABLED-1}"
BACKUP_SCHEDULE="${BACKUP_SCHEDULE-monthly}"
BACKUP_LOG="${BACKUP_LOG:-$HOME/backup.log}"

case "$BACKUP_ENABLED" in
  0|1) ;;
  *) echo 'BACKUP_ENABLED must be 0 or 1' >&2; return 1 ;;
esac
case "$BACKUP_SCHEDULE" in
  monthly) BACKUP_CRON='15 4 1 * *' ;;
  weekly) BACKUP_CRON='15 4 * * 1' ;;
  daily) BACKUP_CRON='15 4 * * *' ;;
  *) echo 'BACKUP_SCHEDULE must be monthly, weekly or daily' >&2; return 1 ;;
esac
