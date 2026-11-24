from .base import *  # noqa

DEBUG = True

INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
INTERNAL_IPS = ["127.0.0.1"]


# Dev: print emails to the console instead of sending them.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "chronoq <noreply@chronoq.local>"


# Dev/test jobs commonly target localhost webhooks and mocked hosts.
ALLOW_PRIVATE_TARGET_URLS = True
