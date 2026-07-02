.PHONY: help up down build logs shell-django shell-db migrate makemigrations test lint format clean superuser status check

help:
	@echo "chronoq — development commands"
	@echo ""
	@echo "  make up               Start all services (detached)"
	@echo "  make down             Stop all services"
	@echo "  make build            Rebuild images"
	@echo "  make status           Show running services"
	@echo "  make logs             Tail all logs"
	@echo "  make shell-django     Open Django shell (requires 'make up')"
	@echo "  make shell-db         Open psql on the database (requires 'make up')"
	@echo "  make migrate          Run Django migrations (requires 'make up')"
	@echo "  make makemigrations   Create new migrations (requires 'make up')"
	@echo "  make superuser        Create Django superuser (requires 'make up')"
	@echo "  make test             Run backend tests"
	@echo "  make lint             Run ruff (read-only)"
	@echo "  make format           Run black + ruff --fix + black (chain-safe)"
	@echo "  make check            Run ruff + black --check + pytest (what CI runs)"
	@echo "  make clean            Nuke volumes (destructive)"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

status:
	docker compose ps

logs:
	docker compose logs -f

# Commands that need a running service — use 'exec'
shell-django:
	docker compose exec django python manage.py shell -i ipython

shell-db:
	docker compose exec postgres psql -U chronoq -d chronoq

migrate:
	docker compose exec django python manage.py migrate

makemigrations:
	docker compose exec django python manage.py makemigrations

superuser:
	docker compose exec django python manage.py createsuperuser

# Commands that run in a throwaway container — use 'run'
test:
	docker compose run --rm django pytest

lint:
	docker compose run --rm django ruff check .

format:
	docker compose run --rm django black .
	docker compose run --rm django ruff check --fix .
	docker compose run --rm django black .

# What CI runs. Use this before every push.
check:
	docker compose run --rm django ruff check .
	docker compose run --rm django black --check .
	docker compose run --rm django pytest

clean:
	docker compose down -v