from django.apps import AppConfig


class NotifyingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifying"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer

        from .consumers import OrganizerDecisionEmailConsumer

        register_consumer(OrganizerDecisionEmailConsumer())
    label = "notifying"
