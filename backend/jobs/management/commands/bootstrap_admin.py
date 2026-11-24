"""
First-run admin bootstrap.

Creates an initial superuser from DJANGO_SUPERUSER_* environment variables,
but ONLY when there are no users yet. This is the standard self-hosted
first-run pattern (cf. Grafana, GitLab, n8n): a fresh `clone && docker compose
up` lands on a usable login with no manual step, while any existing deployment
is never touched — the empty-table gate makes it a true one-time seed.

Distinct from ensure_superuser (dev convenience, keyed on a specific username):
this is keyed on "the system has no users at all", which is the right
condition for an initial bootstrap.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed an initial superuser from DJANGO_SUPERUSER_* if no users exist."

    def handle(self, *args, **options):
        User = get_user_model()  # noqa: N806

        if User.objects.exists():
            self.stdout.write("Users already exist; bootstrap skipped.")
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "No users yet, but DJANGO_SUPERUSER_USERNAME/PASSWORD are "
                    "unset — skipping bootstrap. Create an admin manually or set "
                    "those vars and redeploy."
                )
            )
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Bootstrapped initial admin '{username}'."))
