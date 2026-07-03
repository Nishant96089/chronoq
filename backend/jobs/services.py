"""
Service layer for job scheduling logic.

Keeping business logic out of models makes it easier to test in isolation
and reuse from scheduler tasks, views, and management commands.
"""

from datetime import datetime

from croniter import croniter
from django.utils import timezone


def compute_next_fire_at(cron_expression: str, after: datetime | None = None) -> datetime:
    """
    Given a cron expression and a reference time, return the next fire time.

    Args:
        cron_expression: Standard 5-field cron string, e.g. "0 6 * * *".
        after: Reference time. Defaults to now (timezone-aware, UTC).

    Returns:
        A timezone-aware datetime for the next scheduled fire.

    Raises:
        ValueError: If the cron expression is invalid.
    """
    if after is None:
        after = timezone.now()

    # croniter needs a valid start point; timezone-aware datetime is fine.
    itr = croniter(cron_expression, after)
    return itr.get_next(datetime)


def validate_cron_expression(cron_expression: str) -> None:
    """
    Validate a cron expression. Raises ValueError on invalid input.

    Used by model.clean() and API serializers.
    """
    if not croniter.is_valid(cron_expression):
        raise ValueError(f"Invalid cron expression: {cron_expression!r}")
