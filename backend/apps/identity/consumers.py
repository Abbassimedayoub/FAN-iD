from __future__ import annotations

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .events import (
    PASSWORD_RESET_COMPLETED,
    PASSWORD_RESET_REQUESTED,
    USER_PHONE_CHANGED,
)
from .tasks import (
    send_password_changed_email,
    send_password_reset_email,
    send_phone_changed_email,
)


class PasswordResetEmailConsumer(BaseConsumer):
    """
    Réagit aux événements de récupération appartenant au contexte identity.

    Aucun appel SMTP n'est effectué dans la transaction Outbox.
    """

    name = "identity.password_reset_email"

    handled_event_types = {
        PASSWORD_RESET_REQUESTED,
        PASSWORD_RESET_COMPLETED,
        USER_PHONE_CHANGED,
    }

    def handle(
        self,
        event: OutboxEvent,
    ) -> None:
        user_id = str(event.aggregate_id)

        if event.event_type == USER_PHONE_CHANGED:
            first_record = bool(
                event.payload.get(
                    "first_record",
                )
            )

            self.defer(
                lambda: (
                    send_phone_changed_email.delay(
                        user_id=user_id,
                        first_record=first_record,
                    )
                )
            )
            return

        if event.event_type == PASSWORD_RESET_REQUESTED:
            challenge_id = event.payload.get("challenge_id")

            if not challenge_id:
                return

            self.defer(
                lambda: (
                    send_password_reset_email.delay(
                        user_id=user_id,
                        challenge_id=str(challenge_id),
                    )
                )
            )

            return

        if event.event_type == PASSWORD_RESET_COMPLETED:
            self.defer(
                lambda: (
                    send_password_changed_email.delay(
                        user_id=user_id,
                    )
                )
            )
