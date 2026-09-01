from abc import ABC, abstractmethod
from typing import Any


class PaymentGateway(ABC):
    """
    Port de paiement (§2.3 Source B).

    Implémentations prévues : `StripeGateway` (Sprint 3), `FakeGateway` (tests
    — aucun appel réseau vers Stripe dans la suite de tests).
    """

    @abstractmethod
    def create_intent(self, amount_cents: int, currency: str, metadata: dict) -> Any:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def retrieve_intent(self, intent_id: str) -> Any:
        raise NotImplementedError
