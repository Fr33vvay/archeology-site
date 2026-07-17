#!/usr/bin/env bash
# Выпуск Let's Encrypt и включение HTTPS для коренцвит.рф.
# Запуск на ВМ: sudo bash scripts/enable-https.sh
# Перед запуском откройте порт 443 в группе безопасности Яндекс Облака.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/archeology-site}"
DOMAIN_PUNY="xn--b1afkfqeou7a.xn--p1ai"
EMAIL="${CERTBOT_EMAIL:-}"
cd "${APP_DIR}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите от root: sudo bash scripts/enable-https.sh"
  exit 1
fi

mkdir -p /var/www/certbot /etc/letsencrypt
chmod 755 /var/www/certbot

echo "→ Nginx: HTTP + ACME..."
cp -f nginx/http-acme.conf nginx/default.conf
docker compose up -d
sleep 3
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload || true

CERT_LIVE="/etc/letsencrypt/live/${DOMAIN_PUNY}/fullchain.pem"
if [[ ! -f "${CERT_LIVE}" ]]; then
  CERTBOT_ARGS=(
    certonly
    --webroot
    -w /var/www/certbot
    -d "${DOMAIN_PUNY}"
    -d "www.${DOMAIN_PUNY}"
    --agree-tos
    --non-interactive
  )
  if [[ -n "${EMAIL}" ]]; then
    CERTBOT_ARGS+=(--email "${EMAIL}")
  else
    CERTBOT_ARGS+=(--register-unsafely-without-email)
  fi

  echo "→ Запрос сертификата Let's Encrypt..."
  docker run --rm \
    -v /var/www/certbot:/var/www/certbot \
    -v /etc/letsencrypt:/etc/letsencrypt \
    certbot/certbot "${CERTBOT_ARGS[@]}"
else
  echo "→ Сертификат уже есть: ${CERT_LIVE}"
fi

echo "→ Включаем HTTPS-конфиг..."
cp -f nginx/default-ssl.conf nginx/default.conf
docker compose up -d nginx
sleep 2
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "→ Обновляем .env под HTTPS..."
if [[ -f .env ]]; then
  if grep -q '^WAGTAILADMIN_BASE_URL=' .env; then
    sed -i 's|^WAGTAILADMIN_BASE_URL=.*|WAGTAILADMIN_BASE_URL=https://коренцвит.рф|' .env
  else
    echo 'WAGTAILADMIN_BASE_URL=https://коренцвит.рф' >> .env
  fi
  if grep -q '^DJANGO_CSRF_TRUSTED_ORIGINS=' .env; then
    sed -i 's|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://коренцвит.рф,https://www.коренцвит.рф,https://xn--b1afkfqeou7a.xn--p1ai,https://www.xn--b1afkfqeou7a.xn--p1ai,http://158.160.180.56|' .env
  else
    echo 'DJANGO_CSRF_TRUSTED_ORIGINS=https://коренцвит.рф,https://www.коренцвит.рф,https://xn--b1afkfqeou7a.xn--p1ai,https://www.xn--b1afkfqeou7a.xn--p1ai,http://158.160.180.56' >> .env
  fi
  if grep -q '^DJANGO_COOKIE_SECURE=' .env; then
    sed -i 's|^DJANGO_COOKIE_SECURE=.*|DJANGO_COOKIE_SECURE=1|' .env
  else
    echo 'DJANGO_COOKIE_SECURE=1' >> .env
  fi
fi

docker compose up -d web

CRON_LINE='15 3 * * * cd /opt/archeology-site && docker run --rm -v /var/www/certbot:/var/www/certbot -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot renew --quiet && cp -f nginx/default-ssl.conf nginx/default.conf && docker compose exec -T nginx nginx -s reload >> /var/log/letsencrypt-renew.log 2>&1'
(crontab -l 2>/dev/null | grep -v 'certbot renew' || true; echo "${CRON_LINE}") | crontab -

echo
echo "Готово: https://коренцвит.рф/"
echo "Если https не открывается — добавьте правило 443/TCP в группу безопасности ВМ."
