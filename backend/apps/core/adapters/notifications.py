import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.core.interfaces import NotificationSender

logger = logging.getLogger("fanid.core")


class InMemorySender(NotificationSender):
    """Tests / dev sans SMTP réel — capture les envois pour assertion."""

    def __init__(self) -> None:
        self.emails_sent: list[dict] = []
        self.pushes_sent: list[dict] = []

    def send_email(self, to: str, subject: str, body: str, **kwargs: Any) -> None:
        self.emails_sent.append({"to": to, "subject": subject, "body": body, **kwargs})

    def send_push(self, device_token: str, title: str, body: str, **kwargs: Any) -> None:
        self.pushes_sent.append({"device_token": device_token, "title": title, "body": body, **kwargs})


class ConsoleSender(NotificationSender):
    """
    Journalise au lieu d envoyer — DEVELOPPEMENT UNIQUEMENT.

    Le plan (§2.1) prevoit un adaptateur console tant que le contexte
    `notifying` n existe pas. Il rend le code de verification lisible dans les
    journaux du conteneur, ce qui est exactement ce qu il faut en developpement
    et exactement ce qu il ne faut pas ailleurs : **un code a usage unique
    ecrit en clair dans un journal est un secret publie**.

    D ou l avertissement au demarrage plutot qu un simple commentaire : un
    reglage par defaut qui avale silencieusement les courriels en production
    est precisement le « defaut silencieux » que le §40 du prompt maitre
    interdit.
    """

    def send_email(self, to: str, subject: str, body: str, **kwargs: Any) -> None:
        logger.warning(
            "notification.console.email",
            extra={"to": to, "subject": subject, "body": body, **kwargs},
        )

    def send_push(self, device_token: str, title: str, body: str, **kwargs: Any) -> None:
        logger.warning(
            "notification.console.push",
            extra={"title": title, "body": body, **kwargs},
        )


def build_notification_sender() -> NotificationSender:
    """
    Fabrique l expediteur selon `NOTIFICATION_BACKEND`.

    Aucun repli silencieux : un nom inconnu leve au demarrage de la requete
    plutot que d avaler les envois. Le jour ou `SesAdapter` arrive (S5), il
    s ajoute ici et rien d autre ne bouge.
    """
    backend = str(settings.NOTIFICATION_BACKEND)
    if backend == "console":
        return ConsoleSender()
    if backend == "memory":
        return InMemorySender()
    raise ImproperlyConfigured(
        f"NOTIFICATION_BACKEND inconnu : {backend!r}. Valeurs admises : 'console', 'memory'."
    )
