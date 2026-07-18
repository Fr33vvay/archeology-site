from .base import *  # noqa: F401,F403

DEBUG = True

SECRET_KEY = "django-insecure-dev-only-change-in-production"
EMAIL_ENCRYPTION_ALLOW_DERIVED_KEY = True

ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# В разработке проще без манифеста хэшей
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

try:
    from .local import *  # noqa: F401,F403
except ImportError:
    pass
