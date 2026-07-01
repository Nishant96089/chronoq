# syntax=docker/dockerfile:1.7

# ===== Base =====
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./

# ===== Dev =====
FROM base AS dev
RUN pip install -r requirements.txt -r requirements-dev.txt
COPY . .
RUN chmod +x /app/scripts/*.sh
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ===== Prod =====
FROM base AS prod
RUN pip install -r requirements.txt
COPY . .
RUN chmod +x /app/scripts/*.sh
RUN useradd --create-home --shell /bin/bash chronoq && chown -R chronoq:chronoq /app
USER chronoq
EXPOSE 8000
CMD ["gunicorn", "chronoq.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
