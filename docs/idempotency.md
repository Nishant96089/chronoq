# Idempotency & delivery guarantees

chronoq guarantees **at-least-once delivery**: your endpoint will be called for
every scheduled execution, even if a worker crashes mid-flight. The tradeoff of
at-least-once is that, in rare failure scenarios, your endpoint may receive the
**same request more than once**. This document explains how to handle that
safely.

## Why duplicates can happen

- **Redelivery** — if a worker crashes after starting a request but before
  acknowledging completion, the task is redelivered and the request is retried.
  This is the *same logical attempt* happening twice.
- **Retries** — if a request genuinely fails (5xx, timeout, connection error),
  chronoq retries it with exponential backoff. Each retry is a *new attempt*.

## Headers chronoq sends

Every request includes:

| Header | Meaning | Stable across… |
|--------|---------|----------------|
| `X-Job-Execution-Id` | **Idempotency key.** Unique per execution attempt. | Redeliveries of the same attempt (same value). |
| `X-Job-Id` | Which job this execution belongs to. | All executions of a job. |
| `X-Job-Attempt` | Attempt number (1 = original, 2+ = retries). | — (increments per retry). |

## How to dedupe (recommended)

Use `X-Job-Execution-Id` as an idempotency key:

1. On receiving a request, read `X-Job-Execution-Id`.
2. Check whether you've already successfully processed that ID.
3. If yes → return success without re-doing the work (it's a duplicate).
4. If no → process it, then record the ID as processed.

    # Pseudocode
    execution_id = request.headers["X-Job-Execution-Id"]
    if already_processed(execution_id):
        return 200  # duplicate — already handled
    do_the_work()
    mark_processed(execution_id)
    return 200

This is the same pattern used by Stripe (`Idempotency-Key`) and other webhook
providers.

## Key semantics: redelivery vs. retry

- **Redelivery** carries the **same** `X-Job-Execution-Id` → your dedupe check
  catches it → you skip the duplicate. ✅
- **Retry** carries a **different** `X-Job-Execution-Id` (it's a new attempt) →
  your dedupe check does *not* match → you process it. ✅ This is correct: the
  previous attempt failed, so the retry *should* be processed.

In other words: dedupe on `X-Job-Execution-Id` and you automatically do the
right thing — ignore accidental duplicates, honor legitimate retries.

## What chronoq guarantees vs. what you must do

- **chronoq guarantees:** a stable, unique key per attempt; the same key on
  redelivery; a distinct key per retry.
- **You must:** dedupe on that key if your endpoint's actions are not naturally
  idempotent (e.g. charging a card, sending an email). If your endpoint is
  already idempotent (e.g. "set status = done"), you may not need to.