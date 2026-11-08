"""
Manually purge old JobExecution rows (same logic the daily beat task runs).

Examples:
    python manage.py purge_executions
    python manage.py purge_executions --days 30
    python manage.py purge_executions --days 7 --batch-size 500
"""

from django.core.management.base import BaseCommand

from jobs.services import purge_old_executions


class Command(BaseCommand):
    help = "Delete JobExecution rows older than the retention window (batched)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override EXECUTION_RETENTION_DAYS (0 disables).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Override EXECUTION_PURGE_BATCH_SIZE.",
        )

    def handle(self, *args, **options):
        deleted = purge_old_executions(
            older_than_days=options["days"],
            batch_size=options["batch_size"],
        )
        self.stdout.write(self.style.SUCCESS(f"Purged {deleted} execution(s)."))
