from email.mime.image import MIMEImage
import logging
import os
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.core.email_branding import (
    FANID_LOGO_CID,
    load_fanid_logo_bytes,
    render_fanid_email_html,
)
from apps.core.interfaces import NotificationSender

logger = logging.getLogger("fanid.core")


class InMemorySender(NotificationSender):
    """Tests / dev sans SMTP réel — capture les envois pour assertion."""

    def __init__(self) -> None:
        self.emails_sent: list[dict] = []
        self.pushes_sent: list[dict] = []

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        self.emails_sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                **kwargs,
            }
        )

    def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        self.pushes_sent.append(
            {
                "device_token": device_token,
                "title": title,
                "body": body,
                **kwargs,
            }
        )


class ConsoleSender(NotificationSender):
    """
    Journalise au lieu d envoyer — DEVELOPPEMENT UNIQUEMENT.

    Le backend console permet de vérifier les notifications en local sans
    effectuer de trafic SMTP réel.
    """

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        logger.warning(
            "notification.console.email",
            extra={
                "to": to,
                "subject": subject,
                "body_length": len(body),
                "has_html": True,
                "has_reply_to": bool(kwargs.get("reply_to")),
            },
        )

    def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        logger.warning(
            "notification.console.push",
            extra={
                "title": title,
                "body": body,
                **kwargs,
            },
        )


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()

    if not value:
        raise ImproperlyConfigured(f"{name} est requis lorsque NOTIFICATION_BACKEND='smtp'.")

    return value


def _environment_bool(
    name: str,
    *,
    default: bool,
) -> bool:
    raw = os.environ.get(name)

    if raw is None:
        return default

    value = raw.strip().lower()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    raise ImproperlyConfigured(f"{name} doit être un booléen.")


class SmtpSender(NotificationSender):
    """
    Envoi SMTP réel.

    Les secrets restent exclusivement dans l environnement du processus.
    Ce backend fonctionne avec un serveur SMTP standard, notamment Gmail,
    Amazon SES SMTP, Mailgun SMTP ou un relais d entreprise.
    """

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        host = _required_environment("EMAIL_HOST")

        username = os.environ.get(
            "EMAIL_HOST_USER",
            "",
        ).strip()

        password = os.environ.get(
            "EMAIL_HOST_PASSWORD",
            "",
        )

        from_email = (
            os.environ.get(
                "DEFAULT_FROM_EMAIL",
                "",
            ).strip()
            or username
        )

        if not from_email:
            raise ImproperlyConfigured(
                "DEFAULT_FROM_EMAIL ou EMAIL_HOST_USER est requis " "lorsque NOTIFICATION_BACKEND='smtp'."
            )

        use_tls = _environment_bool(
            "EMAIL_USE_TLS",
            default=True,
        )
        use_ssl = _environment_bool(
            "EMAIL_USE_SSL",
            default=False,
        )

        if use_tls and use_ssl:
            raise ImproperlyConfigured(
                "EMAIL_USE_TLS et EMAIL_USE_SSL ne peuvent pas " "être activés simultanément."
            )

        default_port = 465 if use_ssl else 587

        try:
            port = int(
                os.environ.get(
                    "EMAIL_PORT",
                    str(default_port),
                )
            )
        except ValueError as exc:
            raise ImproperlyConfigured("EMAIL_PORT doit être un entier.") from exc

        try:
            timeout = float(
                os.environ.get(
                    "EMAIL_TIMEOUT",
                    "10",
                )
            )
        except ValueError as exc:
            raise ImproperlyConfigured("EMAIL_TIMEOUT doit être un nombre.") from exc

        connection = get_connection(
            backend=("django.core.mail.backends.smtp." "EmailBackend"),
            host=host,
            port=port,
            username=username or None,
            password=password or None,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
        )

        reply_to_value = kwargs.get("reply_to")
        reply_to = [str(reply_to_value)] if reply_to_value else None

        html_body = kwargs.get("html_body") or render_fanid_email_html(
            subject=subject,
            body=body,
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to],
            reply_to=reply_to,
            connection=connection,
        )

        message.attach_alternative(
            html_body,
            "text/html",
        )

        logo = MIMEImage(
            load_fanid_logo_bytes(),
            _subtype="png",
        )
        logo.add_header(
            "Content-ID",
            f"<{FANID_LOGO_CID}>",
        )
        logo.add_header(
            "Content-Disposition",
            "inline",
            filename="fanid-logo.png",
        )

        message.mixed_subtype = "related"
        message.attach(logo)

        sent = message.send(fail_silently=False)

        if sent != 1:
            raise RuntimeError("Le serveur SMTP n'a pas confirmé " "l'envoi du message.")

    def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError("Le backend SMTP ne prend pas en charge " "les notifications push.")


def build_notification_sender() -> NotificationSender:
    """
    Fabrique l expediteur selon `NOTIFICATION_BACKEND`.

    Aucun repli silencieux : une valeur inconnue provoque une erreur.
    """

    backend = str(settings.NOTIFICATION_BACKEND)

    if backend == "console":
        return ConsoleSender()

    if backend == "memory":
        return InMemorySender()

    if backend == "smtp":
        return SmtpSender()

    raise ImproperlyConfigured(
        "NOTIFICATION_BACKEND inconnu : " f"{backend!r}. Valeurs admises : " "'console', 'memory', 'smtp'."
    )
