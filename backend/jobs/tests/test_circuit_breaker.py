"""
Tests for the circuit breaker: state machine + executor integration.

The clear_circuit_breaker fixture (conftest.py, autouse) gives each test a
clean Redis breaker state.
"""

import time

import pytest
import responses

from jobs.circuit_breaker import (
    CLOSED,
    COOLDOWN_SECONDS,
    FAILURE_THRESHOLD,
    HALF_OPEN,
    OPEN,
    CircuitBreaker,
)
from jobs.models import JobExecution
from jobs.tasks import execute_job_execution
from jobs.tests.factories import JobExecutionFactory, JobFactory

pytestmark = pytest.mark.django_db


class TestCircuitBreakerStateMachine:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.current_state("fresh.example.com") == CLOSED

    def test_trips_open_at_threshold(self):
        cb = CircuitBreaker()
        d = "trip.example.com"
        for _ in range(FAILURE_THRESHOLD - 1):
            cb.record_failure(d)
        assert cb.current_state(d) == CLOSED  # not yet
        cb.record_failure(d)  # threshold-th failure
        assert cb.current_state(d) == OPEN

    def test_open_blocks_requests(self):
        cb = CircuitBreaker()
        d = "blocked.example.com"
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(d)
        allowed, state = cb.allows_request(d)
        assert allowed is False
        assert state == OPEN

    def test_success_resets_to_closed(self):
        cb = CircuitBreaker()
        d = "reset.example.com"
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(d)
        assert cb.current_state(d) == OPEN
        cb.record_success(d)
        assert cb.current_state(d) == CLOSED

    def test_domain_extraction(self):
        cb = CircuitBreaker()
        assert cb.domain_for("https://api.example.com/path") == "api.example.com"
        assert cb.domain_for("http://localhost:8000/x") == "localhost:8000"

    def test_different_domains_isolated(self):
        cb = CircuitBreaker()
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure("a.example.com")
        # b is untouched.
        assert cb.current_state("a.example.com") == OPEN
        assert cb.current_state("b.example.com") == CLOSED


class TestCircuitBreakerExecutorIntegration:
    @responses.activate
    def test_open_circuit_fails_fast_no_retry(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://deadhost.example.com/hook",
            http_method="POST",
            max_retries=3,
        )
        # Pre-trip the breaker for this domain.
        cb = CircuitBreaker()
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure("deadhost.example.com")
        assert cb.current_state("deadhost.example.com") == OPEN

        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        with django_capture_on_commit_callbacks(execute=False):
            result = execute_job_execution(root.id)

        root.refresh_from_db()
        # Failed fast with circuit_open, and NO HTTP call was made
        # (responses would raise if an unregistered call happened, but we
        # never reach the call).
        assert result["status"] == "circuit_open"
        assert root.status == JobExecution.Status.FAILED
        assert root.error_message == "circuit_open"
        # No retry scheduled — that's the design decision.
        assert JobExecution.objects.filter(parent_execution=root).count() == 0

    @responses.activate
    def test_success_records_to_breaker(self, django_capture_on_commit_callbacks):
        job = JobFactory(target_url="https://healthy.example.com/hook")
        responses.add(responses.POST, "https://healthy.example.com/hook", status=200)
        root = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)

        with django_capture_on_commit_callbacks(execute=False):
            execute_job_execution(root.id)

        cb = CircuitBreaker()
        assert cb.current_state("healthy.example.com") == CLOSED

    @responses.activate
    def test_failures_accumulate_toward_tripping(self, django_capture_on_commit_callbacks):
        job = JobFactory(
            target_url="https://flaky.example.com/hook",
            max_retries=0,  # no retries, so each execution is one failure
        )
        responses.add(responses.POST, "https://flaky.example.com/hook", status=500)

        cb = CircuitBreaker()
        # Run FAILURE_THRESHOLD separate executions; each records one failure.
        for _ in range(FAILURE_THRESHOLD):
            ex = JobExecutionFactory(job=job, attempt_number=1, parent_execution=None)
            with django_capture_on_commit_callbacks(execute=False):
                execute_job_execution(ex.id)

        assert cb.current_state("flaky.example.com") == OPEN


class TestHalfOpenRecovery:
    def test_half_open_after_cooldown(self, monkeypatch):
        """
        After cooldown elapses, allows_request should transition OPEN -> HALF_OPEN
        and permit exactly one probe.
        """
        cb = CircuitBreaker()
        d = "recovering.example.com"
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(d)
        assert cb.current_state(d) == OPEN

        # Simulate cooldown having elapsed by rewinding opened_at.
        keys = cb._keys(d)
        past = time.time() - (COOLDOWN_SECONDS + 1)
        cb.r.set(keys["opened_at"], str(past))

        allowed, state = cb.allows_request(d)
        assert state == HALF_OPEN
        assert allowed is True  # first probe granted

        # A second concurrent probe should be blocked (single-probe guarantee).
        allowed2, state2 = cb.allows_request(d)
        assert allowed2 is False

    def test_half_open_probe_success_closes(self):
        cb = CircuitBreaker()
        d = "healed.example.com"
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(d)
        keys = cb._keys(d)
        cb.r.set(keys["opened_at"], str(time.time() - (COOLDOWN_SECONDS + 1)))
        cb.allows_request(d)  # -> half-open, probe granted

        cb.record_success(d)  # probe succeeded
        assert cb.current_state(d) == CLOSED

    def test_half_open_probe_failure_reopens(self):
        cb = CircuitBreaker()
        d = "stillbroken.example.com"
        for _ in range(FAILURE_THRESHOLD):
            cb.record_failure(d)
        keys = cb._keys(d)
        cb.r.set(keys["opened_at"], str(time.time() - (COOLDOWN_SECONDS + 1)))
        cb.allows_request(d)  # -> half-open, probe granted

        cb.record_failure(d)  # probe failed
        assert cb.current_state(d) == OPEN
