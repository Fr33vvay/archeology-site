# Бэкапы (Яндекс Диск)

Раз в **2 дня** в 04:00 скрипт кладёт архив БД+медиа на Яндекс Диск и оставляет **14** последних копий. При ошибке — письмо на `7634216@gmail.com`.

## Разовая настройка rclone на ВМ

```bash
# 1) Установить rclone (если ещё нет)
curl https://rclone.org/install.sh | sudo bash

# 2) Создать remote с именем yadisk
rclone config
```

В мастере:

1. `n` — New remote  
2. name: `yadisk`  
3. Storage: `yandex` (Яндекс Диск)  
4. Пройти авторизацию в браузере (rclone покажет ссылку; на ВМ без GUI удобно вариант с `rclone authorize` на своём ноутбуке — см. [доку rclone](https://rclone.org/yandex/))  
5. `q` — Quit  

Проверка:

```bash
rclone lsd yadisk:
rclone mkdir yadisk:Archeology-site/backups
```

## Ручной прогон

```bash
cd /opt/archeology-site
./scripts/backup.sh
```

Лог: `~/backup.log`. Локально: `/opt/archeology-site/backups/backup-….tar.gz` (только последний).

## Cron

```bash
cd /opt/archeology-site
./scripts/setup-backup-cron.sh
```

Расписание: `15 4 */2 * *` (каждые двое суток в 04:15).

## Восстановление

1. Скачать нужный `backup-….tar.gz` с Диска.  
2. Распаковать: внутри `db.sql` и `media.tar.gz`.  
3. На ВМ:

```bash
cd /opt/archeology-site
# БД (осторожно: перезапишет данные)
docker compose exec -T db psql -U archeology -d archeology < db.sql
# или сначала создать пустую БД / дропнуть таблицы — по ситуации

# Медиа
docker compose run --rm --no-deps \
  -v "$PWD:/restore:ro" \
  web \
  tar -xzf /restore/media.tar.gz -C /app
```
