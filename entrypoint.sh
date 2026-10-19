#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static assets..."
python manage.py collectstatic --noinput

echo "Verifying default owner and admin accounts..."
python manage.py create_initial_owner || true

echo "Starting server: $@"
exec "$@"
