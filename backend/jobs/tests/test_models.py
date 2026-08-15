"""
Tests for Job/JobExecution model behavior.
"""

import pytest

from jobs.models import JobExecution
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestJobModel:
    def test_save_computes_next_fire_at(self):
        job = JobFactory(schedule_cron="*/5 * * * *", next_fire_at=None)
        job.refresh_from_db()
        assert job.next_fire_at is not None

    def test_next_fire_at_recomputed_on_cron_change(self):
        job = JobFactory(schedule_cron="0 6 * * *")
        original = job.next_fire_at
        job.schedule_cron = "0 18 * * *"
        job.save()
        job.refresh_from_db()
        assert job.next_fire_at != original

    def test_public_id_is_unique_uuid(self):
        j1 = JobFactory()
        j2 = JobFactory()
        assert j1.public_id != j2.public_id

    def test_str(self):
        job = JobFactory(name="Nightly backup")
        assert "Nightly backup" in str(job)


class TestJobExecutionModel:
    def test_response_snippet_truncated(self):
        big = "x" * 5000
        ex = JobExecutionFactory(response_body_snippet=big)
        ex.refresh_from_db()
        assert len(ex.response_body_snippet) <= JobExecution.RESPONSE_SNIPPET_MAX_LENGTH

    def test_execution_belongs_to_job(self):
        job = JobFactory()
        ex = JobExecutionFactory(job=job)
        assert ex in job.executions.all()
