from abc import ABC, abstractmethod
from typing import Iterable


class EventPublisher(ABC):
    """
    Port de publication d'événements (§2.3 Source B, ADR-S-03).

    Implémentation Sprint 0 : `UnimplementedEventPublisher` (garde-fou
    explicite — voir `apps.core.adapters.events` pour la justification
    complète, correction post-bilan P2.2). La voie normale de publication
    au Sprint 0 est `apps.core.outbox.publisher.publish_event()`, appelé
    dans une transaction ; le relais dispatche ensuite en interne via
    `register_consumer()`, sans passer par ce port.

    Implémentations prévues : `SqsPublisher`/`KafkaPublisher` (V2, bascule de
    configuration sans refonte), `RecordingPublisher` (tests — capture les
    événements publiés pour assertion, n'appelle jamais de service réseau
    réel).
    """

    @abstractmethod
    def publish(self, event: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish_batch(self, events: Iterable[dict]) -> None:
        raise NotImplementedError
