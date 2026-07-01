#!/bin/sh
set -e

# Skip the postgres-wait + migrate dance for one-off commands.
# Only run it when we're actually starting the server or a long-lived process.
case "$1" in
    python|gunicorn|celery)
        echo "Waiting for postgres..."
        until pg_isready -h "$POSTGRES_HOST" -U "$POSTGRES_USER" >/dev/null 2>&1; do
          sleep 1
        done
        echo "postgres:$POSTGRES_PORT - accepting connections"

        # Migrations should only run once — only if we're starting the Django server.
        # Not for celery workers/beat, they'd race with each other.
        if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
            echo "Running migrations..."
            python manage.py migrate --noinput
        fi
        ;;
esac

echo "Starting: $@"
exec "$@"