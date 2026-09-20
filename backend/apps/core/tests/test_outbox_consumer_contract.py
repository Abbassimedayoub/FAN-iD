"""
Ensure deferred network side effects run only after the relay transaction commits, never while SKIP
LOCKED row locks are held.
"""

import uuid

import pytest
from django.db import transaction
from django.test import TransactionTestCase

from apps.core.outbox import relay
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.publisher import publish_event


class _DeferringConsumer(BaseConsumer):
    """Test consumer that schedules a side effect through defer() instead of executing it inline."""

    name = "test.deferring_consumer"
    handled_event_types = {"test.deferrable_event"}

    def __init__(self):
        self.executed_during_handle = []
        self.deferred_calls = []

    def handle(self, event):
        # Negative proof: no synchronous network side effect runs here.
        self.executed_during_handle.append(event.id)
        self.defer(lambda: self.deferred_calls.append(event.id))


class OutboxDeferredSideEffectTests(TransactionTestCase):
    """
    Use TransactionTestCase so transaction.on_commit callbacks actually execute and pre/post-commit
    behavior can be observed.
    """

    def test_deferred_callback_runs_only_after_relay_transaction_commits(self):
        consumer = _DeferringConsumer()
        relay._CONSUMER_REGISTRY.clear()
        relay.register_consumer(consumer)
        try:
            with transaction.atomic():
                event = publish_event(
                    event_type="test.deferrable_event",
                    aggregate_type="test_aggregate",
                    aggregate_id=uuid.uuid4(),
                    payload={},
                )

            # relay_batch() is atomic; when it returns, its transaction has committed and deferred
            # callbacks may have run.
            result = relay.relay_batch(batch_size=10)

            assert result.published == 1
            assert event.id in consumer.executed_during_handle
            assert (
                event.id in consumer.deferred_calls
            ), "le callback différé n'a jamais été exécuté après le commit du relais"
        finally:
            relay._CONSUMER_REGISTRY.clear()

    def test_deferred_callback_does_not_run_if_relay_transaction_rolls_back(self):
        """If the relay transaction rolls back before commit, the deferred callback must never execute."""
        consumer = _DeferringConsumer()
        relay._CONSUMER_REGISTRY.clear()
        relay.register_consumer(consumer)

        class _DeliberateFailure(Exception):
            pass

        try:
            with transaction.atomic():
                publish_event(
                    event_type="test.deferrable_event",
                    aggregate_type="test_aggregate",
                    aggregate_id=uuid.uuid4(),
                    payload={},
                )

            with pytest.raises(_DeliberateFailure):
                with transaction.atomic():
                    events = list(relay.OutboxEvent.objects.select_for_update(skip_locked=True))
                    for event in events:
                        relay._dispatch_to_consumers(event)
                    raise _DeliberateFailure("simule un échec après dispatch, avant commit")

            assert consumer.deferred_calls == [], "le callback différé s'est exécuté malgré un rollback"
        finally:
            relay._CONSUMER_REGISTRY.clear()
