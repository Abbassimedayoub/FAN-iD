"""Django middleware support for JWT-aware request processing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

from apps.core.exceptions import BusinessError

from .authentication import JWT_PREAUTH_ERROR_ATTR, JWT_PREAUTH_RESULT_ATTR, JWTAuthentication


class JWTAuthenticationMiddleware:
    """Resolve a Bearer principal before user-scoped Django middleware runs."""

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        authenticator = JWTAuthentication()

        try:
            result = authenticator.authenticate(request)
        except BusinessError as exc:
            # DRF remains responsible for formatting authentication failures.
            # Caching the failure avoids decoding or checking the token twice.
            setattr(request, JWT_PREAUTH_ERROR_ATTR, exc)
        else:
            setattr(request, JWT_PREAUTH_RESULT_ATTR, result)

            if result is not None:
                user, claims = result
                authenticated_request: Any = request
                authenticated_request.user = user
                authenticated_request.auth = claims

        return self.get_response(request)
