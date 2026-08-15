"""
Test factories for jobs. factory_boy generates model instances with
sensible defaults so individual tests only specify what they care about.
"""

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from jobs.models import Job, JobExecution

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Job {n}")
    target_url = "https://example.com/webhook"
    http_method = Job.HTTPMethod.POST
    schedule_cron = "*/5 * * * *"
    timeout_seconds = 30
    max_retries = 3
    retry_backoff_seconds = 60
    is_active = True


class JobExecutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobExecution

    job = factory.SubFactory(JobFactory)
    status = JobExecution.Status.PENDING
    scheduled_for = factory.LazyFunction(timezone.now)
