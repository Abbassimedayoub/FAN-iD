"""
Outbox concurrency tests: rolled-back transactions publish nothing, concurrent
relays do not duplicate work, and repeated failures eventually mark events DEAD.

These tests require real PostgreSQL for SKIP LOCKED and database constraints.
"""

import threading
import uuid

import pytest
from django.db import IntegrityError, connections, transaction

from apps.core.outbox import relay
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import ConsumedEvent, OutboxEvent
from apps.core.outbox.publisher import publish_event


class _RecordingConsumer(BaseConsumer):
    name = "test.recording_consumer"
    handled_event_types = {"test.event"}

    def __init__(self):
        self.handled: list = []

    def handle(self, event):
        self.handled.append(event.id)


class _AlwaysFailingConsumer(BaseConsumer):
    name = "test.always_failing_consumer"
    handled_event_types = {"test.poison"}

    def handle(self, event):
        raise RuntimeError("simulated permanent failure")


@pytest.mark.django_db(transaction=True)
def test_publish_event_requires_active_transaction():
    with pytest.raises(AssertionError):
        publish_event(
            event_type="test.event",
            aggregate_type="test_aggregate",
            aggregate_id=uuid.uuid4(),
            payload={},
        )


@pytest.mark.django_db
def test_rolled_back_transaction_publishes_no_event():
    """An event must never persist when the surrounding business transaction rolls back."""
    aggregate_id = uuid.uuid4()

    class _DeliberateRollback(Exception):
        pass

    with pytest.raises(_DeliberateRollback):
        with transaction.atomic():
            publish_event(
                event_type="test.event",
                aggregate_type="test_aggregate",
                aggregate_id=aggregate_id,
                payload={"x": 1},
            )
            raise _DeliberateRollback("simule un échec métier après l'écriture de l'événement")

    assert not OutboxEvent.objects.filter(aggregate_id=aggregate_id).exists()


@pytest.mark.django_db
def test_committed_transaction_publishes_event():
    aggregate_id = uuid.uuid4()
    with transaction.atomic():
        publish_event(
            event_type="test.event",
            aggregate_type="test_aggregate",
            aggregate_id=aggregate_id,
            payload={"x": 1},
        )
    assert OutboxEvent.objects.filter(aggregate_id=aggregate_id, status=OutboxEvent.Status.PENDING).exists()


@pytest.mark.django_db
def test_relay_dispatches_pending_event_to_matching_consumer():
    consumer = _RecordingConsumer()
    relay._CONSUMER_REGISTRY.clear()
    relay.register_consumer(consumer)
    try:
        with transaction.atomic():
            event = publish_event(
                event_type="test.event",
                aggregate_type="test_aggregate",
                aggregate_id=uuid.uuid4(),
                payload={},
            )
        result = relay.relay_batch(batch_size=10)

        assert result.published == 1
        event.refresh_from_db()
        assert event.status == OutboxEvent.Status.PUBLISHED
        assert event.id in consumer.handled
        assert ConsumedEvent.objects.filter(consumer_name=consumer.name, event_id=event.id).exists()
    finally:
        relay._CONSUMER_REGISTRY.clear()


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_relays_never_process_same_event_twice():
    """SKIP LOCKED ensures concurrent relays never process the same event twice."""
    consumer = _RecordingConsumer()
    relay._CONSUMER_REGISTRY.clear()
    relay.register_consumer(consumer)

    event_ids = []
    with transaction.atomic():
        for _ in range(10):
            event = publish_event(
                event_type="test.event",
                aggregate_type="test_aggregate",
                aggregate_id=uuid.uuid4(),
                payload={},
            )
            event_ids.append(event.id)

    results = []
    lock = threading.Lock()

    def worker():
        connections.close_all()
        try:
            result = relay.relay_batch(batch_size=10)
            with lock:
                results.append(result.published)
        finally:
            connections.close_all()

    try:
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 10  # all processed exactly once
        published_events = OutboxEvent.objects.filter(id__in=event_ids, status=OutboxEvent.Status.PUBLISHED)
        assert published_events.count() == 10
        # No duplicate consumption: consumed_event remains one-to-one with events.
        assert ConsumedEvent.objects.filter(event_id__in=event_ids).count() == 10
    finally:
        relay._CONSUMER_REGISTRY.clear()


@pytest.mark.django_db
def test_event_failing_five_times_becomes_dead(settings):
    settings.OUTBOX_MAX_ATTEMPTS = 5
    consumer = _AlwaysFailingConsumer()
    relay._CONSUMER_REGISTRY.clear()
    relay.register_consumer(consumer)
    try:
        with transaction.atomic():
            event = publish_event(
                event_type="test.poison",
                aggregate_type="test_aggregate",
                aggregate_id=uuid.uuid4(),
                payload={},
            )

        for attempt in range(1, 6):
            # Backoff moves available_at into the future; reset it between attempts to
            # simulate time passing.
            OutboxEvent.objects.filter(pk=event.pk).update(available_at=relay.timezone.now())
            relay.relay_batch(batch_size=10)
            event.refresh_from_db()
            if attempt < 5:
                assert event.status == OutboxEvent.Status.FAILED
                assert event.attempts == attempt

        assert event.status == OutboxEvent.Status.DEAD
        assert event.attempts == 5
    finally:
        relay._CONSUMER_REGISTRY.clear()


@pytest.mark.django_db
def test_consumed_event_primary_key_deduplicates():
    """The composite (consumer_name, event_id) constraint is the deduplication key."""
    event_id = uuid.uuid4()
    ConsumedEvent.objects.create(consumer_name="c1", event_id=event_id)

    with pytest.raises(IntegrityError):
        ConsumedEvent.objects.create(consumer_name="c1", event_id=event_id)


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_relays_one_event_is_processed_exactly_once():
    """Strict SKIP LOCKED proof: one pending event plus two relays yields one processing."""
    consumer = _RecordingConsumer()
    relay._CONSUMER_REGISTRY.clear()
    relay.register_consumer(consumer)

    with transaction.atomic():
        event = publish_event(
            event_type="test.event",
            aggregate_type="test_aggregate",
            aggregate_id=uuid.uuid4(),
            payload={"test": "single-event-concurrency"},
        )

    barrier = threading.Barrier(2)
    results = []
    results_lock = threading.Lock()

    def worker():
        connections.close_all()
        try:
            # Force both relays to start competing at the same time.
            barrier.wait()

            result = relay.relay_batch(batch_size=1)

            with results_lock:
                results.append(result.published)
        finally:
            connections.close_all()

    try:
        threads = [
            threading.Thread(target=worker),
            threading.Thread(target=worker),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        event.refresh_from_db()

        # Exactly one relay must publish the event.
        assert sorted(results) == [0, 1], results
        assert event.status == OutboxEvent.Status.PUBLISHED

        # Exactly one consumer execution.
        assert consumer.handled.count(event.id) == 1

        # Exactly one consumption record.
        assert (
            ConsumedEvent.objects.filter(
                consumer_name=consumer.name,
                event_id=event.id,
            ).count()
            == 1
        )

    finally:
        relay._CONSUMER_REGISTRY.clear()


@pytest.mark.django_db
def test_same_event_can_be_consumed_independently_by_two_consumers():
    event_id = uuid.uuid4()

    ConsumedEvent.objects.create(
        consumer_name="consumer-a",
        event_id=event_id,
    )

    ConsumedEvent.objects.create(
        consumer_name="consumer-b",
        event_id=event_id,
    )

    assert (
        ConsumedEvent.objects.filter(
            event_id=event_id,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_dead_event_updates_fanid_outbox_dead_metric(settings):
    settings.OUTBOX_MAX_ATTEMPTS = 1

    consumer = _AlwaysFailingConsumer()
    relay._CONSUMER_REGISTRY.clear()
    relay.register_consumer(consumer)

    try:
        with transaction.atomic():
            event = publish_event(
                event_type="test.poison",
                aggregate_type="test_aggregate",
                aggregate_id=uuid.uuid4(),
                payload={},
            )

        relay.relay_batch(batch_size=10)

        event.refresh_from_db()

        assert event.status == OutboxEvent.Status.DEAD
        assert event.attempts == 1

        assert relay.fanid_outbox_dead._value.get() >= 1

    finally:
        relay._CONSUMER_REGISTRY.clear()
