"""
P1.C.1 — garantit qu'un effet de bord réseau planifié via `BaseConsumer.defer()`
ne s'exécute JAMAIS pendant que le relais tient ses verrous `SELECT FOR
UPDATE SKIP LOCKED`, seulement après le commit de `relay_batch()`.
"""
import uuid

import pytest
from django.db import transaction
from django.test import TransactionTestCase

from apps.core.outbox import relay
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.publisher import publish_event


class _DeferringConsumer(BaseConsumer):
    """Consumer de test qui planifie un effet de bord via defer() plutôt que de l'exécuter en direct."""

    name = "test.deferring_consumer"
    handled_event_types = {"test.deferrable_event"}

    def __init__(self):
        self.executed_during_handle = []
        self.deferred_calls = []

    def handle(self, event):
        # Preuve négative : rien n'est exécuté ici de synchrone/réseau.
        self.executed_during_handle.append(event.id)
        self.defer(lambda: self.deferred_calls.append(event.id))


class OutboxDeferredSideEffectTests(TransactionTestCase):
    """
    TransactionTestCase (pas TestCase) : nécessaire pour que les callbacks
    `transaction.on_commit()` s'exécutent réellement — TestCase enveloppe
    chaque test dans une transaction jamais commitée, ce qui empêcherait
    d'observer la différence entre "avant commit" et "après commit".
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

            # relay_batch() est lui-même @transaction.atomic — au retour de
            # l'appel, sa transaction a déjà committé, donc le callback
            # différé a déjà pu s'exécuter.
            result = relay.relay_batch(batch_size=10)

            assert result.published == 1
            assert event.id in consumer.executed_during_handle
            assert event.id in consumer.deferred_calls, (
                "le callback différé n'a jamais été exécuté après le commit du relais"
            )
        finally:
            relay._CONSUMER_REGISTRY.clear()

    def test_deferred_callback_does_not_run_if_relay_transaction_rolls_back(self):
        """
        Si la transaction du relais échoue AVANT son commit, le callback
        différé ne doit jamais s'exécuter — cohérent avec la garantie
        transactionnelle de l'Outbox (aucun effet de bord sur un rollback).
        """
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
