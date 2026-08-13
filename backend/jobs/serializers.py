"""
DRF serializers for the Job and JobExecution models.

Design notes:
- We expose `public_id` (UUID) in URLs and API responses, never the internal
  BigAutoField `id`. This matches our hybrid PK strategy.
- Cron expressions are validated at the serializer layer (not just in the
  model's save()) so invalid input gets a clean 400 response.
- JobExecution is read-only via API. Executions are created by the scheduler,
  not by clients.
"""

from rest_framework import serializers

from .models import Job, JobExecution
from .services import validate_cron_expression


class JobSerializer(serializers.ModelSerializer):
    # `owner` is set from the request user, not sent by the client.
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Job
        fields = [
            "public_id",
            "owner",
            "name",
            "target_url",
            "http_method",
            "headers",
            "body",
            "timeout_seconds",
            "schedule_cron",
            "next_fire_at",
            "max_retries",
            "retry_backoff_seconds",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "public_id",
            "owner",
            "next_fire_at",
            "created_at",
            "updated_at",
        ]

    def validate_schedule_cron(self, value: str) -> str:
        """Reject invalid cron expressions with a clean 400."""
        try:
            validate_cron_expression(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e
        return value

    def validate_headers(self, value):
        """Headers must be a flat dict of string keys and string values."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Headers must be an object (dict).")
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError("All header keys and values must be strings.")
        return value


class JobExecutionSerializer(serializers.ModelSerializer):
    job = serializers.SlugRelatedField(slug_field="public_id", read_only=True)

    class Meta:
        model = JobExecution
        fields = [
            "public_id",
            "job",
            "status",
            "scheduled_for",
            "started_at",
            "finished_at",
            "attempt_number",
            "http_status_code",
            "response_body_snippet",
            "error_message",
            "created_at",
        ]
        # Entire model is read-only — clients never create/modify executions.
        read_only_fields = fields
