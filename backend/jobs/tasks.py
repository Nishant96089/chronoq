"""
Celery tasks for chronoq.

Two tasks power Phase 1:

- ``tick`` — the scheduler. Runs periodically via Celery Beat. Finds jobs whose
  next_fire_at has arrived, creates JobExecution rows, dispatches execution.

- ``execute_job_execution`` — the worker. Takes a JobExecution id, makes the
  HTTP call, records the result. Updates the parent Job's next_fire_at when done.

Phase 1 is single-node — no distributed locking, no retries, no circuit breaker.
Phase 2 adds retries + timeouts. Phase 3 adds distributed leader election.
"""

import logging

import requests
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Job, JobExecution
from .services import compute_next_fire_at

logger = logging.getLogger(__name__)

# When tick runs, it considers jobs whose next_fire_at is within this window
# from "now". Slightly wider than the beat interval so nothing slips through
# the cracks if a tick runs late.
TICK_LOOKAHEAD_SECONDS = 45


@shared_task(name="jobs.tick")
def tick() -> dict:
    """
    Scheduler tick. Finds due jobs and enqueues them for execution.

    Runs every 30s via Celery Beat. Returns a small summary dict for
    observability (log lines will show it).

    Design notes:
    - We compute an in-memory 'now'. Jobs due within TICK_LOOKAHEAD_SECONDS
      are considered ready. This absorbs a few seconds of clock skew or
      tick jitter.
    - Each due job gets a JobExecution row created (status=pending) inside
      a transaction, then dispatched via .delay() AFTER commit so the
      worker can't pick it up before the row is visible.
    - We update the Job's next_fire_at immediately so a subsequent tick
      before this execution completes won't fire it again.
    """
    now = timezone.now()
    cutoff = now + timezone.timedelta(seconds=TICK_LOOKAHEAD_SECONDS)

    # Fetch due jobs. The composite index (is_active, next_fire_at) makes
    # this a fast range scan even at 100k jobs.
    due_jobs = list(
        Job.objects.filter(
            is_active=True,
            next_fire_at__isnull=False,
            next_fire_at__lte=cutoff,
        ).only("id", "public_id", "schedule_cron", "next_fire_at")
    )

    dispatched = 0
    for job in due_jobs:
        try:
            _schedule_one(job, scheduled_for=job.next_fire_at)
            dispatched += 1
        except Exception:
            # Never let one bad job break the whole tick.
            logger.exception("Failed to schedule job id=%s", job.id)

    result = {"now": now.isoformat(), "considered": len(due_jobs), "dispatched": dispatched}
    logger.info("tick complete: %s", result)
    return result


def _schedule_one(job: Job, scheduled_for) -> None:
    """
    Create a JobExecution and dispatch the executor task.

    Transactionally: create the execution row and update the Job's
    next_fire_at. Dispatch the Celery task only AFTER commit — otherwise
    a worker could pick up the id before the row is visible to other DB
    connections.
    """
    with transaction.atomic():
        execution = JobExecution.objects.create(
            job=job,
            scheduled_for=scheduled_for,
            status=JobExecution.Status.PENDING,
        )
        # Advance the schedule so the same fire time can't be picked up again.
        # We compute the NEXT fire time relative to the one we just consumed,
        # not to "now", so we don't drift.
        try:
            job.next_fire_at = compute_next_fire_at(job.schedule_cron, after=scheduled_for)
            Job.objects.filter(pk=job.pk).update(next_fire_at=job.next_fire_at)
        except ValueError:
            logger.error("Invalid cron on job id=%s: %r", job.id, job.schedule_cron)

    # Dispatch AFTER the transaction commits. on_commit ensures ordering.
    transaction.on_commit(lambda: execute_job_execution.delay(execution.id))


@shared_task(name="jobs.execute_job_execution")
def execute_job_execution(execution_id: int) -> dict:
    """
    Execute one JobExecution: make the HTTP call, record the outcome.

    Runs inside a Celery worker. We update the execution's status in stages
    so an observer (dashboard, admin) sees pending -> running -> success/failed.
    """
    try:
        execution = JobExecution.objects.select_related("job").get(pk=execution_id)
    except JobExecution.DoesNotExist:
        logger.error("execute_job_execution: no such execution id=%s", execution_id)
        return {"error": "not_found", "execution_id": execution_id}

    job = execution.job

    # Transition to running.
    execution.status = JobExecution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.save(update_fields=["status", "started_at"])

    logger.info(
        "executing job=%s execution=%s url=%s method=%s",
        job.public_id,
        execution.public_id,
        job.target_url,
        job.http_method,
    )

    try:
        response = requests.request(
            method=job.http_method,
            url=job.target_url,
            headers=job.headers or {},
            data=job.body or None,
            timeout=job.timeout_seconds,
        )
    except requests.exceptions.Timeout as e:
        _finish(execution, status=JobExecution.Status.TIMEOUT, error=str(e))
        return {"status": "timeout", "execution_id": execution_id}
    except requests.exceptions.RequestException as e:
        _finish(execution, status=JobExecution.Status.FAILED, error=str(e))
        return {"status": "failed", "execution_id": execution_id, "error": str(e)}

    # Any 2xx / 3xx is success. 4xx / 5xx is a failed HTTP call.
    ok = response.status_code < 400
    final_status = JobExecution.Status.SUCCESS if ok else JobExecution.Status.FAILED
    _finish(
        execution,
        status=final_status,
        http_status_code=response.status_code,
        response_body=response.text,
        error=None if ok else f"HTTP {response.status_code}",
    )
    return {
        "status": final_status,
        "execution_id": execution_id,
        "http_status_code": response.status_code,
    }


def _finish(
    execution: JobExecution,
    *,
    status: str,
    http_status_code: int | None = None,
    response_body: str = "",
    error: str | None = None,
) -> None:
    """Record final state of an execution. Truncation handled by model.save()."""
    execution.status = status
    execution.finished_at = timezone.now()
    if http_status_code is not None:
        execution.http_status_code = http_status_code
    if response_body:
        execution.response_body_snippet = response_body
    if error:
        execution.error_message = error
    execution.save(
        update_fields=[
            "status",
            "finished_at",
            "http_status_code",
            "response_body_snippet",
            "error_message",
        ]
    )
    logger.info(
        "execution finished id=%s status=%s http=%s",
        execution.id,
        status,
        http_status_code,
    )
