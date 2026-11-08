"""
Service layer for job scheduling logic.

Keeping business logic out of models makes it easier to test in isolation
and reuse from scheduler tasks, views, and management commands.
"""

import contextlib
import random
from datetime import datetime

from croniter import croniter
from django.db import connection
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


def compute_retry_scheduled_for(root_scheduled_for, attempt_number, backoff_seconds):
    """
    Compute the scheduled_for time of a retry attempt.

    Uses exponential backoff measured absolutely from the ROOT execution's
    scheduled_for — not from when the failure occurred. Keeps retry timing
    deterministic and testable.

    Formula: root_scheduled_for + backoff_seconds * 2^(attempt_number - 2)
      - attempt_number 2 (first retry): delay = backoff * 2^0 = backoff
      - attempt_number 3: delay = backoff * 2^1 = 2 * backoff
      - attempt_number 4: delay = backoff * 2^2 = 4 * backoff
    """
    from datetime import timedelta

    if attempt_number < 2:
        raise ValueError("Retries start at attempt_number 2")

    multiplier = 2 ** (attempt_number - 2)
    delay = timedelta(seconds=backoff_seconds * multiplier)
    return root_scheduled_for + delay


# A fixed, arbitrary 64-bit integer identifying the scheduler leader lock.
# All scheduler nodes contend for THIS specific advisory lock. The number is
# arbitrary but must be the same across all nodes (it's the lock's identity).
SCHEDULER_LOCK_ID = 947218364501


@contextlib.contextmanager
def scheduler_leadership():
    """
    Context manager that acquires the scheduler advisory lock if available.

    Yields True if this process became leader (got the lock), False otherwise.
    Releases the lock on exit if it was held.

    Usage:
        with scheduler_leadership() as is_leader:
            if is_leader:
                run_the_tick()

    Uses pg_try_advisory_lock (non-blocking): returns immediately with
    True/False rather than waiting for the lock. A non-leader tick should
    skip, not queue up behind the leader.

    The lock is session-scoped (tied to this DB connection). If this process
    dies while holding it, Postgres releases it automatically — that's what
    gives us free, fast failover.
    """
    acquired = False
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SCHEDULER_LOCK_ID])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [SCHEDULER_LOCK_ID])


def compute_jitter_seconds(max_jitter_seconds=None):
    """
    Return a random dispatch delay in [0, max_jitter_seconds] to spread
    scheduled executions and avoid the thundering herd.

    Reads SCHEDULER_JITTER_SECONDS from settings when max_jitter_seconds is
    not given. Returns 0 if jitter is disabled (max <= 0), so it's a no-op
    for anyone who turns it off.
    """
    from django.conf import settings

    if max_jitter_seconds is None:
        max_jitter_seconds = getattr(settings, "SCHEDULER_JITTER_SECONDS", 0)

    if not max_jitter_seconds or max_jitter_seconds <= 0:
        return 0.0

    return random.uniform(0, max_jitter_seconds)


def purge_old_executions(older_than_days=None, batch_size=None) -> int:
    """
    Delete JobExecution rows older than the retention window, in batches.

    Execution history is append-only and grows without bound. This enforces a
    retention policy by deleting rows whose created_at is older than the cutoff.

    Deletion is CHUNKED (batch_size rows per round) so a large purge never takes
    one long lock or bloats a single transaction — each batch is its own small,
    index-driven delete. This is the production-correct way to bulk-delete in
    Postgres (a single huge DELETE causes long locks and table bloat).

    Args:
        older_than_days: rows older than this are deleted. Defaults to
            settings.EXECUTION_RETENTION_DAYS. 0 (or less) disables purging.
        batch_size: rows deleted per round. Defaults to
            settings.EXECUTION_PURGE_BATCH_SIZE.

    Returns:
        Total number of execution rows deleted.
    """
    from datetime import timedelta

    from django.conf import settings

    from .models import JobExecution

    if older_than_days is None:
        older_than_days = getattr(settings, "EXECUTION_RETENTION_DAYS", 90)
    if batch_size is None:
        batch_size = getattr(settings, "EXECUTION_PURGE_BATCH_SIZE", 1000)

    if older_than_days <= 0:
        return 0  # retention disabled

    cutoff = timezone.now() - timedelta(days=older_than_days)
    total = 0
    while True:
        # Select a batch of PKs first, then delete them. Selecting the PKs keeps
        # each delete statement small and driven by the created_at index.
        ids = list(
            JobExecution.objects.filter(created_at__lt=cutoff).values_list("pk", flat=True)[
                :batch_size
            ]
        )
        if not ids:
            break
        deleted, _ = JobExecution.objects.filter(pk__in=ids).delete()
        total += deleted
        if len(ids) < batch_size:
            break
    return total
