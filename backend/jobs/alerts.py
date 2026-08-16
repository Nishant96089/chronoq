"""
Alerting for chronoq.

Fires notifications when a job fails permanently (retries exhausted) or when
a target domain's circuit trips. Two channels: email and webhook.

Design (see docs/decisions.md):
- Throttled per (job, condition): at most one alert per hour, via Redis, to
  avoid alert fatigue (industry standard — PagerDuty/Alertmanager all dedupe).
- Async: sending runs in a Celery task so it never blocks the executor, and a
  failing webhook can't break a job.
- Both channels attempted independently; one failing doesn't stop the other.
"""

import json
import logging

import redis
import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Throttle window: don't re-alert for the same (job, condition) within this many
# seconds. One hour is a sane industry default.
ALERT_THROTTLE_SECONDS = 3600

# Condition identifiers.
CONDITION_RETRIES_EXHAUSTED = "retries_exhausted"
CONDITION_CIRCUIT_OPEN = "circuit_open"


def _redis():
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def should_send(job_public_id: str, condition: str) -> bool:
    """
    Throttle check. Returns True if we should send (and marks it sent), False
    if an alert for this (job, condition) was already sent within the window.

    Uses SET NX with a TTL: the first caller sets the key and gets True;
    subsequent callers within the TTL see the key exists and get False.
    """
    r = _redis()
    key = f"alert:{job_public_id}:{condition}"
    # NX = only set if absent. Returns True if set (i.e. we're first).
    acquired = r.set(key, "1", nx=True, ex=ALERT_THROTTLE_SECONDS)
    return bool(acquired)


@shared_task(name="jobs.send_alert")
def send_alert(
    job_public_id: str,
    job_name: str,
    condition: str,
    detail: str,
    alert_email: str = "",
    alert_webhook_url: str = "",
) -> dict:
    """
    Send an alert via configured channels. Runs async.

    Called with the job's alert config passed in (not re-fetched) so the task
    is self-contained and testable.
    """
    subject = f"[chronoq] {job_name}: {condition}"
    body = (
        f"Job '{job_name}' ({job_public_id}) triggered an alert.\n\n"
        f"Condition: {condition}\n"
        f"Detail: {detail}\n"
    )

    results = {"email": None, "webhook": None}

    # --- Email ---
    if alert_email:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[alert_email],
                fail_silently=False,
            )
            results["email"] = "sent"
            logger.info("alert email sent job=%s to=%s", job_public_id, alert_email)
        except Exception as e:
            results["email"] = f"error: {e}"
            logger.exception("alert email failed job=%s", job_public_id)

    # --- Webhook ---
    if alert_webhook_url:
        payload = {
            "job_public_id": job_public_id,
            "job_name": job_name,
            "condition": condition,
            "detail": detail,
        }
        try:
            resp = requests.post(
                alert_webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            results["webhook"] = f"status {resp.status_code}"
            logger.info(
                "alert webhook sent job=%s url=%s status=%s",
                job_public_id,
                alert_webhook_url,
                resp.status_code,
            )
        except Exception as e:
            results["webhook"] = f"error: {e}"
            logger.exception("alert webhook failed job=%s", job_public_id)

    return results


def fire_alert(job, condition: str, detail: str) -> bool:
    """
    Entry point called from tasks. Applies throttling, then dispatches the
    async send_alert task if not throttled and the job has any alert channel.

    Returns True if an alert was dispatched, False if skipped (throttled or
    no channels configured).
    """
    if not job.alert_email and not job.alert_webhook_url:
        return False  # nothing to send to

    if not should_send(str(job.public_id), condition):
        logger.info("alert throttled job=%s condition=%s", job.public_id, condition)
        return False

    send_alert.delay(
        job_public_id=str(job.public_id),
        job_name=job.name,
        condition=condition,
        detail=detail,
        alert_email=job.alert_email,
        alert_webhook_url=job.alert_webhook_url,
    )
    return True
