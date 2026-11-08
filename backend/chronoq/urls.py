"""
chronoq URL configuration.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.throttling import ScopedRateThrottle

from chronoq.health import healthz, readyz


class ThrottledObtainAuthToken(ObtainAuthToken):
    """
    Token login with a tight, dedicated rate limit (brute-force guard).

    The login endpoint is the primary credential-guessing target, so it gets its
    own scope ("login"), far tighter than the authenticated API, keyed by client
    IP. Rate from DEFAULT_THROTTLE_RATES['login'].
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("api/", include("jobs.urls")),
    # Token login: POST {username, password} -> {"token": "..."} (rate-limited)
    path("api/auth/token/", ThrottledObtainAuthToken.as_view(), name="api_token_auth"),
    # Session login for the browsable API.
    path("api-auth/", include("rest_framework.urls")),
    # Prometheus metrics endpoint (aggregates multiprocess metrics).
    path("", include("django_prometheus.urls")),
]
