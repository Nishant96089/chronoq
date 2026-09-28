"""
Tests for at-least-once redelivery correctness.

With acks_late + reject_on_worker_lost, a task can be redelivered if its worker
died. Because tick() creates the JobExecution row and the executor is keyed by
execution_id, a redelivery re-processes the SAME row (no duplicate rows). The
terminal-state guard ensures a redelivery of an already-finished execution is a
no-op (doesn't redo the HTTP call or overwrite the result).
"""

import pytest
import responses

from jobs.models import JobExecution
from jobs.tasks import execute_job_execution
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestTerminalStateGuard:
    def test_terminal_states_definition(self):
        terminal = JobExecution.Status.terminal_states()
        assert JobExecution.Status.SUCCESS in terminal
        assert JobExecution.Status.FAILED in terminal
        assert JobExecution.Status.TIMEOUT in terminal
        # Non-terminal states must NOT be in the set.
        assert JobExecution.Status.PENDING not in terminal
        assert JobExecution.Status.RUNNING not in terminal

    @responses.activate
    def test_redelivery_of_success_is_noop(self):
        """
        Execution already SUCCESS (worker crashed after recording, before ack).
        Redelivery must skip — no second HTTP call, result unchanged.
        """
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        # Register a mock; if it's called, responses records it.
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.SUCCESS,
            http_status_code=200,
            attempt_number=1,
            parent_execution=None,
        )

        result = execute_job_execution(ex.id)

        # Skipped as already-done.
        assert result["status"] == "already_done"
        # No HTTP call was made (the guard returned before the request).
        assert len(responses.calls) == 0
        # Result unchanged.
        ex.refresh_from_db()
        assert ex.status == JobExecution.Status.SUCCESS

    @responses.activate
    def test_redelivery_of_failed_is_noop(self):
        job = JobFactory(target_url="https://example.com/hook")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.FAILED,
            attempt_number=1,
            parent_execution=None,
        )

        result = execute_job_execution(ex.id)

        assert result["status"] == "already_done"
        assert len(responses.calls) == 0

    @responses.activate
    def test_redelivery_of_pending_runs(self):
        """
        Execution still PENDING (worker died before doing anything). Redelivery
        must actually run it.
        """
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.PENDING,
            attempt_number=1,
            parent_execution=None,
        )

        result = execute_job_execution(ex.id)

        # It ran and succeeded.
        assert result["status"] == JobExecution.Status.SUCCESS
        assert len(responses.calls) == 1
        ex.refresh_from_db()
        assert ex.status == JobExecution.Status.SUCCESS

    @responses.activate
    def test_redelivery_of_running_reruns(self):
        """
        Execution is RUNNING (worker crashed mid-call — we don't know if the
        call completed). Redelivery must re-run it (at-least-once: better to
        redo than to leave possibly-undone). Idempotency (next step) makes the
        possible duplicate safe on the receiver side.
        """
        job = JobFactory(target_url="https://example.com/hook", http_method="POST")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.RUNNING,
            attempt_number=1,
            parent_execution=None,
        )

        result = execute_job_execution(ex.id)

        # Re-ran to completion.
        assert result["status"] == JobExecution.Status.SUCCESS
        assert len(responses.calls) == 1


class TestNoDuplicateRows:
    @responses.activate
    def test_redelivery_does_not_create_new_row(self):
        """
        Re-processing the same execution_id operates on the SAME row — a
        redelivery never creates a second JobExecution for one logical run.
        """
        job = JobFactory(target_url="https://example.com/hook")
        responses.add(responses.POST, "https://example.com/hook", status=200)
        ex = JobExecutionFactory(
            job=job,
            status=JobExecution.Status.PENDING,
            attempt_number=1,
            parent_execution=None,
        )
        count_before = JobExecution.objects.count()

        # Process it twice (simulating a redelivery of the same task).
        execute_job_execution(ex.id)
        execute_job_execution(ex.id)  # second delivery — now terminal, no-op

        # No new rows created by either processing.
        assert JobExecution.objects.count() == count_before
