#!/bin/sh
set -e

# Production Django entrypoint.
#
# Migrations are handled by the one-shot `migrate` service (so N web replicas
# never race on schema changes). Here we only wait for the DB, collect static
# for the web server, and hand off.

case "$1" in
    gunicorn|celery|python)
        echo "Waiting for postgres..."
        until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" >/dev/null 2>&1; do
          sleep 1
        done
        echo "postgres - accepting connections"

        # Only the web server needs static assets + the metrics dir.
        if [ "$1" = "gunicorn" ]; then
            mkdir -p "${PROMETHEUS_MULTIPROC_DIR:-/app/prometheus_multiproc}"
            echo "Collecting static files..."
            python manage.py collectstatic --noinput
        fi
        ;;
esac

echo "Starting: $@"
exec "$@"
