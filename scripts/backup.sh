#!/bin/sh
# Минимальный бэкап БД и медиа на ВМ.
# Запуск из каталога проекта: ./scripts/backup.sh

set -e
STAMP=$(date +%Y%m%d-%H%M%S)
OUT_DIR=${BACKUP_DIR:-./backups}
mkdir -p "$OUT_DIR"

docker compose exec -T db pg_dump -U "${POSTGRES_USER:-archeology}" "${POSTGRES_DB:-archeology}" \
  > "$OUT_DIR/db-$STAMP.sql"

docker compose run --rm --no-deps -v "$OUT_DIR:/backup" web \
  tar -czf "/backup/media-$STAMP.tar.gz" -C /app media

echo "Готово: $OUT_DIR/db-$STAMP.sql и media-$STAMP.tar.gz"
