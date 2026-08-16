"""
Tests for the scheduler tick and executor tasks.

HTTP calls are mocked with `responses` so tests are fast and deterministic.

Note on transactions: tick() uses transaction.on_commit to dispatch the
executor. pytest-django wraps tests in a rolled-back transaction, so
on_commit never fires by default. We use the django_capture_on_commit_callbacks
fixture where we need those callbacks to run.
"""

import pytest
import responses
from django.utils import timezone

from jobs.models import Job, JobExecution
from jobs.tasks import execute_job_execution, tick
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


def _set_next_fire_at(job, when):
    """
    Set next_fire_at directly in the DB, bypassing Job.save() (which would
    recompute it from the cron). This lets tests control exactly when a job
    is 'due'.
    """
    Job.objects.filter(pk=job.pk).update(next_fire_at=when)
    job.refresh_from_db()


class TestTick:
    def test_due_job_gets_execution_created(self, django_capture_on_commit_callbacks):
        job = JobFactory(is_active=True)
        _set_next_fire_at(job, timezone.now())

        with django_capture_on_commit_callbacks(execute=False):
            result = tick()

        assert result["considered"] == 1
        assert result["dispatched"] == 1
        assert JobExecution.objects.filter(job=job).count() == 1

    def test_inactive_job_not_dispatched(self):
        job = JobFactory(is_active=False)
        _set_next_fire_at(job, timezone.now())
        result = tick()
        assert result["dispatched"] == 0
        assert JobExecution.objects.count() == 0

    def test_future_job_not_dispatched(self):
        job = JobFactory(is_active=True)
        _set_next_fire_at(job, timezone.now() + timezone.timedelta(hours=1))
        result = tick()
        assert result["dispatched"] == 0

    def test_tick_advances_next_fire_at(self):
        job = JobFactory(schedule_cron="*/5 * * * *", is_active=True)
        # Pin next_fire_at to a known past-ish value so advancement is unambiguous.
        pinned = timezone.now().replace(second=0, microsecond=0)
        _set_next_fire_at(job, pinned)

        tick()

        job.refresh_from_db()
        assert job.next_fire_at > pinned


class TestExecuteJobExecution:
    @responses.activate
    def test_successful_execution(self):
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        responses.add(responses.POST, "https://example.com/hook", status=200, body="ok")
        ex = JobExecutionFactory(job=job)

        result = execute_job_execution(ex.id)

        ex.refresh_from_db()
        assert ex.status == JobExecution.Status.SUCCESS
        assert ex.http_status_code == 200
        assert result["status"] == JobExecution.Status.SUCCESS

    @responses.activate
    def test_http_error_marks_failed(self):
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        responses.add(responses.POST, "https://example.com/hook", status=500)
        ex = JobExecutionFactory(job=job)

        execute_job_execution(ex.id)

        ex.refresh_from_db()
        assert ex.status == JobExecution.Status.FAILED
        assert ex.http_status_code == 500

    @responses.activate
    def test_connection_error_marks_failed(self):
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        # No responses.add → unregistered URL raises ConnectionError.
        ex = JobExecutionFactory(job=job)

        execute_job_execution(ex.id)

        ex.refresh_from_db()
        assert ex.status == JobExecution.Status.FAILED

    def test_missing_execution_returns_error(self):
        result = execute_job_execution(999999)
        assert result.get("error") == "not_found"


class TestRetryLogic:
    @responses.activate
    def test_failure_schedules_retry(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://example.com/hook",
            http_method="POST",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        responses.add(responses.POST, "https://example.com/hook", status=500)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(root.id)

        # A retry (attempt 2) should have been created, pointing at the root.
        retries = JobExecution.objects.filter(parent_execution=root)
        assert retries.count() == 1
        retry = retries.first()
        assert retry.attempt_number == 2
        assert retry.parent_execution_id == root.id

    @responses.activate
    def test_retry_uses_absolute_backoff(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://example.com/hook",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        responses.add(responses.POST, "https://example.com/hook", status=500)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
        root_time = root.scheduled_for

        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(root.id)

        retry = JobExecution.objects.get(parent_execution=root)
        # First retry (attempt 2): delay = 60 * 2^0 = 60s from root.scheduled_for.
        expected = root_time + timezone.timedelta(seconds=60)
        assert retry.scheduled_for == expected

    @responses.activate
    def test_all_retries_point_to_root(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://example.com/hook",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        responses.add(responses.POST, "https://example.com/hook", status=500)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        # Simulate attempt 2 failing → should schedule attempt 3, still pointing at root.
        attempt2 = JobExecutionFactory(job=job, attempt_number=2, parent_execution=root)
        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(attempt2.id)

        attempt3 = JobExecution.objects.get(attempt_number=3)
        assert attempt3.parent_execution_id == root.id  # star, not chain

    @responses.activate
    def test_retries_exhausted_no_more_retries(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://example.com/hook",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        responses.add(responses.POST, "https://example.com/hook", status=500)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
        # attempt_number 4 > max_retries 3 → should NOT schedule another.
        final = JobExecutionFactory(job=job, attempt_number=4, parent_execution=root)

        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(final.id)

        # No attempt 5 created.
        assert not JobExecution.objects.filter(attempt_number=5).exists()

    @responses.activate
    def test_success_schedules_no_retry(self, django_capture_on_commit_callbacks):
        job = JobFactory(target_url="https://example.com/hook", max_retries=3)
        responses.add(responses.POST, "https://example.com/hook", status=200)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(root.id)

        # Success → no retry.
        assert JobExecution.objects.filter(parent_execution=root).count() == 0
