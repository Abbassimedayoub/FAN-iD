from django.urls import path

from .views import PaymentIntentCreateView

app_name = "payments"

urlpatterns = [
    path(
        "orders/<uuid:order_id>/payment-intent",
        PaymentIntentCreateView.as_view(),
        name="payment-intent-create",
    ),
]
