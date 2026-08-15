import sys

from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core (socle transverse)"

    def ready(self) -> None:
        # Enregistre les controles systeme avant tout retour anticipe.
        # L'import suffit : @register() attache les controles au registre Django.
        from . import checks  # noqa: F401

        # Ne pas instrumenter pendant makemigrations/migrate/collectstatic — bruit
        # inutile et connexion réseau au collecteur non pertinente pour ces commandes.
        management_commands_to_skip = {"makemigrations", "migrate", "collectstatic", "shell"}
        if len(sys.argv) > 1 and sys.argv[1] in management_commands_to_skip:
            return
        if getattr(settings, "OTEL_ENABLED", True):
            from .observability.tracing import bootstrap_tracing

            bootstrap_tracing()
