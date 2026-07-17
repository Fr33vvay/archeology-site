#!/usr/bin/env python3
"""Письмо на почту, если на корневом диске ВМ осталось меньше порога свободного места."""

from __future__ import annotations

import argparse
import smtplib
import subprocess
import sys
from email.mime.text import MIMEText
from pathlib import Path

SECRETS_PATH = Path.home() / ".msmtp-secrets"
STATE_PATH = Path.home() / ".disk-alert-state"
THRESHOLD_GB = 5
ALERT_TO = "7634216@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def free_gb(path: str = "/") -> int:
    out = subprocess.check_output(["df", "-BG", path], text=True)
    line = out.strip().splitlines()[-1]
    avail = line.split()[3].rstrip("G")
    return int(avail)


def load_smtp_auth() -> tuple[str, str]:
    if not SECRETS_PATH.is_file():
        raise SystemExit(f"Нет файла с паролем: {SECRETS_PATH}")
    line = SECRETS_PATH.read_text(encoding="utf-8").strip().splitlines()[0]
    if ":" not in line:
        raise SystemExit(f"В {SECRETS_PATH} нужна строка email:password")
    email, password = line.split(":", 1)
    email, password = email.strip(), password.strip().replace(" ", "")
    if not email or not password:
        raise SystemExit(f"Пустой email или пароль в {SECRETS_PATH}")
    return email, password


def send_mail(subject: str, body: str) -> None:
    user, password = load_smtp_auth()
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ALERT_TO
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=45) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Отправить тестовое письмо и выйти",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=THRESHOLD_GB,
        help=f"Порог свободного места в ГБ (по умолчанию {THRESHOLD_GB})",
    )
    args = parser.parse_args()

    free = free_gb("/")
    if args.test:
        send_mail(
            "[коренцвит.рф] Тест алерта по диску",
            (
                "Это тестовое письмо: отправка с ВМ работает.\n\n"
                f"Сейчас свободно примерно {free} ГБ (порог алерта {args.threshold} ГБ).\n"
            ),
        )
        print(f"Тестовое письмо отправлено на {ALERT_TO}. Свободно: {free} ГБ")
        return 0

    if free >= args.threshold:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        print(f"OK: свободно {free} ГБ (>= {args.threshold})")
        return 0

    if STATE_PATH.exists():
        print(f"Уже алертили: свободно {free} ГБ, повторное письмо не шлём")
        return 0

    send_mail(
        f"[коренцвит.рф] Мало места на диске: {free} ГБ свободно",
        (
            f"На ВМ сайта коренцвит.рф осталось около {free} ГБ "
            f"(порог {args.threshold} ГБ).\n\n"
            "Проверка:\n"
            "  ssh freeway@158.160.180.56\n"
            "  df -h /\n"
            "  sudo du -sh /var/lib/docker/volumes/archeology-site_*\n"
        ),
    )
    STATE_PATH.write_text("alerted\n", encoding="utf-8")
    print(f"Алерт отправлен: свободно {free} ГБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
