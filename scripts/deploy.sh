#!/usr/bin/env bash
# Деплой на прод только после успешного прогона всех тестов.
# Запуск из корня репозитория: ./scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEPLOY_HOST="${DEPLOY_HOST:-freeway@158.160.180.56}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/archeology-site}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Есть незакоммиченные изменения. Сначала закоммитьте, потом деплойте." >&2
  exit 1
fi

echo "==> Тесты"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi
"$PYTHON" manage.py test

echo "==> Push в origin"
git push origin HEAD

echo "==> Сборка и перезапуск на $DEPLOY_HOST"
# default.conf на ВМ — рабочая копия default-ssl.conf; сбрасываем перед pull.
# nginx пересоздаём: после cp bind-mount может держать старый inode файла.
# После sudo-операций возвращаем владельца .env SSH-пользователю (cron/compose).
ssh "$DEPLOY_HOST" "cd $DEPLOY_DIR && sudo git checkout -- nginx/default.conf && sudo git pull && sudo docker compose build web && sudo docker compose run --rm web python manage.py migrate --noinput && sudo docker compose run --rm web python manage.py ensure_site && sudo docker compose up -d web && sudo cp -f nginx/default-ssl.conf nginx/default.conf && sudo docker compose up -d --force-recreate nginx && sudo docker compose exec -T nginx nginx -t && if [ -f .env ]; then sudo chown \"\$USER:\$USER\" .env && sudo chmod 600 .env; fi"

echo "==> Готово"
