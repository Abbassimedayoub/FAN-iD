from abc import ABC, abstractmethod
from typing import Iterable


class EventPublisher(ABC):
    """
    Event-publication port.

    The current explicit guardrail implementation is
    `UnimplementedEventPublisher`. The normal publication path is
    `apps.core.outbox.publisher.publish_event()`, called inside a transaction;
    the relay then dispatches internally through `register_consumer()`.

    Expected future implementations include `SqsPublisher` or
    `KafkaPublisher`; tests use `RecordingPublisher` to capture events
    without calling any real network service.
    """

    @abstractmethod
    def publish(self, event: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish_batch(self, events: Iterable[dict]) -> None:
        raise NotImplementedError
