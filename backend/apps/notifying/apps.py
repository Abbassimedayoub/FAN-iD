from django.apps import AppConfig


class NotifyingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifying"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer

        from .consumers import OrganizerDecisionEmailConsumer
        from .event_scanner_consumers import (
            EventScannerNotificationConsumer,
        )

        register_consumer(OrganizerDecisionEmailConsumer())
        register_consumer(
            EventScannerNotificationConsumer()
        )

    label = "notifying"
