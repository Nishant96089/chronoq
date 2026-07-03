# Decisions Log

Format: one entry per significant technical decision. Include date, context,
options considered, choice, and reasoning.

---

## 2026-07-01 — Why I'm building this

**Context:** Learning project to internalize distributed systems patterns
(leader election, idempotency, circuit breakers, partitioning) that I've read
about but never implemented.

**Non-goals:** Enterprise scale, competing with Temporal, revenue.

**Success criteria:**
- End-to-end working system running under Docker Compose
- Load test proving system survives 10k jobs + random pod kills
- A written architecture doc I could defend in a senior backend interview

---

## 2026-07-01 — Monorepo over multi-repo

**Choice:** Monorepo (`/backend`, `/frontend`, `/infra`, `/docs`).

**Reasoning:** Solo project, atomic commits across boundaries are valuable.
Docker Compose orchestration is trivially co-located.

---

## 2026-07-01 — Django settings package over single file

**Choice:** `chronoq/settings/{base,dev,prod}.py` package.

**Reasoning:** Single `settings.py` blocks environment separation. Base holds
the shared config, dev adds debug toolbar, prod adds security hardening. Same
pattern used by cookiecutter-django and every serious Django project.

---

## 2026-07-01 — Postgres 16 + Redis 7 (both Alpine)

**Reasoning:** Alpine images are ~5x smaller than default. Postgres 16 is
current stable with native partitioning improvements we'll use in Phase 4.
Redis 7 for its improved stream/consumer group features we may use for the
job queue in Phase 3.

**Trade-off:** Alpine sometimes has quirks with musl vs glibc. Acceptable
here — no C extensions in our Postgres/Redis usage.

---

## 2026-07-01 — Separate Redis DBs for cache, broker, and results

**Choice:** DB 0 = cache, DB 1 = Celery broker, DB 2 = Celery results.

**Reasoning:** Redis supports 16 numbered DBs. Isolation makes `redis-cli -n 1`
show only broker keys — huge for debugging. Cost is zero.

---

## 2026-07-01 — Celery task_acks_late = True

**Reasoning:** By default Celery acknowledges a task before executing it. If
the worker crashes mid-execution, the task is lost. With `acks_late=True`,
the task is only acknowledged after successful execution. Combined with
idempotent task design (Phase 3), this is what gives us at-least-once
delivery. This is the same pattern SQS, RabbitMQ, and every serious queue
recommends.

**Trade-off:** Long-running tasks may be re-delivered if a worker dies —
tasks must be idempotent.

---

## 2026-07-01 — Bind mount vs image contents on WSL2

**Issue hit:** Bind-mounted scripts weren't executable inside the container
even though the Dockerfile ran `chmod +x`.

**Root cause:** Bind mounts override image contents with host contents at
runtime, including permissions. The image's chmod is ignored because the
runtime file comes from the host.

**Fix:** `chmod +x` the script on the host filesystem (WSL native
`/home/nishant/...`, not `/mnt/c/...`). Also keep the chmod in the Dockerfile
so production images (which don't use bind mounts) still work.

**Lesson:** Bind mounts are a "surprising in one direction" abstraction —
they change file source but keep image environment. Whenever a bind-mounted
file behaves differently in dev vs prod, look here first.

---

## 2026-07-03 — Scheduler design: on_commit, drift-free advancement, tick lookahead

**Choice:** Three design details worth writing down before I forget why.

**a) `transaction.on_commit(lambda: task.delay(...))`**
Dispatch Celery tasks AFTER the DB transaction commits, not inside it.
Otherwise a worker in another process could pick up the task ID before
the row is visible. Without this, tests pass locally but production
gets sporadic "DoesNotExist" errors under load.

**b) `next_fire_at = compute_next_fire_at(cron, after=scheduled_for)`**
Not `after=now`. Advance from the fire time we just consumed, not
wall-clock now. This prevents cron drift when the tick runs late.
A 6:00 AM job stays 6:00 AM, not 6:00:03 AM after the first fire.

**c) `TICK_LOOKAHEAD_SECONDS = 45`**
Wider than the 30s beat interval. Absorbs clock skew and tick jitter
so no fires slip through. Downside: a job's execution might start
up to 15s early. Acceptable tradeoff — being late is worse than
being slightly early in a scheduler.

**Learning:** Small design choices compound. Any one of these missing
would create bugs I'd chase for hours. Writing them down means I can
defend them in a senior interview when someone asks "why did you..."

---