FROM python:3.12-slim-bookworm

RUN useradd wagtail

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DJANGO_SETTINGS_MODULE=mysite.settings.production

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /app

COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh \
 && mkdir -p /app/media /app/staticfiles \
 && chown -R wagtail:wagtail /app

COPY --chown=wagtail:wagtail . .

USER wagtail

# Заглушки SMTP/шифрования только для collectstatic на этапе сборки образа;
# на рантайме реальные секреты приходят из .env (без них production не стартует).
RUN DJANGO_SECRET_KEY=build-only \
    POSTGRES_HOST=localhost \
    EMAIL_HOST_USER=build \
    EMAIL_HOST_PASSWORD=build \
    EMAIL_ENCRYPTION_KEY=build-only-not-a-real-fernet-key-!!!! \
    python manage.py collectstatic --noinput --clear

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "mysite.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
