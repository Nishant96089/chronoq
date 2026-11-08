from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0002_job_alert_email_job_alert_webhook_url"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="jobexecution",
            index=models.Index(fields=["created_at"], name="exec_created_idx"),
        ),
    ]