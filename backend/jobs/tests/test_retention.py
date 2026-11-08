"""
Tests for execution-history retention (Phase 4.1).

created_at is auto_now_add, so to simulate aged rows we create normally then
rewrite created_at via .update() (bypasses auto_now_add), the same trick the
scheduler tests use for next_fire_at.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from jobs.models import JobExecution
from jobs.services import purge_old_executions
from jobs.tasks import purge_executions
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


def _aged_execution(job, days_old):
    ex = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
    old = timezone.now() - timedelta(days=days_old)
    JobExecution.objects.filter(pk=ex.pk).update(created_at=old)
    ex.refresh_from_db()
    return ex


class TestPurgeOldExecutions:
    def test_deletes_old_keeps_recent(self):
        job = JobFactory()
        _aged_execution(job, days_old=200)
        _aged_execution(job, days_old=200)
        recent = JobExecutionFactory(job=job)  # created_at ~ now

        deleted = purge_old_executions(older_than_days=90)

        assert deleted == 2
        assert JobExecution.objects.count() == 1
        assert JobExecution.objects.filter(pk=recent.pk).exists()

    def test_boundary_inside_window_kept(self):
        job = JobFactory()
        _aged_execution(job, days_old=89)  # just inside the 90-day window

        deleted = purge_old_executions(older_than_days=90)

        assert deleted == 0
        assert JobExecution.objects.count() == 1

    def test_zero_days_disables_purge(self):
        job = JobFactory()
        _aged_execution(job, days_old=500)

        assert purge_old_executions(older_than_days=0) == 0
        assert JobExecution.objects.count() == 1

    def test_batching_deletes_everything_old(self):
        job = JobFactory()
        for _ in range(5):
            _aged_execution(job, days_old=200)

        # batch_size smaller than the number of rows exercises the loop.
        deleted = purge_old_executions(older_than_days=90, batch_size=2)

        assert deleted == 5
        assert JobExecution.objects.count() == 0


class TestPurgeTask:
    def test_leader_purges_and_reports(self):
        job = JobFactory()
        for _ in range(3):
            _aged_execution(job, days_old=200)

        result = purge_executions()

        assert result["leader"] is True
        assert result["deleted"] == 3
        assert JobExecution.objects.count() == 0
