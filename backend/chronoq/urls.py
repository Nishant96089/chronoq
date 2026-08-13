"""
chronoq URL configuration.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("jobs.urls")),
    # Token login: POST {username, password} -> {"token": "..."}
    path("api/auth/token/", obtain_auth_token, name="api_token_auth"),
    # Session login for the browsable API.
    path("api-auth/", include("rest_framework.urls")),
]
