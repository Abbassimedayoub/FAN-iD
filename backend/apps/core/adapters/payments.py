import uuid
from typing import Any

from apps.core.interfaces import PaymentGateway


class FakeGateway(PaymentGateway):
    """
    Tests — aucun appel réseau vers Stripe. Implémentation réelle
    (`StripeGateway`) livrée au Sprint 3 avec la logique d'achat.
    """

    def __init__(self) -> None:
        self.created_intents: list[dict] = []

    def create_intent(self, amount_cents: int, currency: str, metadata: dict) -> Any:
        intent = {
            "id": f"pi_fake_{uuid.uuid4().hex[:16]}",
            "amount_cents": amount_cents,
            "currency": currency,
            "metadata": metadata,
            "client_secret": f"secret_{uuid.uuid4().hex}",
        }
        self.created_intents.append(intent)
        return intent

    def verify_webhook(self, payload: bytes, signature: str) -> Any:
        return {"verified": True, "payload": payload}

    def retrieve_intent(self, intent_id: str) -> Any:
        for intent in self.created_intents:
            if intent["id"] == intent_id:
                return intent
        raise LookupError(f"PaymentIntent {intent_id} introuvable (FakeGateway).")
