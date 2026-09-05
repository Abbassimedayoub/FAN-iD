from __future__ import annotations

import uuid
from typing import Any

from apps.core.interfaces import PaymentGateway

def _metadata_to_dict(metadata: Any) -> dict[str, Any]:
    if isinstance(metadata, dict):
        return dict(metadata)

    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())

    return {}



class FakeGateway(PaymentGateway):
    """
    Tests — aucun appel réseau vers Stripe.
    """

    provider_name = "fake"

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



class StripeWebhookSignatureError(ValueError):
    """La signature d'un webhook Stripe est absente ou invalide."""


class StripeGateway(PaymentGateway):
    """
    Adaptateur Stripe : les clés sont uniquement lues depuis l'environnement.
    """

    provider_name = "stripe"

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str,
        client=None,
    ) -> None:
        self.webhook_secret = webhook_secret

        if client is None:
            from stripe import StripeClient

            client = StripeClient(secret_key)

        self.client = client

    def create_intent(self, amount_cents: int, currency: str, metadata: dict) -> Any:
        intent = self.client.v1.payment_intents.create(
            params={
                "amount": amount_cents,
                "currency": currency.lower(),
                "automatic_payment_methods": {"enabled": True},
                "metadata": metadata,
            }
        )
        return {
            "id": intent.id,
            "amount_cents": intent.amount,
            "currency": intent.currency.upper(),
            "metadata": _metadata_to_dict(intent.metadata),
            "client_secret": intent.client_secret,
        }

    def verify_webhook(self, payload: bytes, signature: str) -> Any:
        import stripe

        try:
            return stripe.Webhook.construct_event(
                payload,
                signature,
                self.webhook_secret,
            )
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise StripeWebhookSignatureError(
                "Signature Stripe invalide.",
            ) from exc

    def retrieve_intent(self, intent_id: str) -> Any:
        intent = self.client.v1.payment_intents.retrieve(intent_id)
        return {
            "id": intent.id,
            "amount_cents": intent.amount,
            "currency": intent.currency.upper(),
            "metadata": _metadata_to_dict(intent.metadata),
            "client_secret": intent.client_secret,
            "status": intent.status,
        }
