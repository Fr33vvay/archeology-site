#!/usr/bin/env bash
# Cron еженедельного отчёта: понедельник 12:00 Europe/Moscow.
# На ВМ сайт в Docker — команда через docker compose.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRON_LINE="0 12 * * 1 cd ${ROOT} && /usr/bin/docker compose run --rm web python manage.py send_weekly_report >>${HOME}/weekly-report.log 2>&1"

# TZ на ВМ обычно UTC; Europe/Moscow = UTC+3 → 09:00 UTC = 12:00 MSK.
# Если системный TZ уже Europe/Moscow, используйте 0 12; иначе 0 9 UTC.
# Определяем по /etc/timezone или timedatectl.
TZ_NAME="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
if [[ "${TZ_NAME}" == "Europe/Moscow" ]]; then
  CRON_LINE="0 12 * * 1 cd ${ROOT} && /usr/bin/docker compose run --rm web python manage.py send_weekly_report >>${HOME}/weekly-report.log 2>&1"
else
  # 12:00 MSK = 09:00 UTC
  CRON_LINE="0 9 * * 1 cd ${ROOT} && /usr/bin/docker compose run --rm web python manage.py send_weekly_report >>${HOME}/weekly-report.log 2>&1"
fi

(crontab -l 2>/dev/null | grep -v 'send_weekly_report' || true; echo "${CRON_LINE}") | crontab -
echo "Cron еженедельного отчёта установлен:"
echo "  ${CRON_LINE}"
crontab -l | grep send_weekly_report || true
