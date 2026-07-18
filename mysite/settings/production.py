import os

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "archeology"),
        "USER": os.environ.get("POSTGRES_USER", "archeology"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

WAGTAILADMIN_BASE_URL = os.environ.get("WAGTAILADMIN_BASE_URL", "http://localhost")

# SMTP (Gmail): EMAIL_HOST_USER / EMAIL_HOST_PASSWORD в .env на ВМ.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "noreply@localhost",
)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = os.environ.get("EMAIL_SUBJECT_PREFIX", "[коренцвит.рф] ")

# Без рабочего SMTP регистрация с mandatory снова даст 500 — включаем только при наличии учётки.
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    ACCOUNT_EMAIL_VERIFICATION = os.environ.get(
        "ACCOUNT_EMAIL_VERIFICATION", "mandatory"
    )
else:
    ACCOUNT_EMAIL_VERIFICATION = "none"
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# После включения HTTPS на домене: DJANGO_COOKIE_SECURE=1 в .env
_COOKIE_SECURE = os.environ.get("DJANGO_COOKIE_SECURE", "0") == "1"
SESSION_COOKIE_SECURE = _COOKIE_SECURE
CSRF_COOKIE_SECURE = _COOKIE_SECURE

try:
    from .local import *  # noqa: F401,F403
except ImportError:
    pass
