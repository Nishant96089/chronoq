"""
chronoq URL configuration.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("jobs.urls")),
    # DRF's built-in login views — gives us session-based auth for the
    # browsable API and simplifies testing via curl with a cookie jar.
    path("api-auth/", include("rest_framework.urls")),
]
