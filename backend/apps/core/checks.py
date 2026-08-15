"""
Controles systeme du socle.

Django execute ces fonctions avant chaque commande `manage.py` — y compris le
`migrate` de l entrypoint. C est le dernier filet avant qu un environnement mal
configure ne demarre en silence.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, register


@register()
def console_notifier_is_development_only(
    app_configs: Any,
    **kwargs: Any,
) -> list[Error]:
    """
    Refuse `NOTIFICATION_BACKEND='console'` hors developpement.
    """
    if settings.DEBUG or getattr(settings, "NOTIFICATION_BACKEND", None) != "console":
        return []

    return [
        Error(
            "NOTIFICATION_BACKEND='console' alors que DEBUG=False.",
            hint=(
                "ConsoleSender ecrit les codes a usage unique dans les journaux et "
                "n envoie rien. Utiliser un adaptateur reel, ou 'memory' en test."
            ),
            id="core.E001",
        )
    ]
