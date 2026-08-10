from abc import ABC, abstractmethod


class NotificationSender(ABC):
    """
    Port de notification (§2.3 Source B).

    Implémentations prévues : `SesAdapter`, `FcmAdapter` (sprints ultérieurs),
    `InMemorySender` (tests — capture les envois sans réseau).
    """

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_push(self, device_token: str, title: str, body: str, **kwargs) -> None:
        raise NotImplementedError
