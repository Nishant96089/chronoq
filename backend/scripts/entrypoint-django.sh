#!/bin/sh
set -e

echo "Waiting for postgres..."
until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER"; do
  sleep 1
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting: $@"
exec "$@"