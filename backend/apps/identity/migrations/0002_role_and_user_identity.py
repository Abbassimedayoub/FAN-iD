"""
Modèle d'identité du Sprint 1 (plan S1 §3.1).

`identity/0001_initial` est immuable (§6 du prompt d'exécution) : tout arrive
ici en migration avant.

Les colonnes NOT NULL sont ajoutées **avec une valeur par défaut immédiatement
retirée** (`preserve_default=False`). C'est l'idiome Django et l'exigence
d'ADR-S-08 : un `NOT NULL` sans défaut sur une table potentiellement peuplée
échoue. La valeur par défaut ne survit pas à la migration.

La contrainte d'âge est posée en `RunSQL` plutôt qu'en `Meta.constraints` :
l'expression `(created_at AT TIME ZONE 'UTC' - INTERVAL '16 years')::date` n'est
pas exprimable en `Q()`, et une traduction approchée serait pire qu'un SQL
explicite et relu. Réversible (ADR-S-08). Voir ADR-S1-01 pour la justification
complète et les vérifications sur PostgreSQL 16.
"""
import datetime
import uuid

import django.contrib.auth.validators
import django.utils.timezone
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models

import apps.identity.fields

# `AT TIME ZONE` avec une zone LITTÉRALE est immuable, contrairement à un cast
# `timestamptz::date` qui dépend du fuseau de session. L'expression ne référence
# que des colonnes de la ligne : elle est donc déterministe et vérifie « l'âge
# À L'INSCRIPTION », pas « l'âge aujourd'hui ».
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
        # --- Socle commun (TimeStampedModel / VersionedModel) ---
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
        # --- État civil et conformité ---
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
        # --- Identité canonique ---
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
