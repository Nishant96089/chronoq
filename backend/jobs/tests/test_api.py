"""
API-level tests: auth enforcement, user scoping, validation.
"""

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from jobs.tests.factories import JobFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(user):
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


class TestJobsAPI:
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/jobs/")
        assert resp.status_code in (401, 403)

    def test_list_only_own_jobs(self, auth_client, user):
        JobFactory(owner=user, name="Mine")
        JobFactory(name="Someone else's")  # different owner
        resp = auth_client.get("/api/jobs/")
        assert resp.status_code == 200
        names = [j["name"] for j in resp.data["results"]]
        assert "Mine" in names
        assert "Someone else's" not in names

    def test_create_job(self, auth_client):
        payload = {
            "name": "New job",
            "target_url": "https://example.com/hook",
            "http_method": "POST",
            "schedule_cron": "*/5 * * * *",
        }
        resp = auth_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 201
        assert resp.data["next_fire_at"] is not None

    def test_create_rejects_invalid_cron(self, auth_client):
        payload = {
            "name": "Bad cron",
            "target_url": "https://example.com/hook",
            "schedule_cron": "not a cron",
        }
        resp = auth_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 400
        assert "schedule_cron" in resp.data

    def test_trigger_creates_execution(self, auth_client, user):
        job = JobFactory(owner=user)
        resp = auth_client.post(f"/api/jobs/{job.public_id}/trigger/")
        assert resp.status_code == 202
        assert resp.data["status"] == "pending"

    def test_cannot_access_others_job(self, auth_client):
        other_job = JobFactory()  # different owner
        resp = auth_client.get(f"/api/jobs/{other_job.public_id}/")
        assert resp.status_code == 404
