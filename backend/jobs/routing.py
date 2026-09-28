"""WebSocket URL routing for the jobs app."""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/jobs/(?P<job_public_id>[0-9a-f-]+)/executions/$",
        consumers.ExecutionConsumer.as_asgi(),
    ),
]
