#!/usr/bin/env python3
"""Одноразово прописывает SMTP в .env из ~/.msmtp-secrets (на ВМ)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ENV_PATH = Path("/opt/archeology-site/.env")
SECRETS_PATH = Path.home() / ".msmtp-secrets"
KEYS = (
    "DJANGO_EMAIL_BACKEND",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USE_TLS",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "DEFAULT_FROM_EMAIL",
    "ACCOUNT_EMAIL_VERIFICATION",
)


def main() -> int:
    if not SECRETS_PATH.is_file():
        print(f"Нет {SECRETS_PATH}", file=sys.stderr)
        return 1
    if not ENV_PATH.is_file():
        print(f"Нет {ENV_PATH}", file=sys.stderr)
        return 1

    line = SECRETS_PATH.read_text(encoding="utf-8").strip().splitlines()[0]
    email, password = line.split(":", 1)
    email, password = email.strip(), password.strip().replace(" ", "")
    if not email or not password:
        print("Пустой email/пароль в msmtp-secrets", file=sys.stderr)
        return 1

    text = ENV_PATH.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not any(ln.startswith(k + "=") for k in KEYS)]
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines.extend(
        [
            "",
            "# SMTP / подтверждение регистрации",
            "DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST=smtp.gmail.com",
            "EMAIL_PORT=587",
            "EMAIL_USE_TLS=1",
            f"EMAIL_HOST_USER={email}",
            f"EMAIL_HOST_PASSWORD={password}",
            f"DEFAULT_FROM_EMAIL={email}",
            "ACCOUNT_EMAIL_VERIFICATION=mandatory",
            "",
        ]
    )

    out = "\n".join(lines) + "\n"
    if len(sys.argv) > 1 and sys.argv[1] == "--stdout":
        # для sudo tee без печати в наш stdout вызывающей стороны — пишем в файл-аргумент
        Path(sys.argv[2]).write_text(out, encoding="utf-8")
        print("ok")
        return 0

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(out)
        tmp = fh.name
    print(tmp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
