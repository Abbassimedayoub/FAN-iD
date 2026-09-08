from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    label = "payments"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer
        from .refund_consumers import EventCancellationRefundConsumer

        register_consumer(EventCancellationRefundConsumer())
