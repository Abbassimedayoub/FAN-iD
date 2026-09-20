"""
Identity model migration.

The initial identity migration remains immutable, so all new schema changes are
introduced here as a forward migration.

NOT NULL columns are added with a temporary default that is removed immediately
through `preserve_default=False`. This is the standard Django pattern for
adding required columns to a table that may already contain rows.

The age constraint uses `RunSQL` because the expression based on
`created_at AT TIME ZONE 'UTC'` is not representable accurately with `Q()`.
The SQL is explicit and reversible.
"""
import datetime
import uuid

import django.contrib.auth.validators
import django.utils.timezone
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models

import apps.identity.fields

# `AT TIME ZONE` with a literal zone is deterministic, unlike a direct
# `timestamptz::date` cast that depends on the session timezone. The expression
# checks age at account creation rather than age at the current date.
ADD_AGE_CONSTRAINT = """
ALTER TABLE identity_user ADD CONSTRAINT ck_user_min_age_16
CHECK (date_of_birth <= ((created_at AT TIME ZONE 'UTC') - INTERVAL '16 years')::date);
"""
DROP_AGE_CONSTRAINT = "ALTER TABLE identity_user DROP CONSTRAINT IF EXISTS ck_user_min_age_16;"


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        CreateExtension("citext"),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=20, unique=True)),
                ("permissions", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "identity_role"},
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.CheckConstraint(
                condition=models.Q(name__in=["FAN", "ORGANIZER", "SCANNER", "ADMIN"]),
                name="ck_role_name_valid",
            ),
        ),
        # --- Shared structural fields from TimeStampedModel / VersionedModel ---
        migrations.AddField(
            model_name="user",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="user",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        # --- Personal and compliance fields ---
        migrations.AddField(
            model_name="user",
            name="date_of_birth",
            field=models.DateField(default=datetime.date(1970, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="terms_accepted_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="anonymized_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # --- Canonical identity ---
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                blank=True,
                help_text="Hérité d'AbstractUser, neutralisé : l'identifiant de connexion est l'email.",
                max_length=150,
                null=True,
                validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=apps.identity.fields.CITextEmailField(max_length=254, unique=True),
        ),
        migrations.RunSQL(sql=ADD_AGE_CONSTRAINT, reverse_sql=DROP_AGE_CONSTRAINT),
    ]
