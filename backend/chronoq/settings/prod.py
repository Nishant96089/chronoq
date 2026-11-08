"""
Production settings.

Inherits everything from base (which already reads ALLOWED_HOSTS, DEBUG,
CORS, caches, throttles, encryption keys, etc. from the environment) and layers
on the hardening a public deployment needs: TLS behind a proxy, HSTS, secure
cookies, static serving via WhiteNoise, and stdout logging.
"""

from .base import *  # noqa

DEBUG = False

# ===== TLS / proxy =====
# Behind a TLS-terminating proxy or load balancer, trust its forwarded-proto
# header so request.is_secure() is correct. Without this, SECURE_SSL_REDIRECT
# never sees "https" and redirects forever.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Env-toggleable so a plain-HTTP box (before a cert is wired) doesn't infinite
# redirect. Flip to True once HTTPS is live.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)

# Health probes hit plain HTTP internally; never redirect them or the
# orchestrator reads a 301 as "unhealthy".
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$", r"^readyz/?$"]

SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_CONTENT_TYPE_NOSNIFF = True

# HSTS is only meaningful over HTTPS — gate it on the SSL toggle.
if SECURE_SSL_REDIRECT:
    SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Cross-origin POSTs (admin login, browsable API) over HTTPS need the origin
# trusted. e.g. DJANGO_CSRF_TRUSTED_ORIGINS=https://chronoq.example.com
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# ===== Static files (WhiteNoise) =====
# WhiteNoise lets the app container serve its own admin / DRF static assets
# with compression + far-future caching, so a reverse proxy isn't required just
# for static. Middleware goes immediately after SecurityMiddleware.
_sec = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE.insert(_sec + 1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Hashed + compressed. Requires `collectstatic` (run in the entrypoint).
    # If collectstatic ever errors on a missing referenced asset, drop back to
    # "whitenoise.storage.CompressedStaticFilesStorage" (no manifest strictness).
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_FROM_EMAIL = "chronoq <noreply@chronoq.local>"

# ===== Logging (to stdout, for the container runtime to collect) =====
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "jobs": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
