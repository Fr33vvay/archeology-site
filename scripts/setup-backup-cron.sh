#!/usr/bin/env bash
# Вешает cron бэкапа для пользователя freeway (каждые 2 дня в 04:00).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRON_LINE="0 4 */2 * * cd ${ROOT} && /bin/bash ${ROOT}/scripts/backup.sh >>${HOME}/backup.log 2>&1"

chmod +x "${ROOT}/scripts/backup.sh"
(crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' || true; echo "${CRON_LINE}") | crontab -
echo "Cron бэкапа установлен:"
echo "  ${CRON_LINE}"
crontab -l | grep backup || true
