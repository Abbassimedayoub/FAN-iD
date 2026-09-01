from django.apps import AppConfig


class OrganizingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organizing"
    label = "organizing"

    def ready(self) -> None:
        from apps.core.outbox.relay import (
            register_consumer,
        )

        from .scanner_consumers import (
            ScannerLifecycleConsumer,
        )

        register_consumer(ScannerLifecycleConsumer())
