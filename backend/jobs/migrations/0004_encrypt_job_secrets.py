from django.db import migrations

import jobs.fields


class Migration(migrations.Migration):
    """
    Switch Job.headers / Job.body to encrypted fields.

    SeparateDatabaseAndState: the STATE side records the field-class change so
    Django's model state matches; the DATABASE side changes only the headers
    column type (jsonb -> text) with a safe USING cast. body is already text, so
    it needs no DB change. Existing plaintext rows stay readable (the fields
    decrypt-or-passthrough); run `manage.py encrypt_secrets` to re-encrypt them.
    """

    dependencies = [
        ("jobs", "0003_jobexecution_exec_created_idx"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="job",
                    name="headers",
                    field=jobs.fields.EncryptedJSONField(blank=True, default=dict),
                ),
                migrations.AlterField(
                    model_name="job",
                    name="body",
                    field=jobs.fields.EncryptedTextField(blank=True, default=""),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE jobs_job ALTER COLUMN headers TYPE text USING headers::text;",
                    # Reverse only works before any encrypted (non-JSON) data exists.
                    reverse_sql="ALTER TABLE jobs_job ALTER COLUMN headers TYPE jsonb USING headers::jsonb;",
                ),
            ],
        ),
    ]