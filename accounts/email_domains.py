"""Разрешённые домены почты для публичной регистрации (российские сервисы)."""

from __future__ import annotations

import os

# Основные российские почтовые сервисы.
DEFAULT_ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "yandex.ru",
        "ya.ru",
        "yandex.by",
        "yandex.kz",
        "mail.ru",
        "inbox.ru",
        "list.ru",
        "bk.ru",
        "internet.ru",
        "rambler.ru",
        "lenta.ru",
        "autorambler.ru",
        "myrambler.ru",
        "ro.ru",
        "vk.com",  # иногда выдаётся при связке с VK
    }
)


def allowed_email_domains() -> frozenset[str]:
    extra = os.environ.get("RUSSIAN_EMAIL_DOMAINS", "")
    domains = set(DEFAULT_ALLOWED_EMAIL_DOMAINS)
    for part in extra.split(","):
        d = part.strip().lower()
        if d:
            domains.add(d)
    return frozenset(domains)


def is_russian_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if domain in allowed_email_domains():
        return True
    # Корпоративная / вузовская почта в зонах РФ
    return (
        domain.endswith(".ru")
        or domain.endswith(".su")
        or domain.endswith(".рф")
        or domain.endswith(".xn--p1ai")
    )
