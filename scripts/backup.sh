#!/usr/bin/env bash
# Бэкап БД + медиа → локально и на Яндекс Диск (rclone).
# Запуск из каталога проекта: ./scripts/backup.sh
# Переменные окружения — см. ниже.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP_REMOTE="${BACKUP_KEEP:-14}"
RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-yadisk}"
RCLONE_PATH="${BACKUP_RCLONE_PATH:-Archeology-site/backups}"
ALERT_TO="${BACKUP_ALERT_TO:-7634216@gmail.com}"
LOG="${BACKUP_LOG:-$HOME/backup.log}"
WORKDIR=""
FAILED=0

log() {
  echo "[$(date -Is)] $*" | tee -a "$LOG"
}

cleanup() {
  if [[ -n "$WORKDIR" && -d "$WORKDIR" ]]; then
    rm -rf "$WORKDIR"
  fi
}

notify_fail() {
  local reason="$1"
  python3 - "$ALERT_TO" "$reason" <<'PY' || true
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

alert_to, reason = sys.argv[1], sys.argv[2]
secrets = Path.home() / ".msmtp-secrets"
if not secrets.is_file():
    print("Нет ~/.msmtp-secrets — письмо не отправлено", file=sys.stderr)
    raise SystemExit(1)
line = secrets.read_text(encoding="utf-8").strip().splitlines()[0]
email, password = line.split(":", 1)
email, password = email.strip(), password.strip().replace(" ", "")
body = (
    "Не удалось сделать бэкап сайта коренцвит.рф.\n\n"
    f"Причина:\n{reason}\n\n"
    "Лог на ВМ: ~/backup.log\n"
    "Проверьте: docker compose, rclone (remote yadisk), свободное место.\n"
)
msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = "[коренцвит.рф] Ошибка бэкапа"
msg["From"] = email
msg["To"] = alert_to
with smtplib.SMTP("smtp.gmail.com", 587, timeout=45) as smtp:
    smtp.starttls()
    smtp.login(email, password)
    smtp.send_message(msg)
print(f"Письмо об ошибке отправлено на {alert_to}")
PY
}

on_error() {
  local line="$1"
  FAILED=1
  local reason="Сбой в scripts/backup.sh (строка ${line}). См. ~/backup.log"
  log "ОШИБКА: $reason"
  notify_fail "$reason"
  cleanup
  exit 1
}

trap 'on_error $LINENO' ERR
trap cleanup EXIT

mkdir -p "$OUT_DIR"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/archeology-backup.XXXXXX")"

log "Старт бэкапа → $OUT_DIR (remote ${RCLONE_REMOTE}:${RCLONE_PATH})"

log "Дамп PostgreSQL…"
docker compose exec -T db pg_dump \
  -U "${POSTGRES_USER:-archeology}" \
  "${POSTGRES_DB:-archeology}" \
  >"$WORKDIR/db.sql"

log "Архив media…"
docker compose run --rm --no-deps \
  -v "$WORKDIR:/backup" \
  web \
  tar -czf /backup/media.tar.gz -C /app media

ARCHIVE="backup-${STAMP}.tar.gz"
log "Сборка $ARCHIVE…"
tar -czf "$OUT_DIR/$ARCHIVE" -C "$WORKDIR" db.sql media.tar.gz

# На ВМ оставляем только свежий полный архив
find "$OUT_DIR" -maxdepth 1 -type f -name 'backup-*.tar.gz' ! -name "$ARCHIVE" -delete
# Старые промежуточные файлы прежнего формата
find "$OUT_DIR" -maxdepth 1 -type f \( -name 'db-*.sql' -o -name 'media-*.tar.gz' \) -delete

if ! command -v rclone >/dev/null 2>&1; then
  log "rclone не установлен"
  notify_fail "На ВМ не установлен rclone. Установите и настройте remote «${RCLONE_REMOTE}»."
  exit 1
fi

REMOTES="$(rclone listremotes 2>/dev/null || true)"
if [[ "$REMOTES" != *"${RCLONE_REMOTE}:"* ]]; then
  log "Нет rclone remote «${RCLONE_REMOTE}»"
  notify_fail "Не настроен rclone remote «${RCLONE_REMOTE}». Выполните: rclone config"
  exit 1
fi

log "Загрузка на Яндекс Диск…"
rclone copy "$OUT_DIR/$ARCHIVE" "${RCLONE_REMOTE}:${RCLONE_PATH}/" --retries 3

log "Ротация на Диске (оставить ${KEEP_REMOTE})…"
mapfile -t REMOTE_FILES < <(
  rclone lsf "${RCLONE_REMOTE}:${RCLONE_PATH}/" --files-only 2>/dev/null \
    | grep -E '^backup-[0-9]{8}-[0-9]{6}\.tar\.gz$' \
    | sort -r
)
if ((${#REMOTE_FILES[@]} > KEEP_REMOTE)); then
  for old in "${REMOTE_FILES[@]:KEEP_REMOTE}"; do
    log "Удаляю старый: $old"
    rclone deletefile "${RCLONE_REMOTE}:${RCLONE_PATH}/${old}" || true
  done
fi

SIZE="$(du -h "$OUT_DIR/$ARCHIVE" | awk '{print $1}')"
log "Готово: $OUT_DIR/$ARCHIVE ($SIZE) → ${RCLONE_REMOTE}:${RCLONE_PATH}/"
echo "Готово: $OUT_DIR/$ARCHIVE → ${RCLONE_REMOTE}:${RCLONE_PATH}/"
