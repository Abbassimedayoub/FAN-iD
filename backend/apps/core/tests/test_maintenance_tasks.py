import importlib
import json
import sys
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.core.apps import CoreConfig
from apps.core.idempotency import service as idempotency_service
from apps.core.idempotency.models import IdempotencyRecord
from apps.core.idempotency.tasks import purge_expired_idempotency_records
from apps.core.outbox.models import OutboxEvent
from apps.core.outbox.tasks import purge_published_events, relay_outbox_batch


def _core_config() -> CoreConfig:
    return CoreConfig(
        "apps.core",
        importlib.import_module("apps.core"),
    )


def test_outbox_relay_task_uses_configured_batch_size_and_logs(settings):
    settings.OUTBOX_RELAY_BATCH_SIZE = 37
    result = SimpleNamespace(published=2, failed=1, dead=1)

    with (
        patch(
            "apps.core.outbox.tasks.relay.relay_batch",
            return_value=result,
        ) as relay_batch,
        patch("apps.core.outbox.tasks.logger.info") as logger_info,
    ):
        payload = relay_outbox_batch.run()

    relay_batch.assert_called_once_with(batch_size=37)
    logger_info.assert_called_once_with(
        "outbox_relay_tick",
        extra={"published": 2, "failed": 1, "dead": 1},
    )
    assert payload == {"published": 2, "failed": 1, "dead": 1}


def test_outbox_purge_task_uses_retention_cutoff_and_logs(settings):
    settings.OUTBOX_RETENTION_DAYS = 14
    now = timezone.now()

    queryset = MagicMock()
    queryset.delete.return_value = (3, {"core.OutboxEvent": 3})

    with (
        patch("django.utils.timezone.now", return_value=now),
        patch.object(
            OutboxEvent.objects,
            "filter",
            return_value=queryset,
        ) as filter_mock,
        patch("apps.core.outbox.tasks.logger.info") as logger_info,
    ):
        deleted = purge_published_events.run()

    filter_mock.assert_called_once_with(
        status=OutboxEvent.Status.PUBLISHED,
        published_at__lt=now - timedelta(days=14),
    )
    queryset.delete.assert_called_once_with()
    logger_info.assert_called_once_with(
        "outbox_purge_completed",
        extra={"deleted_count": 3},
    )
    assert deleted == 3


def test_idempotency_purge_task_delegates_and_logs():
    with (
        patch(
            "apps.core.idempotency.tasks.service.purge_expired",
            return_value=4,
        ) as purge_expired,
        patch(
            "apps.core.idempotency.tasks.logger.info",
        ) as logger_info,
    ):
        deleted = purge_expired_idempotency_records.run()

    purge_expired.assert_called_once_with()
    logger_info.assert_called_once_with(
        "idempotency_purge_completed",
        extra={"deleted_count": 4},
    )
    assert deleted == 4


@pytest.mark.django_db
def test_failed_idempotency_record_can_be_retried(user):
    first = idempotency_service.begin(
        key="maintenance-failed-retry",
        user_id=user.pk,
        endpoint="/api/v1/test-maintenance",
        request_hash="hash-before-failure",
    )

    idempotency_service.fail(first.record)

    first.record.refresh_from_db()
    assert first.record.status == IdempotencyRecord.Status.FAILED

    retry = idempotency_service.begin(
        key="maintenance-failed-retry",
        user_id=user.pk,
        endpoint="/api/v1/test-maintenance",
        request_hash="hash-after-failure",
    )

    retry.record.refresh_from_db()

    assert retry.replayed is False
    assert retry.record.status == IdempotencyRecord.Status.IN_PROGRESS
    assert retry.record.request_hash == "hash-after-failure"


@pytest.mark.django_db
def test_purge_expired_idempotency_records_keeps_active_records(user):
    expired = idempotency_service.begin(
        key="maintenance-expired",
        user_id=user.pk,
        endpoint="/api/v1/test-maintenance",
        request_hash="expired",
    ).record

    active = idempotency_service.begin(
        key="maintenance-active",
        user_id=user.pk,
        endpoint="/api/v1/test-maintenance",
        request_hash="active",
    ).record

    IdempotencyRecord.objects.filter(pk=expired.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    deleted = idempotency_service.purge_expired()

    assert deleted == 1
    assert not IdempotencyRecord.objects.filter(pk=expired.pk).exists()
    assert IdempotencyRecord.objects.filter(pk=active.pk).exists()


def test_serialize_response_body_handles_non_json_native_values():
    identifier = uuid.UUID("12345678-1234-5678-1234-567812345678")

    payload = idempotency_service.serialize_response_body(
        {"identifier": identifier},
    )

    assert json.loads(payload) == {"identifier": str(identifier)}


def test_core_config_skips_tracing_for_management_commands(settings):
    settings.OTEL_ENABLED = True

    with (
        patch.object(sys, "argv", ["manage.py", "migrate"]),
        patch(
            "apps.core.observability.tracing.bootstrap_tracing",
        ) as bootstrap_tracing,
    ):
        _core_config().ready()

    bootstrap_tracing.assert_not_called()


def test_core_config_bootstraps_tracing_when_enabled(settings):
    settings.OTEL_ENABLED = True

    with (
        patch.object(sys, "argv", ["pytest"]),
        patch(
            "apps.core.observability.tracing.bootstrap_tracing",
        ) as bootstrap_tracing,
    ):
        _core_config().ready()

    bootstrap_tracing.assert_called_once_with()
