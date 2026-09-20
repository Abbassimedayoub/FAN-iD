"""
Migration `0001_infrastructure` creates only the three infrastructure tables:
`idempotency_record`, `outbox_event`, and `consumed_event`. It creates no
business tables.

The migration is handwritten. The `outbox_event_sequence_seq` sequence is
created with raw SQL and attached as the DEFAULT for `sequence` because Django
allows only one AutoField per model and the primary key is already a UUID.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=64)),
                ("endpoint", models.CharField(max_length=120)),
                ("request_hash", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("IN_PROGRESS", "En cours"),
                            ("COMPLETED", "Terminé"),
                            ("FAILED", "Échoué"),
                        ],
                        default="IN_PROGRESS",
                        max_length=16,
                    ),
                ),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("response_headers", models.JSONField(blank=True, default=dict, null=True)),
                ("locked_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="idempotency_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "idempotency_record"},
        ),
        migrations.CreateModel(
            name="OutboxEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=64)),
                ("event_version", models.PositiveSmallIntegerField(default=1)),
                ("aggregate_type", models.CharField(max_length=40)),
                ("aggregate_id", models.UUIDField()),
                ("sequence", models.BigIntegerField(editable=False, unique=True)),
                ("payload", models.JSONField()),
                ("correlation_id", models.CharField(blank=True, max_length=40, null=True)),
                ("causation_id", models.UUIDField(blank=True, null=True)),
                ("actor_id", models.UUIDField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "En attente"),
                            ("PUBLISHED", "Publié"),
                            ("FAILED", "Échoué (sera retenté)"),
                            ("DEAD", "Mort (abandonné après 5 tentatives)"),
                        ],
                        default="PENDING",
                        max_length=12,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("available_at", models.DateTimeField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
                ("occurred_at", models.DateTimeField()),
            ],
            options={"db_table": "outbox_event"},
        ),
        migrations.CreateModel(
            name="ConsumedEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("consumer_name", models.CharField(max_length=80)),
                ("event_id", models.UUIDField()),
                ("consumed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "consumed_event"},
        ),
        # Real PostgreSQL sequence for outbox_event.sequence.
        migrations.RunSQL(
            sql=[
                "CREATE SEQUENCE outbox_event_sequence_seq OWNED BY outbox_event.sequence;",
                "ALTER TABLE outbox_event ALTER COLUMN sequence SET DEFAULT nextval('outbox_event_sequence_seq');",
                "SELECT setval('outbox_event_sequence_seq', 1, false);",
            ],
            reverse_sql=[
                "ALTER TABLE outbox_event ALTER COLUMN sequence DROP DEFAULT;",
                "DROP SEQUENCE IF EXISTS outbox_event_sequence_seq;",
            ],
        ),
        # Explicit CHECK constraints and indexes.
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(fields=("key", "user"), name="uq_idempotency_key_user"),
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["IN_PROGRESS", "COMPLETED", "FAILED"]),
                name="ck_idempotency_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="idempotencyrecord",
            index=models.Index(fields=["expires_at"], name="ix_idempotency_expires_at"),
        ),
        migrations.AddConstraint(
            model_name="outboxevent",
            constraint=models.CheckConstraint(check=models.Q(attempts__gte=0), name="ck_outbox_attempts_nonneg"),
        ),
        migrations.AddConstraint(
            model_name="outboxevent",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["PENDING", "PUBLISHED", "FAILED", "DEAD"]),
                name="ck_outbox_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="outboxevent",
            index=models.Index(
                fields=["status", "available_at"],
                name="ix_outbox_relay_queue",
                condition=models.Q(status__in=["PENDING", "FAILED"]),
            ),
        ),
        migrations.AddIndex(
            model_name="outboxevent",
            index=models.Index(
                fields=["aggregate_type", "aggregate_id", "sequence"], name="ix_outbox_aggregate_order"
            ),
        ),
        migrations.AddIndex(
            model_name="outboxevent",
            index=models.Index(fields=["status"], name="ix_outbox_dead", condition=models.Q(status="DEAD")),
        ),
        migrations.AddConstraint(
            model_name="consumedevent",
            constraint=models.UniqueConstraint(fields=("consumer_name", "event_id"), name="pk_consumed_event"),
        ),
        migrations.AddIndex(
            model_name="consumedevent",
            index=models.Index(fields=["consumed_at"], name="ix_consumed_event_purge"),
        ),
    ]
