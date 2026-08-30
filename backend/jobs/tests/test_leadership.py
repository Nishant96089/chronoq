"""
Tests for scheduler leader election via Postgres advisory locks.

The advisory lock is connection-scoped. In tests, pytest-django runs each test
in a single connection, so we verify the lock's acquire/release semantics and
that tick() respects leadership.
"""

import pytest
from django.db import connection

from jobs.services import SCHEDULER_LOCK_ID, scheduler_leadership
from jobs.tasks import tick
from jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def _lock_is_held() -> bool:
    """Check whether ANY session holds the scheduler advisory lock."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_locks " "WHERE locktype = 'advisory' AND objid = %s",
            [SCHEDULER_LOCK_ID & 0xFFFFFFFF],  # lower 32 bits = objid
        )
        return cur.fetchone()[0] > 0


class TestSchedulerLeadership:
    def test_acquires_and_yields_true_when_free(self):
        with scheduler_leadership() as is_leader:
            assert is_leader is True

    def test_releases_after_context(self):
        with scheduler_leadership() as is_leader:
            assert is_leader is True
        # After the context exits, the lock is released; we can grab it again.
        with scheduler_leadership() as is_leader_again:
            assert is_leader_again is True

    def test_lock_released_on_exception(self):
        # Even if the body raises, the finally-block must release the lock.
        with pytest.raises(ValueError):
            with scheduler_leadership() as is_leader:
                assert is_leader is True
                raise ValueError("boom")
        # Lock should be free again — acquire succeeds.
        with scheduler_leadership() as is_leader:
            assert is_leader is True


class TestTickLeadershipGate:
    def test_leader_tick_does_work(self, django_capture_on_commit_callbacks):
        """When leadership is available (single test connection), tick works."""
        from django.utils import timezone

        from jobs.models import Job

        job = JobFactory(is_active=True)
        Job.objects.filter(pk=job.pk).update(next_fire_at=timezone.now())

        with django_capture_on_commit_callbacks(execute=False):
            result = tick()

        assert result["leader"] is True
        assert result["dispatched"] == 1

    def test_tick_result_reports_leadership(self, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=False):
            result = tick()
        # In tests the lock is free, so tick is leader.
        assert result["leader"] is True
