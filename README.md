# Научный архив (archeology-site)

Академический сайт-архив на **Wagtail**: статьи с иллюстрациями, галерея по папкам, поиск, контакты.  
Публичной регистрации и комментариев в MVP нет.

Репозиторий: https://github.com/Fr33vvay/archeology-site

## Локальный запуск (разработка)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_demo
python manage.py runserver
```

Откройте http://127.0.0.1:8000/ и админку http://127.0.0.1:8000/admin/

Демо-логины (смените сразу):

| Пользователь | Пароль |
|---|---|
| `admin` | `admin-change-me` |
| `editor` | `editor-change-me` |

Памятка для редакторов: [EDITORS.md](EDITORS.md)  
Регистрация по почте: [AUTH.md](AUTH.md)

## Деплой на ВМ в Яндекс Облаке (Docker Compose)

1. Создайте новую виртуальную машину (Ubuntu 22.04/24.04), диск 20–40 ГБ, публичный IP.
2. В группе безопасности откройте порты **22** (SSH), **80** (HTTP) и **443** (HTTPS).
3. На ВМ установите Docker и Docker Compose plugin.
4. Склонируйте репозиторий и настройте окружение:

```bash
git clone https://github.com/Fr33vvay/archeology-site.git
cd archeology-site
cp .env.example .env
# отредактируйте .env: DJANGO_SECRET_KEY, POSTGRES_PASSWORD, WAGTAILADMIN_BASE_URL=http://ВАШ_IP
docker compose up -d --build
```

Сайт: `http://ВАШ_IP/`  
Админка: `http://ВАШ_IP/admin/`

Повторный запуск демо: `LOAD_DEMO=1` в `.env` (по умолчанию включено при первом старте контейнера). После наполнения можно поставить `LOAD_DEMO=0`.

### Бэкап

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

## Домен и HTTPS

Домен: `коренцвит.рф` (punycode `xn--b1afkfqeou7a.xn--p1ai`).

1. A-записи `@` и `www` → IP ВМ.
2. В группе безопасности Яндекс Облака откройте **443/TCP**.
3. На ВМ:

```bash
cd /opt/archeology-site
sudo git pull
# опционально: CERTBOT_EMAIL=you@yandex.ru
sudo bash scripts/enable-https.sh
sudo docker compose up -d --build
```

Сайт: https://коренцвит.рф/  
Продление сертификата — cron (настраивает скрипт).

## Стек

Wagtail + Django + PostgreSQL + Nginx + Gunicorn. Медиа — том на диске ВМ.
