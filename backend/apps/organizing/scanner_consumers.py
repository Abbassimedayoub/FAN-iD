from __future__ import annotations

from django.utils import timezone

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.identity.api import USER_LOGGED_IN, USER_PASSWORD_CHANGED, USER_PROFILE_UPDATED

from .constants import (
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_EMAIL_SENT,
    SCANNER_INVITATION_CANCELLED,
    SCANNER_INVITED,
    SCANNER_OPENED,
)
from .events import (
    SCANNER_INVITATION_REISSUED_EVENT,
    SCANNER_INVITED_EVENT,
    SCANNER_LEAVE_REJECTED_EVENT,
    SCANNER_LEAVE_REQUESTED_EVENT,
    SCANNER_PASSWORD_HELP_REQUESTED_EVENT,
    SCANNER_REVOKED_EVENT,
    SCANNER_TEMP_PASSWORD_REISSUED_EVENT,
)
from .models import Scanner
from .scanner_credential_tasks import send_scanner_password_help_emails, send_scanner_password_reissued_emails
from .scanner_leave_tasks import send_scanner_leave_rejected_emails, send_scanner_leave_request_emails
from .scanner_tasks import (
    send_scanner_invitation_emails,
    send_scanner_invitation_reissued_emails,
    send_scanner_milestone_emails,
    send_scanner_revocation_emails,
)

TERMINAL_STATUSES = {
    SCANNER_INVITATION_CANCELLED,
    SCANNER_DELETED,
}


def activate_scanner_if_ready(
    *,
    user_id: object,
) -> Scanner | None:
    """
    L'activation exige les deux étapes :
    - mot de passe temporaire remplacé ;
    - téléphone renseigné.
    """

    scanner = Scanner.objects.select_related("user").filter(user_id=user_id).first()

    if scanner is None:
        return None

    if scanner.status in TERMINAL_STATUSES:
        return None

    if scanner.status == SCANNER_ACTIVE:
        return None

    if scanner.status not in {
        SCANNER_INVITED,
        SCANNER_EMAIL_SENT,
        SCANNER_OPENED,
    }:
        return None

    if scanner.user.must_change_password:
        return None

    phone = (scanner.user.phone or "").strip()

    if not phone:
        return None

    updated = Scanner.objects.filter(
        pk=scanner.pk,
        status__in=[
            SCANNER_INVITED,
            SCANNER_EMAIL_SENT,
            SCANNER_OPENED,
        ],
    ).update(
        status=SCANNER_ACTIVE,
        activated_at=timezone.now(),
    )

    if not updated:
        return None

    scanner.refresh_from_db()

    return scanner


class ScannerLifecycleConsumer(BaseConsumer):
    name = "organizing.scanner_lifecycle"

    handled_event_types = {
        SCANNER_INVITED_EVENT,
        SCANNER_LEAVE_REQUESTED_EVENT,
        SCANNER_LEAVE_REJECTED_EVENT,
        SCANNER_REVOKED_EVENT,
        USER_LOGGED_IN,
        USER_PASSWORD_CHANGED,
        SCANNER_PASSWORD_HELP_REQUESTED_EVENT,
        SCANNER_TEMP_PASSWORD_REISSUED_EVENT,
        SCANNER_INVITATION_REISSUED_EVENT,
        USER_PROFILE_UPDATED,
    }

    def handle(
        self,
        event: OutboxEvent,
    ) -> None:
        if event.event_type == SCANNER_PASSWORD_HELP_REQUESTED_EVENT:
            self.defer(
                lambda: (
                    send_scanner_password_help_emails.delay(
                        request_id=(event.payload["request_id"]),
                    )
                )
            )
            return

        if event.event_type == SCANNER_TEMP_PASSWORD_REISSUED_EVENT:
            self.defer(
                lambda: (
                    send_scanner_password_reissued_emails.delay(
                        request_id=(event.payload["request_id"]),
                        generation=int(event.payload["generation"]),
                    )
                )
            )
            return

        if event.event_type == SCANNER_LEAVE_REQUESTED_EVENT:
            self.defer(
                lambda: send_scanner_leave_request_emails.delay(
                    scanner_id=str(event.aggregate_id),
                )
            )
            return

        if event.event_type == SCANNER_LEAVE_REJECTED_EVENT:
            self.defer(
                lambda: send_scanner_leave_rejected_emails.delay(
                    scanner_id=str(event.aggregate_id),
                )
            )
            return

        if event.event_type == SCANNER_REVOKED_EVENT:
            self.defer(
                lambda: (
                    send_scanner_revocation_emails.delay(
                        scanner_id=str(event.aggregate_id),
                    )
                )
            )
            return

        if event.event_type == SCANNER_INVITATION_REISSUED_EVENT:
            self.defer(
                lambda: (
                    send_scanner_invitation_reissued_emails.delay(
                        scanner_id=str(event.aggregate_id),
                        generation=int(event.payload["generation"]),
                    )
                )
            )
            return

        if event.event_type == SCANNER_INVITED_EVENT:
            self.defer(
                lambda: (
                    send_scanner_invitation_emails.delay(
                        scanner_id=str(event.aggregate_id),
                    )
                )
            )
            return

        if event.event_type == USER_LOGGED_IN:
            if event.payload.get("role") != "SCANNER":
                return

            scanner = Scanner.objects.filter(
                user_id=event.aggregate_id,
            ).first()

            if scanner is None:
                return

            if scanner.status in TERMINAL_STATUSES:
                return

            if scanner.status in {
                SCANNER_INVITED,
                SCANNER_EMAIL_SENT,
            }:
                Scanner.objects.filter(
                    pk=scanner.pk,
                    status__in=[
                        SCANNER_INVITED,
                        SCANNER_EMAIL_SENT,
                    ],
                ).update(
                    status=SCANNER_OPENED,
                    opened_at=timezone.now(),
                )

                self.defer(
                    lambda: (
                        send_scanner_milestone_emails.delay(
                            scanner_id=str(scanner.pk),
                            milestone="OPENED",
                        )
                    )
                )

            return

        if event.event_type == USER_PROFILE_UPDATED:
            changed_fields = set(
                event.payload.get(
                    "changed_fields",
                    [],
                )
            )

            if "phone" not in changed_fields:
                return

            scanner = activate_scanner_if_ready(
                user_id=event.aggregate_id,
            )

            if scanner is None:
                return

            self.defer(
                lambda: (
                    send_scanner_milestone_emails.delay(
                        scanner_id=str(scanner.pk),
                        milestone="ACTIVE",
                    )
                )
            )
            return

        if event.event_type == USER_PROFILE_UPDATED:
            changed_fields = set(
                event.payload.get(
                    "changed_fields",
                    [],
                )
            )

            if "phone" not in changed_fields:
                return

            scanner = activate_scanner_if_ready(
                user_id=event.aggregate_id,
            )

            if scanner is None:
                return

            self.defer(
                lambda: (
                    send_scanner_milestone_emails.delay(
                        scanner_id=str(scanner.pk),
                        milestone="ACTIVE",
                    )
                )
            )
            return

        if event.event_type == USER_PASSWORD_CHANGED:
            if not event.payload.get("temporary_credential_replaced"):
                return

            scanner = activate_scanner_if_ready(
                user_id=event.aggregate_id,
            )

            if scanner is None:
                return

            self.defer(
                lambda: (
                    send_scanner_milestone_emails.delay(
                        scanner_id=str(scanner.pk),
                        milestone="ACTIVE",
                    )
                )
            )
            return
