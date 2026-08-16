"""
Tests for the alerting system: throttling, channel sending, and fire_alert
dispatch. Email uses Django's locmem backend; webhooks are mocked with responses.

The clear_alerts fixture flushes alert:* Redis keys so throttle state doesn't
leak between tests.
"""

import pytest
import responses
from django.core import mail

from jobs.alerts import (
    CONDITION_RETRIES_EXHAUSTED,
    fire_alert,
    send_alert,
    should_send,
)
from jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


class TestThrottle:
    def test_first_call_allowed(self):
        assert should_send("job-abc", CONDITION_RETRIES_EXHAUSTED) is True

    def test_second_call_throttled(self):
        should_send("job-abc", CONDITION_RETRIES_EXHAUSTED)
        # Same job + condition again within the window → throttled.
        assert should_send("job-abc", CONDITION_RETRIES_EXHAUSTED) is False

    def test_different_condition_not_throttled(self):
        should_send("job-abc", "retries_exhausted")
        # Different condition → independent throttle.
        assert should_send("job-abc", "circuit_open") is True

    def test_different_job_not_throttled(self):
        should_send("job-abc", CONDITION_RETRIES_EXHAUSTED)
        assert should_send("job-xyz", CONDITION_RETRIES_EXHAUSTED) is True


class TestSendAlert:
    def test_email_sent(self):
        result = send_alert(
            job_public_id="abc",
            job_name="Test",
            condition="retries_exhausted",
            detail="all failed",
            alert_email="ops@example.com",
        )
        assert result["email"] == "sent"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["ops@example.com"]
        assert "retries_exhausted" in mail.outbox[0].subject

    @responses.activate
    def test_webhook_sent(self):
        responses.add(responses.POST, "https://hooks.example.com/alert", status=200)
        result = send_alert(
            job_public_id="abc",
            job_name="Test",
            condition="circuit_open",
            detail="domain down",
            alert_webhook_url="https://hooks.example.com/alert",
        )
        assert result["webhook"] == "status 200"
        # Verify the payload was JSON with the right fields.
        body = responses.calls[0].request.body
        assert "circuit_open" in body

    @responses.activate
    def test_both_channels(self):
        responses.add(responses.POST, "https://hooks.example.com/alert", status=200)
        result = send_alert(
            job_public_id="abc",
            job_name="Test",
            condition="retries_exhausted",
            detail="x",
            alert_email="ops@example.com",
            alert_webhook_url="https://hooks.example.com/alert",
        )
        assert result["email"] == "sent"
        assert result["webhook"] == "status 200"

    def test_no_channels_noops(self):
        result = send_alert(
            job_public_id="abc",
            job_name="Test",
            condition="retries_exhausted",
            detail="x",
        )
        assert result["email"] is None
        assert result["webhook"] is None


class TestFireAlert:
    def test_dispatches_when_configured(self):
        job = JobFactory(alert_email="ops@example.com")
        # fire_alert calls send_alert.delay; in eager mode it runs inline.
        dispatched = fire_alert(job, CONDITION_RETRIES_EXHAUSTED, detail="x")
        assert dispatched is True

    def test_skips_when_no_channels(self):
        job = JobFactory(alert_email="", alert_webhook_url="")
        dispatched = fire_alert(job, CONDITION_RETRIES_EXHAUSTED, detail="x")
        assert dispatched is False

    def test_throttled_second_time(self):
        job = JobFactory(alert_email="ops@example.com")
        first = fire_alert(job, CONDITION_RETRIES_EXHAUSTED, detail="x")
        second = fire_alert(job, CONDITION_RETRIES_EXHAUSTED, detail="x")
        assert first is True
        assert second is False  # throttled
