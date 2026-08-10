from abc import ABC, abstractmethod
from typing import Iterable


class EventPublisher(ABC):
    """
    Port de publication d'événements (§2.3 Source B, ADR-S-03).

    Implémentations prévues : `InProcessPublisher` (V1 — relais Celery vers
    consommateurs in-process), `SqsPublisher` (V2, bascule de configuration
    sans refonte), `RecordingPublisher` (tests — capture les événements publiés
    pour assertion, n'appelle jamais de service réseau réel).
    """

    @abstractmethod
    def publish(self, event: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish_batch(self, events: Iterable[dict]) -> None:
        raise NotImplementedError
