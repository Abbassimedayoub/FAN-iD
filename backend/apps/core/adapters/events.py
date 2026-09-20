from typing import Iterable

from apps.core.interfaces import EventPublisher


class UnimplementedEventPublisher(EventPublisher):
    """
    Explicit guardrail — NOT a functional V1 implementation.

    This class used to be called `InProcessPublisher`, which implied a real
    implementation of the `EventPublisher` port even though both methods only
    raised `NotImplementedError`. The name now states the truth: no direct
    implementation of this port exists at this stage, by design.

    The normal publication path is
    `apps.core.outbox.publisher.publish_event()`, called inside the business
    transaction. It writes to `outbox_event`, preserving producer/event
    atomicity. The relay then consumes that table and dispatches events to
    consumers registered with `register_consumer()`.

    This port remains as an extension point for a future
    `SqsPublisher`/`KafkaPublisher`. Until such an implementation exists,
    using this guardrail deliberately fails instead of silently pretending to
    publish an event.

    Tests should use `RecordingPublisher` below.
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
    """Test double that records published events without side effects."""

    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        self.published.append(event)

    def publish_batch(self, events: Iterable[dict]) -> None:
        self.published.extend(events)
