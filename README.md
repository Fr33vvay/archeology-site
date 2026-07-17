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
2. В группе безопасности откройте порты **22** (SSH) и **80** (HTTP).
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

## Домен позже

1. Купите домен у регистратора (reg.ru, timeweb, beget и т.п.).
2. Создайте A-запись `@` → IP вашей ВМ (и при желании `www`).
3. В `.env` укажите `DJANGO_ALLOWED_HOSTS=ваш.домен`, `WAGTAILADMIN_BASE_URL=https://ваш.домен`, при необходимости `DJANGO_CSRF_TRUSTED_ORIGINS=https://ваш.домен`.
4. Перезапустите: `docker compose up -d`.
5. Добавьте HTTPS (Let's Encrypt) в Nginx — приложение переносить не нужно.

## Стек

Wagtail + Django + PostgreSQL + Nginx + Gunicorn. Медиа — том на диске ВМ.
