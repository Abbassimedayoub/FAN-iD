"""
BaseConsumer — consommateurs idempotents (§22/§23 master prompt, ADR-S-03).

La livraison Outbox est *at-least-once* : chaque consommateur DOIT être
idempotent. La table `consumed_event` (PK composite `(consumer_name,
event_id)`) est le mécanisme de déduplication : l'insertion est tentée en
DÉBUT de traitement, une IntegrityError signifie "déjà traité".

RÈGLE ABSOLUE (§24 master prompt, audit P1.C.1) — `consume()` s'exécute à
l'intérieur de la transaction du relais (`relay.relay_batch()`), qui tient
les verrous `SELECT ... FOR UPDATE SKIP LOCKED` sur le lot d'événements en
cours de traitement. **`handle()` ne doit donc JAMAIS effectuer d'appel
réseau direct** (email, push, HTTP externe, `requests.post`, appel Stripe...)
— un appel lent ou bloquant y tiendrait les verrous de TOUT le lot ouvert
pendant la latence réseau, exactement le scénario que le master prompt
interdit explicitement ("un timeout Stripe de 10s à l'intérieur d'un SELECT
FOR UPDATE... bloque toute la vente de cette catégorie pendant 10
secondes" — même risque ici, appliqué au relais).

Tout effet de bord réseau DOIT passer par `self.defer(callback)`, qui
n'exécute `callback` qu'APRÈS que la transaction du relais ait committé et
donc APRÈS libération des verrous. `handle()` ne doit contenir que de
l'écriture DB (rapide, locale) et, le cas échéant, l'enregistrement d'un
callback différé :

    class NotifyOrderPaidConsumer(BaseConsumer):
        name = "notifying.order_paid_email"
        handled_event_types = {"order.paid"}

        def handle(self, event: OutboxEvent) -> None:
            order_id = event.aggregate_id
            # PAS d'appel réseau ici. On planifie une tâche Celery qui, elle,
            # peut appeler SES/SMTP sans tenir aucun verrou Outbox.
            self.defer(lambda: send_order_confirmation_email.delay(order_id=str(order_id)))
"""
import logging
from abc import ABC, abstractmethod
from typing import Callable

from django.db import IntegrityError, transaction

from .models import ConsumedEvent, OutboxEvent

logger = logging.getLogger("fanid.outbox")


class BaseConsumer(ABC):
    name: str  # nom stable, unique par consommateur — clé de `consumed_event`
    handled_event_types: set[str] = set()

    def handles(self, event_type: str) -> bool:
        return event_type in self.handled_event_types

    def consume(self, event: OutboxEvent) -> None:
        with transaction.atomic():
            try:
                ConsumedEvent.objects.create(consumer_name=self.name, event_id=event.id)
            except IntegrityError:
                logger.info(
                    "outbox_event_already_consumed",
                    extra={"consumer": self.name, "event_id": str(event.id)},
                )
                return
            self.handle(event)

    @staticmethod
    def defer(callback: Callable[[], None]) -> None:
        """
        Enregistre `callback` pour exécution APRÈS le commit de la
        transaction englobante (`transaction.on_commit`, sémantique Django :
        différé jusqu'au commit de la transaction ATOMIC LA PLUS EXTERNE,
        donc jusqu'à la fin de `relay.relay_batch()` — les verrous
        `SKIP LOCKED` du lot entier sont déjà libérés quand `callback`
        s'exécute). C'est l'UNIQUE mécanisme sanctionné pour tout effet de
        bord réseau déclenché par un consumer (§24 master prompt).
        """
        transaction.on_commit(callback)

    @abstractmethod
    def handle(self, event: OutboxEvent) -> None:
        """
        Traitement métier de l'événement — implémenté par chaque bounded
        context. DB uniquement (voir règle absolue ci-dessus) ; tout effet
        de bord réseau passe par `self.defer(...)`.
        """
        raise NotImplementedError
