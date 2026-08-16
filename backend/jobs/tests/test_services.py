"""
Unit tests for jobs.services — pure cron math, no DB needed.
"""

from datetime import UTC, datetime

import pytest

from jobs.services import compute_next_fire_at, validate_cron_expression


class TestComputeNextFireAt:
    def test_every_minute(self):
        after = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
        result = compute_next_fire_at("* * * * *", after=after)
        # Next minute boundary after 12:00:30 is 12:01:00.
        assert result == datetime(2026, 1, 1, 12, 1, 0, tzinfo=UTC)

    def test_every_five_minutes(self):
        after = datetime(2026, 1, 1, 12, 2, 0, tzinfo=UTC)
        result = compute_next_fire_at("*/5 * * * *", after=after)
        # Next multiple-of-5 minute after 12:02 is 12:05.
        assert result == datetime(2026, 1, 1, 12, 5, 0, tzinfo=UTC)

    def test_daily_at_six(self):
        after = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = compute_next_fire_at("0 6 * * *", after=after)
        # Already past 6 AM on Jan 1, so next is 6 AM Jan 2.
        assert result == datetime(2026, 1, 2, 6, 0, 0, tzinfo=UTC)

    def test_advances_from_reference_not_now(self):
        # Two calls with the same reference give the same answer — deterministic.
        after = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        a = compute_next_fire_at("*/10 * * * *", after=after)
        b = compute_next_fire_at("*/10 * * * *", after=after)
        assert a == b

    def test_invalid_cron_raises(self):
        with pytest.raises((ValueError, Exception)):
            compute_next_fire_at("not a cron", after=datetime.now(UTC))


class TestValidateCronExpression:
    def test_valid_passes(self):
        validate_cron_expression("*/5 * * * *")  # should not raise

    def test_invalid_raises_valueerror(self):
        with pytest.raises(ValueError):
            validate_cron_expression("nonsense")


class TestComputeRetryScheduledFor:
    def test_first_retry_one_backoff(self):
        from datetime import UTC, datetime, timedelta

        from jobs.services import compute_retry_scheduled_for

        root = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
        result = compute_retry_scheduled_for(root, attempt_number=2, backoff_seconds=60)
        assert result == root + timedelta(seconds=60)

    def test_second_retry_double_backoff(self):
        from datetime import UTC, datetime, timedelta

        from jobs.services import compute_retry_scheduled_for

        root = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
        result = compute_retry_scheduled_for(root, attempt_number=3, backoff_seconds=60)
        assert result == root + timedelta(seconds=120)

    def test_third_retry_quadruple_backoff(self):
        from datetime import UTC, datetime, timedelta

        from jobs.services import compute_retry_scheduled_for

        root = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
        result = compute_retry_scheduled_for(root, attempt_number=4, backoff_seconds=60)
        assert result == root + timedelta(seconds=240)

    def test_attempt_one_raises(self):
        from datetime import UTC, datetime

        import pytest

        from jobs.services import compute_retry_scheduled_for

        root = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
        with pytest.raises(ValueError):
            compute_retry_scheduled_for(root, attempt_number=1, backoff_seconds=60)
