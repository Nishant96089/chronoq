"""
Job and JobExecution models.

Design notes (see docs/decisions.md for full reasoning):
- Hybrid primary keys: BigAutoField `id` for internal joins, UUID `public_id` for URLs.
- Executions are append-only. We never mutate history — retries create new rows.
- `next_fire_at` is a stored, indexed field so the scheduler's core query is a fast range scan.
- No `last_run_at`/`last_status` on Job. That info lives on JobExecution.
"""

import uuid

from django.conf import settings
from django.db import models


class Job(models.Model):
    """
    A scheduled job. Represents 'run this HTTP call on this schedule'.

    A Job is a stable definition. It doesn't track run history — that's on JobExecution.
    """

    class HTTPMethod(models.TextChoices):
        GET = "GET", "GET"
        POST = "POST", "POST"
        PUT = "PUT", "PUT"
        PATCH = "PATCH", "PATCH"
        DELETE = "DELETE", "DELETE"

    # ===== Identity =====
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
    )

    # ===== What to do =====
    name = models.CharField(max_length=200)
    target_url = models.URLField(max_length=2000)
    http_method = models.CharField(
        max_length=10,
        choices=HTTPMethod.choices,
        default=HTTPMethod.POST,
    )
    headers = models.JSONField(default=dict, blank=True)
    body = models.TextField(blank=True, default="")
    timeout_seconds = models.PositiveIntegerField(default=30)

    # ===== When to do it =====
    # Cron expression: "0 6 * * *" = 6 AM daily. We use croniter to compute next_fire_at.
    schedule_cron = models.CharField(max_length=100)
    # Denormalized: computed from schedule_cron on save + after each fire.
    # This is the field the scheduler queries on. Index is critical.
    next_fire_at = models.DateTimeField(null=True, blank=True)

    # ===== Retry policy =====
    max_retries = models.PositiveIntegerField(default=3)
    retry_backoff_seconds = models.PositiveIntegerField(default=60)

    # ===== Lifecycle =====
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # The scheduler's core query: "give me active jobs whose next_fire_at is soon".
        # Composite index because we always filter on both.
        indexes = [
            models.Index(
                fields=["is_active", "next_fire_at"],
                name="job_active_next_fire_idx",
            ),
            models.Index(fields=["owner", "-created_at"], name="job_owner_created_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.public_id})"


class JobExecution(models.Model):
    """
    A single run event of a Job. Append-only — never mutate after finish.

    Retries create new JobExecution rows linked to the original via parent_execution.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        TIMEOUT = "timeout", "Timeout"

    # ===== Identity =====
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="executions")

    # ===== Lifecycle state =====
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # When this execution was *supposed* to fire (per schedule).
    scheduled_for = models.DateTimeField()
    # When the worker actually picked it up and started making the HTTP call.
    started_at = models.DateTimeField(null=True, blank=True)
    # When the HTTP call returned (success or failure).
    finished_at = models.DateTimeField(null=True, blank=True)

    # ===== Retry graph =====
    attempt_number = models.PositiveIntegerField(default=1)
    parent_execution = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retries",
    )

    # ===== Result =====
    http_status_code = models.PositiveIntegerField(null=True, blank=True)
    # Truncated to prevent DB bloat from large responses. See save() below.
    response_body_snippet = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    # ===== Housekeeping =====
    created_at = models.DateTimeField(auto_now_add=True)

    RESPONSE_SNIPPET_MAX_LENGTH = 2048

    class Meta:
        indexes = [
            # "Show me recent executions for this job" — the dashboard's main query.
            models.Index(fields=["job", "-started_at"], name="exec_job_started_idx"),
            # "Find stuck executions" — Phase 2 will need this for timeout detection.
            models.Index(fields=["status", "scheduled_for"], name="exec_status_sched_idx"),
        ]
        ordering = ["-scheduled_for"]

    def __str__(self) -> str:
        return f"{self.job.name} @ {self.scheduled_for.isoformat()} [{self.status}]"

    def save(self, *args, **kwargs):
        # Enforce snippet size at write time. Belt-and-suspenders: workers should truncate
        # before assigning, but this catches any that don't.
        if (
            self.response_body_snippet
            and len(self.response_body_snippet) > self.RESPONSE_SNIPPET_MAX_LENGTH
        ):
            self.response_body_snippet = self.response_body_snippet[
                : self.RESPONSE_SNIPPET_MAX_LENGTH
            ]
        super().save(*args, **kwargs)
