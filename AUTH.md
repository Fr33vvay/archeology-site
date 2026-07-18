# Регистрация и вход

Публичная регистрация — **только по российской почте** (Yandex, Mail.ru, Rambler и др., а также адреса в зоне `.ru` / `.рф`).

Страницы: `/accounts/login/`, `/accounts/signup/`, `/accounts/logout/`.

## Почта

Проверка домена — в `accounts/email_domains.py`.  
Дополнительные домены можно добавить в `.env`:

```env
RUSSIAN_EMAIL_DOMAINS=example.ru,myuni.ru
```

На проде: письмо подтверждения **обязательно** (`ACCOUNT_EMAIL_VERIFICATION=mandatory`).  
SMTP — Gmail (`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` в `.env`). Пока учётка не задана, сайт откатывается к console backend и без проверки (чтобы не ломать signup).

## Редакторы сайта

Аккаунты редакторов Wagtail (`/admin/`) — отдельные. Публичная регистрация **не** даёт доступ в админку.
