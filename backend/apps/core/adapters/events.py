from typing import Iterable

from apps.core.interfaces import EventPublisher


class InProcessPublisher(EventPublisher):
    """
    V1 — ne PAS confondre avec un vrai bus : ce publisher se contente d'écrire
    dans la table `outbox_event` (fait par `OutboxPublisher`, pas ici). Ce port
    `EventPublisher` est le point d'extension pour un futur `SqsPublisher` en
    V2 ; au Sprint 0, la voie normale de publication passe par
    `apps.core.outbox.publisher.publish_event()` à l'intérieur d'une
    transaction, PAS par ce port directement (voir §21 master prompt).
    """

    def publish(self, event: dict) -> None:
        raise NotImplementedError(
            "InProcessPublisher n'est pas destiné à un appel direct au Sprint 0 : "
            "utiliser apps.core.outbox.publisher.publish_event() dans une transaction."
        )

    def publish_batch(self, events: Iterable[dict]) -> None:
        raise NotImplementedError(
            "InProcessPublisher n'est pas destiné à un appel direct au Sprint 0."
        )


class RecordingPublisher(EventPublisher):
    """Tests — capture les événements publiés pour assertion, sans effet de bord."""

    def __init__(self):
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        self.published.append(event)

    def publish_batch(self, events: Iterable[dict]) -> None:
        self.published.extend(events)
