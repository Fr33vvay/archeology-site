#!/bin/bash
# Запуск на чистой Ubuntu-ВМ в Яндекс Облаке.
# Пример: curl -fsSL ... | bash  ИЛИ  bash setup-vm.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Fr33vvay/archeology-site.git}"
APP_DIR="${APP_DIR:-/opt/archeology-site}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker

PUBLIC_IP="$(curl -fsSL -H Metadata-Flavor:Google http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || true)"
if [ -z "${PUBLIC_IP}" ]; then
  PUBLIC_IP="$(curl -fsSL ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
fi

if [ ! -d "${APP_DIR}/.git" ]; then
  git clone "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" pull --ff-only
fi

cd "${APP_DIR}"

if [ ! -f .env ]; then
  cp .env.example .env
  SECRET="$(openssl rand -hex 32)"
  DBPASS="$(openssl rand -hex 16)"
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${SECRET}|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DBPASS}|" .env
  sed -i "s|^WAGTAILADMIN_BASE_URL=.*|WAGTAILADMIN_BASE_URL=http://${PUBLIC_IP}|" .env
  sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=*|" .env
  # На проде демо можно отключить после переноса контента
  sed -i "s|^LOAD_DEMO=.*|LOAD_DEMO=1|" .env
fi

docker compose up -d --build

echo
echo "Готово."
echo "Сайт:    http://${PUBLIC_IP}/"
echo "Админка: http://${PUBLIC_IP}/admin/"
echo "Логины демо: admin / admin-change-me  и  editor / editor-change-me — сразу смените пароли."
echo "Каталог: ${APP_DIR}"
