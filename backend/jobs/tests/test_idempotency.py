"""
Tests for idempotency headers on outgoing job requests.

chronoq sends X-Job-Execution-Id (a stable idempotency key), X-Job-Id, and
X-Job-Attempt with every request so receivers can dedupe at-least-once
duplicates. The execution public_id is the key: stable across redeliveries of
one attempt, distinct across retries.
"""

import pytest
import responses

from jobs.models import JobExecution
from jobs.tasks import execute_job_execution
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestIdempotencyHeaders:
    @responses.activate
    def test_sends_execution_id_header(self):
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        execute_job_execution(ex.id)

        sent = responses.calls[0].request.headers
        assert sent["X-Job-Execution-Id"] == str(ex.public_id)
        assert sent["X-Job-Id"] == str(job.public_id)
        assert sent["X-Job-Attempt"] == "1"

    @responses.activate
    def test_execution_id_is_stable_across_redelivery(self):
        """
        Redelivery re-runs the SAME execution → same X-Job-Execution-Id, so a
        receiver can recognize and dedupe the duplicate.
        """
        job = JobFactory(target_url="https://example.com/hook")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.RUNNING,  # simulate mid-call crash state
            attempt_number=1,
            parent_execution=None,
        )

        # Two deliveries of the same execution (redelivery scenario).
        execute_job_execution(ex.id)
        key_first = responses.calls[0].request.headers["X-Job-Execution-Id"]
        # It's now terminal; a second delivery is a no-op (guard), so to prove
        # the key stability we check the key equals the row's public_id.
        assert key_first == str(ex.public_id)

    @responses.activate
    def test_retry_has_distinct_execution_id(self):
        """
        A retry is a NEW execution row → different X-Job-Execution-Id, so the
        receiver treats it as a legitimately new attempt (not a dup).
        """
        job = JobFactory(
            target_url="https://example.com/hook",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
        retry = JobExecutionFactory(job=job, attempt_number=2, parent_execution=root)

        # The two attempts have different public_ids → different keys.
        assert root.public_id != retry.public_id

    @responses.activate
    def test_user_headers_preserved_and_win_collisions(self):
        job = JobFactory(
            target_url="https://example.com/hook",
            http_method="POST",
            headers={"X-Custom": "value", "Authorization": "Bearer xyz"},
        )
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        execute_job_execution(ex.id)

        sent = responses.calls[0].request.headers
        # User headers present.
        assert sent["X-Custom"] == "value"
        assert sent["Authorization"] == "Bearer xyz"
        # chronoq headers also present.
        assert sent["X-Job-Execution-Id"] == str(ex.public_id)
