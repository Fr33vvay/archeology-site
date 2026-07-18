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
SMTP — Gmail (`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` в `.env`). Без этих переменных production-настройки **не стартуют** (`ImproperlyConfigured`) — откат к `verification=none` запрещён.

Подтверждение email только через POST (`ACCOUNT_CONFIRM_EMAIL_ON_GET=False`): ссылка из письма открывает форму, пользователь нажимает «Подтвердить».

## Ограничение частоты (nginx)

В `nginx/default-ssl.conf` (и HTTP-конфигах):

- `/accounts/` — `5r/s`, `burst=20` (login/signup и связанные страницы)
- POST комментариев (`/comments/`, `/blog/comments/`) — мягкий лимит `10r/m`, `burst=10`

## Редакторы сайта

Аккаунты редакторов Wagtail (`/admin/`) — отдельные. Публичная регистрация **не** даёт доступ в админку.
