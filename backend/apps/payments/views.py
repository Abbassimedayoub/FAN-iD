from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.adapters.payments import StripeWebhookSignatureError

from .gateways import get_payment_gateway
from .serializers import PaymentIntentResponseSerializer
from .services import (
    create_payment_intent,
    mark_payment_intent_succeeded,
    mark_payment_refund_failed,
    mark_payment_refund_succeeded,
)


class PaymentIntentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        intent = create_payment_intent(
            order_id=order_id,
            user=request.user,
            gateway=get_payment_gateway(),
        )
        return Response(
            PaymentIntentResponseSerializer(intent).data,
            status=status.HTTP_201_CREATED,
        )


def _field(value, name):
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    Endpoint public Stripe. Son seul accès est la signature Stripe vérifiée.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        gateway = get_payment_gateway()

        if getattr(gateway, "provider_name", None) != "stripe":
            return Response(status=status.HTTP_404_NOT_FOUND)

        signature = request.headers.get("Stripe-Signature", "")

        try:
            event = gateway.verify_webhook(request.body, signature)
        except StripeWebhookSignatureError:
            return Response(
                {"code": "INVALID_STRIPE_SIGNATURE"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = _field(event, "type")
        provider_object = _field(_field(event, "data"), "object")

        if event_type == "payment_intent.succeeded":
            mark_payment_intent_succeeded(
                provider_intent_id=_field(provider_object, "id"),
            )
        elif event_type == "refund.updated":
            refund_status = _field(provider_object, "status")
            if refund_status == "succeeded":
                mark_payment_refund_succeeded(
                    provider_refund_id=_field(provider_object, "id"),
                )
            elif refund_status == "failed":
                mark_payment_refund_failed(
                    provider_refund_id=_field(provider_object, "id"),
                    failure_reason="Stripe a signalé l’échec du remboursement.",
                )

        return Response(status=status.HTTP_200_OK)
