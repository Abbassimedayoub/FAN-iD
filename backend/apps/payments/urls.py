from django.urls import path

from .views import PaymentIntentCreateView, StripeWebhookView

app_name = "payments"

urlpatterns = [
    path(
        "orders/<uuid:order_id>/payment-intent",
        PaymentIntentCreateView.as_view(),
        name="payment-intent-create",
    ),
    path(
        "payments/stripe/webhook",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]
