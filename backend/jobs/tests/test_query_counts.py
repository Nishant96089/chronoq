"""
Query-count tests — guard against N+1 regressions.

Django's assertNumQueries / CaptureQueriesContext count how many SQL queries
run during a block. If serializing a list of N objects runs O(N) queries
instead of O(1), that's an N+1 bug that gets worse as data grows.

These tests pin the query count so a future change that reintroduces N+1
fails loudly.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from jobs.tests.factories import JobExecutionFactory, JobFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    user = UserFactory()
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


class TestJobListQueryCount:
    def test_list_jobs_query_count_constant(self, auth_client):
        """
        Listing jobs should take a constant number of queries regardless of
        how many jobs exist. If it scales with job count → N+1.
        """
        client, user = auth_client

        # Create 3 jobs, measure query count.
        for _ in range(3):
            JobFactory(owner=user)
        with CaptureQueriesContext(connection) as ctx_small:
            resp = client.get("/api/jobs/")
        assert resp.status_code == 200
        small_count = len(ctx_small)

        # Create 20 more (23 total), measure again.
        for _ in range(20):
            JobFactory(owner=user)
        with CaptureQueriesContext(connection) as ctx_large:
            resp = client.get("/api/jobs/")
        assert resp.status_code == 200
        large_count = len(ctx_large)

        # The KEY assertion: query count must NOT grow with the number of jobs.
        # If it does, that's N+1. Allow tiny variance (pagination count query).
        assert large_count <= small_count + 1, (
            f"N+1 detected: {small_count} queries for 3 jobs, "
            f"{large_count} for 23 jobs. Query count scales with data."
        )


class TestExecutionListQueryCount:
    def test_list_executions_query_count_constant(self, auth_client):
        """Same guard for the executions endpoint (has a job FK)."""
        client, user = auth_client
        job = JobFactory(owner=user)

        for _ in range(3):
            JobExecutionFactory(job=job)
        with CaptureQueriesContext(connection) as ctx_small:
            resp = client.get("/api/executions/")
        assert resp.status_code == 200
        small_count = len(ctx_small)

        for _ in range(20):
            JobExecutionFactory(job=job)
        with CaptureQueriesContext(connection) as ctx_large:
            resp = client.get("/api/executions/")
        assert resp.status_code == 200
        large_count = len(ctx_large)

        assert large_count <= small_count + 1, (
            f"N+1 detected on executions: {small_count} queries for 3, " f"{large_count} for 23."
        )
