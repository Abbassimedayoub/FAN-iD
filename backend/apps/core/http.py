"""
HTTP request typing enriched with attributes installed by project middleware.

Django cannot statically declare middleware-added attributes on `HttpRequest`.
These protocol-like subclasses document the real request contract for readers
and type checking without changing what Django instantiates at runtime.
"""

import uuid
from typing import TYPE_CHECKING

from django.http import HttpRequest
from rest_framework.request import Request

if TYPE_CHECKING:  # pragma: no cover - déclaration de type uniquement
    from apps.core.idempotency.models import IdempotencyRecord


class FanIdRequest(HttpRequest):
    """`HttpRequest` augmented with attributes installed by core middleware."""

    #: Set by CorrelationMiddleware on every request.
    correlation_id: str

    #: Set by IdempotencyMiddleware only for requests carrying a valid Idempotency-Key header.
    idempotency_record: "IdempotencyRecord"


class FanIdApiRequest(Request):
    """
    DRF Request augmented by identity authentication.

    Keep this distinct from Django's underlying HttpRequest because
    JWTAuthentication runs inside DRF and decorates the wrapper request. Only
    primitive types are declared here so core does not depend on identity models.
    """

    #: Session identifier re-read from the database for each authenticated request.
    session_id: uuid.UUID

    #: 1 = password, 2 = step-up verification. Read from the session so changes take effect immediately.
    auth_level: int

    #: Organizer identifier installed by the owning context before permission checks; absence denies
    #: OWN_ORGANIZER scope.
    organizer_id: uuid.UUID | None
