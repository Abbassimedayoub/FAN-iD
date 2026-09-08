from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.access"
    label = "access"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer

        from .completion_consumers import EventCompletionAdmissionConsumer
        from .final_report_consumers import EventCompletionFinalReportConsumer

        register_consumer(EventCompletionAdmissionConsumer())
        register_consumer(EventCompletionFinalReportConsumer())
