import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chronoq.settings.dev")

app = Celery("chronoq")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Beat schedule defined in code, not in the DB. Survives `docker compose down -v`
# because it's app config, not stored data. The scheduler tick runs every 30s.
app.conf.beat_schedule = {
    "scheduler-tick": {
        "task": "jobs.tick",
        "schedule": 30.0,  # seconds
    },
    # Daily execution-history retention purge. Leadership-gated in the task, so
    # in a multi-node deployment only one node actually purges. 03:17 UTC is an
    # off-peak, non-round minute (avoids bunching with other :00 cron jobs).
    "retention-purge": {
        "task": "jobs.purge_executions",
        "schedule": crontab(hour=3, minute=17),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
