from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.core.adapters.payments import FakeGateway, StripeGateway


def get_payment_gateway():
    if settings.PAYMENT_GATEWAY == "fake":
        return FakeGateway()

    if settings.PAYMENT_GATEWAY == "stripe":
        if not settings.STRIPE_SECRET_KEY:
            raise ImproperlyConfigured(
                "STRIPE_SECRET_KEY est requis quand PAYMENT_GATEWAY=stripe.",
            )
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ImproperlyConfigured(
                "STRIPE_WEBHOOK_SECRET est requis quand PAYMENT_GATEWAY=stripe.",
            )
        return StripeGateway(
            secret_key=settings.STRIPE_SECRET_KEY,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        )

    raise ImproperlyConfigured(
        "PAYMENT_GATEWAY doit être 'fake' ou 'stripe'.",
    )
