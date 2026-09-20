from abc import ABC, abstractmethod
from typing import Any


class PaymentGateway(ABC):
    """
    Payment-provider port.

    Expected implementations include `StripeGateway` and `FakeGateway` for
    tests with no network calls to Stripe.
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

    @abstractmethod
    def create_refund(
        self,
        *,
        payment_intent_id: str,
        amount_cents: int,
        idempotency_key: str,
    ) -> Any:
        """Create or replay a provider refund."""
        raise NotImplementedError
