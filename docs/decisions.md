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
## 2026-08-13 — Move beat schedule from DB to code (drop DatabaseScheduler)

**Problem:** Two failures compounding:
1. `docker compose down -v` wiped the django_celery_beat periodic task,
   so beat had nothing to dispatch.
2. celery-beat with DatabaseScheduler crashed on boot with
   "column ...clocked_id does not exist" — a race where beat queried
   the periodic-task table before migrations finished applying.

**Choice:** Define the beat schedule in code via app.conf.beat_schedule
and use Celery's default PersistentScheduler (dropped
--scheduler django_celery_beat.schedulers:DatabaseScheduler).

**Reasoning:**
- Our beat schedule is a single fixed entry (tick every 30s). We never
  need to add/edit schedules at runtime via the admin.
- Individual JOB schedules live in our own Job model + tick logic, not
  in django_celery_beat. DatabaseScheduler was always overkill.
- Code-based schedule survives DB wipes and has no migration-order race.

**Trade-off:** Lose runtime schedule editing via Django admin. Acceptable —
we don't use it. django_celery_beat stays in INSTALLED_APPS for now
(harmless); can remove in a later cleanup pass.

## 2026-08-13 — Frontend architecture (Phase 1 Step 4)

**Stack:** React 19 + Vite, Tailwind CSS v4 (via @tailwindcss/vite plugin),
React Query (TanStack) for data fetching, React Router v7, axios.

**Auth: token-based, not session/cookies.**
- POST /api/auth/token/ returns a DRF token; stored in localStorage.
- axios request interceptor attaches `Authorization: Token <t>` to every call.
- Response interceptor clears token + redirects to /login on 401.
- Chose token over session cookies to avoid the CORS+CSRF cookie dance and
  match how production SPAs work. SessionAuth kept server-side only for the
  browsable API.

**Data layer: React Query, all API calls centralized.**
- api/{client,auth,jobs}.js own HTTP; hooks/useJobs.js owns query/mutation
  logic + cache invalidation. Components never call axios directly.
- Query keys centralized (jobKeys) so invalidation is predictable.

**Live execution updates: 5s polling via refetchInterval — for now.**
- Deliberately NOT WebSockets in Phase 1. Polling is simple and adequate
  for a single-user dashboard. Real-time via Django Channels is planned for
  Phase 3, where the same WS infrastructure also serves the distributed
  layer. Avoided adding ASGI/Channels/channel-layer complexity to a phase
  meant to stay single-node-simple.

**Custom modals over browser-native dialogs.**
- window.confirm replaced with a styled ConfirmDialog (Modal + backdrop +
  Escape/backdrop-close). Kept HTML native `required` validation — it's
  accessible and expected, not an intrusive popup.

## 2026-08-15 — Testing: on_commit + save() recompute gotchas

Two test-only subtleties (production code is correct, tests must adapt):
- tick() dispatches via transaction.on_commit, which never fires under
  pytest-django's rolled-back transactions. Use the
  django_capture_on_commit_callbacks fixture to let tick() complete.
- Job.save() recomputes next_fire_at from cron, overriding any value
  passed to the factory. Tests that need a specific next_fire_at set it
  via Job.objects.filter().update() to bypass save().
