#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${LOAD_DEMO:-0}" = "1" ]; then
  python manage.py load_demo
fi

exec "$@"
