"""
Celery tasks for chronoq.

- tick: scheduler. Finds due jobs, creates root JobExecutions, dispatches them.
- execute_job_execution: worker. Makes the HTTP call, records the result, and
  on failure schedules a retry (up to Job.max_retries) with exponential backoff.

Retry model (see docs/decisions.md):
- Star linking: every retry's parent_execution is the ROOT execution (attempt 1).
- Absolute backoff: retry.scheduled_for = root.scheduled_for + backoff * 2^(n-2).
- max_retries=N means up to N+1 total attempts (1 original + N retries).
"""

import logging

import requests
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Job, JobExecution
from .services import compute_next_fire_at, compute_retry_scheduled_for

logger = logging.getLogger(__name__)

TICK_LOOKAHEAD_SECONDS = 45


@shared_task(name="jobs.tick")
def tick() -> dict:
    """Scheduler tick. Finds due jobs and enqueues them for execution."""
    now = timezone.now()
    cutoff = now + timezone.timedelta(seconds=TICK_LOOKAHEAD_SECONDS)

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
            logger.exception("Failed to schedule job id=%s", job.id)

    result = {
        "now": now.isoformat(),
        "considered": len(due_jobs),
        "dispatched": dispatched,
    }
    logger.info("tick complete: %s", result)
    return result


def _schedule_one(job: Job, scheduled_for) -> None:
    """Create a root JobExecution (attempt 1) and dispatch the executor."""
    with transaction.atomic():
        execution = JobExecution.objects.create(
            job=job,
            scheduled_for=scheduled_for,
            status=JobExecution.Status.PENDING,
            attempt_number=1,
            parent_execution=None,
        )
        try:
            job.next_fire_at = compute_next_fire_at(job.schedule_cron, after=scheduled_for)
            Job.objects.filter(pk=job.pk).update(next_fire_at=job.next_fire_at)
        except ValueError:
            logger.error("Invalid cron on job id=%s: %r", job.id, job.schedule_cron)

    transaction.on_commit(lambda: execute_job_execution.delay(execution.id))


@shared_task(name="jobs.execute_job_execution")
def execute_job_execution(execution_id: int) -> dict:
    """Execute one JobExecution: HTTP call, record outcome, retry on failure."""
    try:
        execution = JobExecution.objects.select_related("job").get(pk=execution_id)
    except JobExecution.DoesNotExist:
        logger.error("execute_job_execution: no such execution id=%s", execution_id)
        return {"error": "not_found", "execution_id": execution_id}

    job = execution.job

    execution.status = JobExecution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.save(update_fields=["status", "started_at"])

    logger.info(
        "executing job=%s execution=%s attempt=%s url=%s method=%s",
        job.public_id,
        execution.public_id,
        execution.attempt_number,
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
        _maybe_retry(execution, job)
        return {"status": "timeout", "execution_id": execution_id}
    except requests.exceptions.RequestException as e:
        _finish(execution, status=JobExecution.Status.FAILED, error=str(e))
        _maybe_retry(execution, job)
        return {"status": "failed", "execution_id": execution_id, "error": str(e)}

    ok = response.status_code < 400
    final_status = JobExecution.Status.SUCCESS if ok else JobExecution.Status.FAILED
    _finish(
        execution,
        status=final_status,
        http_status_code=response.status_code,
        response_body=response.text,
        error=None if ok else f"HTTP {response.status_code}",
    )

    if not ok:
        _maybe_retry(execution, job)

    return {
        "status": final_status,
        "execution_id": execution_id,
        "http_status_code": response.status_code,
    }


def _maybe_retry(execution: JobExecution, job: Job) -> None:
    """
    Schedule the next attempt if this one failed and retries remain.

    max_retries=N allows N retries beyond the original (up to N+1 total).
    We retry while attempt_number <= max_retries.
    """
    if execution.attempt_number > job.max_retries:
        logger.info(
            "retries exhausted job=%s root=%s attempts=%s",
            job.public_id,
            _root_id(execution),
            execution.attempt_number,
        )
        # Phase 2.4 will fire an alert here.
        return

    next_attempt = execution.attempt_number + 1
    root = _root_execution(execution)
    retry_scheduled_for = compute_retry_scheduled_for(
        root.scheduled_for, next_attempt, job.retry_backoff_seconds
    )

    with transaction.atomic():
        retry = JobExecution.objects.create(
            job=job,
            scheduled_for=retry_scheduled_for,
            status=JobExecution.Status.PENDING,
            attempt_number=next_attempt,
            parent_execution=root,
        )

    def _dispatch():
        execute_job_execution.apply_async(args=[retry.id], eta=retry_scheduled_for)

    transaction.on_commit(_dispatch)

    logger.info(
        "scheduled retry job=%s root=%s attempt=%s at=%s",
        job.public_id,
        root.public_id,
        next_attempt,
        retry_scheduled_for.isoformat(),
    )


def _root_execution(execution: JobExecution) -> JobExecution:
    """Return the root execution (attempt 1) for a given execution."""
    if execution.parent_execution_id is None:
        return execution
    return execution.parent_execution


def _root_id(execution: JobExecution):
    return _root_execution(execution).public_id


def _finish(
    execution: JobExecution,
    *,
    status: str,
    http_status_code: int | None = None,
    response_body: str = "",
    error: str | None = None,
) -> None:
    """Record final state of an execution."""
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
