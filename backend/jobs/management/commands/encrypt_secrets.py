"""
Re-save every Job so any plaintext headers/body is re-written as ciphertext.

Safe to run repeatedly (already-encrypted rows just get re-encrypted). Run once
after applying the encryption migration to backfill existing rows.
"""

from django.core.management.base import BaseCommand

from jobs.models import Job


class Command(BaseCommand):
    help = "Re-save all jobs to encrypt any plaintext headers/body at rest."

    def handle(self, *args, **options):
        n = 0
        for job in Job.objects.all():
            job.save(update_fields=["headers", "body"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {n} job(s)."))
