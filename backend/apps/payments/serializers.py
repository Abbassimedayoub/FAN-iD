from rest_framework import serializers

from .models import PaymentIntent


class PaymentIntentResponseSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            "id",
            "order_id",
            "provider",
            "provider_intent_id",
            "amount_cents",
            "currency",
            "status",
            "client_secret",
        )
