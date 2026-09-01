from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose l'authentification JWT FAN id dans le schema OpenAPI."""

    target_class = "apps.identity.authentication.JWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, Any]:
        return build_bearer_security_scheme_object(
            header_name="Authorization",
            token_prefix="Bearer",
        )
