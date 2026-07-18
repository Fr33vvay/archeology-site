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

# Нет локального SMTP на ВМ — не пытаемся слать почту через localhost:25.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# После включения HTTPS на домене: DJANGO_COOKIE_SECURE=1 в .env
_COOKIE_SECURE = os.environ.get("DJANGO_COOKIE_SECURE", "0") == "1"
SESSION_COOKIE_SECURE = _COOKIE_SECURE
CSRF_COOKIE_SECURE = _COOKIE_SECURE

try:
    from .local import *  # noqa: F401,F403
except ImportError:
    pass
