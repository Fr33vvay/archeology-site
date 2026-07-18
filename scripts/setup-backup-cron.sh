#!/usr/bin/env bash
# Вешает cron бэкапа для пользователя freeway (каждые 2 дня в 04:00).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# 04:15 — после prune Docker в 04:00
CRON_LINE="15 4 */2 * * cd ${ROOT} && /bin/bash ${ROOT}/scripts/backup.sh >>${HOME}/backup.log 2>&1"

chmod +x "${ROOT}/scripts/backup.sh" 2>/dev/null || true
(crontab -l 2>/dev/null | grep -v 'scripts/backup.sh' || true; echo "${CRON_LINE}") | crontab -
echo "Cron бэкапа установлен:"
echo "  ${CRON_LINE}"
crontab -l | grep backup || true
