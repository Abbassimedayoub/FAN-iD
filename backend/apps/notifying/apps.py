from django.apps import AppConfig


class NotifyingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifying"
    label = "notifying"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer

        from .consumers import OrganizerDecisionEmailConsumer
        from .event_buyer_consumers import EventBuyerNotificationConsumer
        from .event_scanner_consumers import EventScannerNotificationConsumer
        from .final_report_consumers import FinalReportNotificationConsumer
        from .refund_notification_consumers import PaymentRefundNotificationConsumer
        from .ticket_transfer_consumers import TicketTransferNotificationConsumer

        register_consumer(OrganizerDecisionEmailConsumer())
        register_consumer(EventBuyerNotificationConsumer())
        register_consumer(EventScannerNotificationConsumer())
        register_consumer(FinalReportNotificationConsumer())
        register_consumer(PaymentRefundNotificationConsumer())
        register_consumer(TicketTransferNotificationConsumer())
