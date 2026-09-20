from abc import ABC, abstractmethod
from typing import Any


class NotificationSender(ABC):
    """
    Notification port.

    Expected implementations include `SesAdapter`, `FcmAdapter`, and
    `InMemorySender` for tests that capture sends without network access.
    """

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_push(self, device_token: str, title: str, body: str, **kwargs: Any) -> None:
        raise NotImplementedError
