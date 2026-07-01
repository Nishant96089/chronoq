.PHONY: help up down build logs shell-django shell-db migrate makemigrations test lint format clean superuser

help:
	@echo "chronoq — development commands"
	@echo ""
	@echo "  make up               Start all services (detached)"
	@echo "  make down             Stop all services"
	@echo "  make build            Rebuild images"
	@echo "  make logs             Tail all logs"
	@echo "  make shell-django     Open Django shell (ipython)"
	@echo "  make shell-db         Open psql on the database"
	@echo "  make migrate          Run Django migrations"
	@echo "  make makemigrations   Create new migrations"
	@echo "  make superuser        Create Django superuser"
	@echo "  make test             Run backend tests"
	@echo "  make lint             Run ruff"
	@echo "  make format           Run black + ruff --fix"
	@echo "  make clean            Nuke volumes (destructive)"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

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

test:
	docker compose exec django pytest

lint:
	docker compose exec django ruff check .

format:
	docker compose exec django black .
	docker compose exec django ruff check --fix .

clean:
	docker compose down -v