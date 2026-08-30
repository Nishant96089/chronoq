"""
Tests for scheduler jitter (thundering-herd mitigation).

Jitter is applied only to SCHEDULED dispatches, not retries or manual triggers.
"""

import pytest

from jobs.services import compute_jitter_seconds

pytestmark = pytest.mark.django_db


class TestComputeJitter:
    def test_in_range(self, settings):
        settings.SCHEDULER_JITTER_SECONDS = 15
        for _ in range(50):
            j = compute_jitter_seconds()
            assert 0.0 <= j <= 15.0

    def test_respects_custom_max(self):
        for _ in range(50):
            j = compute_jitter_seconds(max_jitter_seconds=5)
            assert 0.0 <= j <= 5.0

    def test_disabled_returns_zero(self, settings):
        settings.SCHEDULER_JITTER_SECONDS = 0
        assert compute_jitter_seconds() == 0.0

    def test_negative_returns_zero(self):
        assert compute_jitter_seconds(max_jitter_seconds=-5) == 0.0

    def test_produces_spread(self, settings):
        """Many calls should produce a spread of values, not a constant."""
        settings.SCHEDULER_JITTER_SECONDS = 15
        values = {round(compute_jitter_seconds(), 3) for _ in range(50)}
        # With continuous random over [0,15], 50 draws should give many
        # distinct values (not all identical).
        assert len(values) > 10


class TestScheduledDispatchJittered:
    def test_tick_dispatch_uses_countdown(
        self, django_capture_on_commit_callbacks, settings, monkeypatch
    ):
        """
        A scheduled dispatch should call apply_async with a countdown (jitter),
        not plain delay(). We capture the apply_async call to verify.
        """
        from django.utils import timezone

        from jobs import tasks
        from jobs.models import Job
        from jobs.tests.factories import JobFactory

        settings.SCHEDULER_JITTER_SECONDS = 15

        # Capture apply_async calls on the executor task.
        calls = []

        def fake_apply_async(*args, **kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(tasks.execute_job_execution, "apply_async", fake_apply_async)

        job = JobFactory(is_active=True)
        Job.objects.filter(pk=job.pk).update(next_fire_at=timezone.now())

        with django_capture_on_commit_callbacks(execute=True):
            tasks.tick()

        # One dispatch happened, and it had a 'countdown' kwarg in [0, 15].
        assert len(calls) == 1
        assert "countdown" in calls[0]
        assert 0.0 <= calls[0]["countdown"] <= 15.0


class TestRetryNotJittered:
    def test_retry_uses_eta_not_jitter(self, django_capture_on_commit_callbacks, settings):
        """
        Retries dispatch with an absolute eta (deterministic backoff), NOT a
        jitter countdown. Verify a retry's scheduled_for equals the exact
        backoff time (no random offset added).
        """
        import responses
        from django.utils import timezone

        from jobs.models import JobExecution
        from jobs.tasks import execute_job_execution
        from jobs.tests.factories import JobExecutionFactory, JobFactory

        settings.SCHEDULER_JITTER_SECONDS = 15

        job = JobFactory(
            target_url="https://example.com/hook",
            max_retries=3,
            retry_backoff_seconds=60,
        )
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
        root_time = root.scheduled_for

        with responses.RequestsMock() as rsps:
            rsps.add(rsps.POST, "https://example.com/hook", status=500)
            with django_capture_on_commit_callbacks(execute=False):
                execute_job_execution(root.id)

        retry = JobExecution.objects.get(parent_execution=root)
        # Exact backoff, no jitter added to scheduled_for.
        expected = root_time + timezone.timedelta(seconds=60)
        assert retry.scheduled_for == expected
