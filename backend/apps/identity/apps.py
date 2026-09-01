from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"
    label = "identity"
    verbose_name = "Identity (comptes, rôles, appareils, sessions)"

    def ready(self) -> None:
        from apps.core.outbox.relay import register_consumer

        from . import openapi  # noqa: F401
        from .consumers import PasswordResetEmailConsumer

        register_consumer(PasswordResetEmailConsumer())
