# Регистрация и вход

На сайте доступны:

1. **Регистрация по почте** — только российские адреса (Yandex, Mail.ru, Rambler и др., а также почта в зоне `.ru`).
2. **Вход через VK ID**.

Страницы: `/accounts/login/`, `/accounts/signup/`, `/accounts/logout/`.

## Почта

Проверка домена — в `accounts/email_domains.py`.  
Дополнительные домены можно добавить в `.env`:

```env
RUSSIAN_EMAIL_DOMAINS=example.ru,myuni.ru
```

Подтверждение письма сейчас **необязательное** (SMTP не настроен). Для обязательного подтверждения позже понадобится почтовый сервер и `ACCOUNT_EMAIL_VERIFICATION=mandatory`.

## Как создать приложение VK ID

1. Откройте [VK ID / кабинет приложений](https://id.vk.ru/about/business/go) или [создание приложения](https://vk.com/editapp?act=create) (тип — сайт / веб).
2. Укажите адрес сайта: `https://коренцвит.рф` (или `http://коренцвит.рф`, пока нет HTTPS).
3. Redirect / callback URL (типичный для allauth):

   `https://коренцвит.рф/accounts/vk/login/callback/`

   Пока сайт только по IP:

   `http://158.160.180.56/accounts/vk/login/callback/`

4. Скопируйте **Application ID** (client_id) и **Защищённый ключ** (secret).
5. На сервере в `/opt/archeology-site/.env` добавьте:

```env
VK_CLIENT_ID=ваш_id
VK_SECRET=ваш_секрет
```

6. Перезапустите:

```bash
cd /opt/archeology-site
sudo docker compose up -d web
```

Кнопка «Войти через VK» появится только если оба ключа заданы.

## Редакторы сайта

Аккаунты редакторов Wagtail (`/admin/`) — отдельные. Публичная регистрация **не** даёт доступ в админку.
