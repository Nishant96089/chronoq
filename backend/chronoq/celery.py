import os

from celery import Celery

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
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
