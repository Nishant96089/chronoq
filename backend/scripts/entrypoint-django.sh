#!/bin/sh
set -e

# Skip the postgres-wait + migrate dance for one-off commands
# (ruff, black, pytest). Only run it when starting the actual server.
case "$1" in
    python|gunicorn|celery)
        echo "Waiting for postgres..."
        until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" >/dev/null 2>&1; do
          sleep 1
        done
        echo "postgres:$POSTGRES_PORT - accepting connections"

        # Migrations + superuser only when starting the Django server.
        if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
            echo "Running migrations..."
            python manage.py migrate --noinput

            echo "Ensuring dev superuser exists..."
            python manage.py ensure_superuser
        fi
        ;;
esac

echo "Starting: $@"
exec "$@"
