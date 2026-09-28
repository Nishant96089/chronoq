"""
Base settings shared across all environments.
"""

from pathlib import Path

import environ

# BASE_DIR is /app inside the container, i.e. backend/ locally.
# Note: settings/base.py is 3 levels deep from BASE_DIR (settings/ -> chronoq/ -> backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# ===== Core =====
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ===== Apps =====
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "channels",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    # Local
    "jobs",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "chronoq.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "chronoq.wsgi.application"
ASGI_APPLICATION = "chronoq.asgi.application"

# ===== Database =====
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
        "CONN_MAX_AGE": env.int("DJANGO_CONN_MAX_AGE", default=60),
    }
}

# ===== Auth =====
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ===== I18n =====
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ===== Static =====
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ===== Celery =====
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# ===== At-least-once delivery hardening =====
# Requeue an in-flight task if its worker is LOST (killed/OOM), not just on
# error. Pairs with acks_late: without this, a hard-killed worker's task can
# still be lost. Tradeoff: a task that reliably crashes its worker becomes a
# "poison pill" that loops — acceptable here since our task is a bounded HTTP
# call, not something that hard-crashes workers.
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Redis has no native ack/redelivery — Celery emulates it. A task taken by a
# worker is "invisible" for this many seconds; if not acked by then, Celery
# assumes the worker died and redelivers. Must exceed our longest possible task
# (job timeout + overhead). Our jobs cap at ~timeout_seconds; 3600s default is
# plenty, but we set it explicitly for clarity.
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}

# ===== Scheduler jitter =====
# Spread scheduled dispatches over a random 0..N second window to avoid the
# thundering herd when many jobs share the same cron time (e.g. 0 * * * *).
# Applies ONLY to scheduled dispatches — not manual triggers or retries.
SCHEDULER_JITTER_SECONDS = env.int("SCHEDULER_JITTER_SECONDS", default=15)

# ===== Redis (general cache / circuit breaker) =====
REDIS_URL = env("REDIS_URL")

# ===== Channels (WebSocket) channel layer =====
# Redis-backed pub/sub bus connecting the Celery worker (event source) to
# WebSocket consumers (in the ASGI process). We use a SEPARATE Redis DB (4)
# from the broker (1), results (2), and cache/circuit-breaker (0) to keep
# concerns isolated.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("CHANNELS_REDIS_URL", default="redis://redis:6379/4")],
        },
    },
}

# ===== Django REST Framework =====
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ===== CORS =====
# In dev, the React app runs on localhost:3000 (and 127.0.0.1 variant).
# Read from env so prod can set its real domain.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)
