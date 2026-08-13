from typing import Iterable

from apps.core.interfaces import EventPublisher


class UnimplementedEventPublisher(EventPublisher):
    """
    Garde-fou explicite — PAS une implémentation V1 fonctionnelle.

    Correction post-bilan Sprint 0 (P2.2) : la classe s'appelait auparavant
    `InProcessPublisher`, un nom qui laissait croire à une implémentation
    réelle du port `EventPublisher` alors que ses deux méthodes ne faisaient
    que lever `NotImplementedError`. Renommée pour que le nom dise la
    vérité : à ce stade du projet, aucune implémentation directe de ce port
    n'existe, et ce n'est pas un oubli.

    Au Sprint 0, la voie normale de publication d'un événement est
    `apps.core.outbox.publisher.publish_event()`, appelé à l'intérieur d'une
    transaction métier — il écrit dans la table `outbox_event` (garantie
    d'atomicité producteur/événement, ADR-S-03). Le relais (`outbox/relay.py`)
    consomme ensuite cette table et dispatche vers les consommateurs
    enregistrés via `register_consumer()` — un mécanisme in-process qui ne
    passe PAS par ce port `EventPublisher`.

    Ce port reste défini (§2.3 Source B) comme le point d'extension pour un
    futur `SqsPublisher`/`KafkaPublisher` en V2 — une bascule de
    configuration, pas une refonte. Tant que cette implémentation V2 n'existe
    pas, instancier ce garde-fou et l'utiliser fait volontairement échouer
    l'appel plutôt que de simuler silencieusement une publication qui n'aurait
    aucun effet réel.

    Pour les tests, utiliser `RecordingPublisher` ci-dessous : c'est le
    double de test concret de ce port, il ne lève jamais `NotImplementedError`.
    """

    def publish(self, event: dict) -> None:
        raise NotImplementedError(
            "Aucune implémentation V2 (SQS/Kafka) du port EventPublisher n'existe "
            "encore. Pour publier un événement métier, utiliser "
            "apps.core.outbox.publisher.publish_event() dans une transaction. "
            "Pour les tests, utiliser RecordingPublisher."
        )

    def publish_batch(self, events: Iterable[dict]) -> None:
        raise NotImplementedError(
            "Aucune implémentation V2 (SQS/Kafka) du port EventPublisher n'existe "
            "encore. Voir apps.core.outbox.publisher.publish_event() (production) "
            "ou RecordingPublisher (tests)."
        )


class RecordingPublisher(EventPublisher):
    """Tests — capture les événements publiés pour assertion, sans effet de bord."""

    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        self.published.append(event)

    def publish_batch(self, events: Iterable[dict]) -> None:
        self.published.extend(events)
