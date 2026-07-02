"""
Django admin registration.

Not the final user-facing UI — that's the React dashboard we build later.
But invaluable for early dev: create test jobs, inspect executions, debug state.
"""

from django.contrib import admin

from .models import Job, JobExecution


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "schedule_cron",
        "next_fire_at",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "http_method", "created_at")
    search_fields = ("name", "target_url", "public_id")
    readonly_fields = ("public_id", "next_fire_at", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("public_id", "owner", "name", "is_active")}),
        (
            "Target",
            {
                "fields": (
                    "target_url",
                    "http_method",
                    "headers",
                    "body",
                    "timeout_seconds",
                )
            },
        ),
        ("Schedule", {"fields": ("schedule_cron", "next_fire_at")}),
        ("Retry policy", {"fields": ("max_retries", "retry_backoff_seconds")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(JobExecution)
class JobExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "scheduled_for",
        "status",
        "attempt_number",
        "http_status_code",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "scheduled_for")
    search_fields = ("job__name", "public_id", "error_message")
    readonly_fields = (
        "public_id",
        "job",
        "scheduled_for",
        "started_at",
        "finished_at",
        "attempt_number",
        "parent_execution",
        "http_status_code",
        "response_body_snippet",
        "error_message",
        "created_at",
    )

    def has_add_permission(self, request):
        # Executions are created by the scheduler, not by humans in admin.
        return False
