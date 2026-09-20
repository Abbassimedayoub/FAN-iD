"""
`RegistrationService` owns supporter-account creation business rules.

Views translate HTTP and serializers validate input shape; this service carries
rules that must hold regardless of caller, including web, mobile, administration
commands, or data-recovery paths.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ValidationBusinessError
from apps.core.outbox.publisher import publish_event

from ..constants import MINIMUM_AGE_YEARS
from ..events import AGGREGATE_USER, USER_REGISTERED, user_registered_payload
from ..exceptions import EmailAlreadyExistsError, TermsNotAcceptedError, UnderageError
from ..models import User

logger = logging.getLogger("fanid.identity")


def age_in_years(birth_date: datetime.date, on_date: datetime.date) -> int:
    """
    Compute attained age without third-party libraries, avoiding day-count approximations around
    leap years.
    """
    had_birthday = (on_date.month, on_date.day) >= (birth_date.month, birth_date.day)
    return on_date.year - birth_date.year - (0 if had_birthday else 1)


@dataclass(frozen=True, slots=True)
class RegistrationCommand:
    """
    Service input whose shape has already been validated by the serializer.

    The command is intentionally closed and carries no privilege fields.
    `terms_accepted` is a boolean; the server records the acceptance timestamp
    rather than trusting a client-supplied timestamp.
    """

    email: str
    password: str
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    terms_accepted: bool
    phone: str | None = None


class RegistrationService:
    """Create a supporter account and publish the corresponding event."""

    @staticmethod
    @transaction.atomic
    def register(command: RegistrationCommand) -> User:
        """
        Create the user and publish `identity.user.registered` in the same transaction so no event
        can survive a rolled-back account creation.
        """
        if not command.terms_accepted:
            raise TermsNotAcceptedError()

        today = timezone.localdate()
        age = age_in_years(command.date_of_birth, today)
        if age < MINIMUM_AGE_YEARS:
            # Error details contain only bounds, never the submitted birth date, because the
            # error body may flow through logs and traces.
            raise UnderageError(details={"minimum_age_years": MINIMUM_AGE_YEARS})

        try:
            # Use an inner savepoint so an IntegrityError does not poison the outer transaction.
            with transaction.atomic():
                user = User.objects.create_user(
                    email=command.email,
                    password=command.password,
                    date_of_birth=command.date_of_birth,
                    terms_accepted_at=timezone.now(),
                    first_name=command.first_name,
                    last_name=command.last_name,
                    phone=command.phone or None,
                )
        except IntegrityError as exc:
            # Do not pre-check uniqueness with SELECT; concurrent requests could both pass.
            # Database citext uniqueness is the race-safe guarantee.
            # traduit sa violation plutot que de courir apres elle.
            raise EmailAlreadyExistsError() from exc
        except DjangoValidationError as exc:
            # create_user calls full_clean so model-validator failures can be mapped cleanly.
            # `django.core.exceptions.ValidationError`.
            raise ValidationBusinessError(details={"fields": exc.message_dict}) from exc

        publish_event(
            event_type=USER_REGISTERED,
            aggregate_type=AGGREGATE_USER,
            aggregate_id=user.pk,
            actor_id=user.pk,
            payload=user_registered_payload(role_name=user.role.name),
        )

        if str(user.phone or "").strip():
            from ..events import USER_PHONE_CHANGED, user_phone_changed_payload

            publish_event(
                event_type=USER_PHONE_CHANGED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=user_phone_changed_payload(
                    first_record=True,
                ),
            )

        # Do not log the email address, password, or any request-body value.
        # The correlation ID links this log entry to the HTTP request for diagnostics.
        logger.info("identity.user_registered", extra={"user_id": str(user.pk)})
        return user

    @staticmethod
    def as_command(data: dict[str, Any]) -> RegistrationCommand:
        """Build the command from already validated data."""
        return RegistrationCommand(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            date_of_birth=data["date_of_birth"],
            terms_accepted=data["terms_accepted"],
            phone=data.get("phone") or None,
        )
