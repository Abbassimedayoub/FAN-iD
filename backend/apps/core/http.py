"""
Requête HTTP enrichie par les middlewares du socle.

Django ne permet pas de déclarer statiquement les attributs qu'un middleware
ajoute à `HttpRequest`. Les déclarer ici donne à mypy — et surtout au lecteur —
le contrat réel de l'objet qui circule dans l'application, au lieu de disperser
un `# type: ignore[attr-defined]` à chaque point d'usage.

Ce module est le point d'extension prévu : le Sprint 1 y ajoutera `device` et
`session` (DeviceBindingMiddleware), et l'acteur résolu pour AuthAuditMiddleware.

`FanIdRequest` n'est jamais instanciée : Django continue de fabriquer des
`WSGIRequest`. C'est une déclaration de contrat destinée au vérificateur de
types, pas une classe à construire.
"""

from typing import TYPE_CHECKING

from django.http import HttpRequest

if TYPE_CHECKING:  # pragma: no cover - déclaration de type uniquement
    from apps.core.idempotency.models import IdempotencyRecord


class FanIdRequest(HttpRequest):
    """`HttpRequest` augmentée des attributs posés par les middlewares du socle."""

    #: Posé par `CorrelationMiddleware` sur CHAQUE requête (jamais absent).
    correlation_id: str

    #: Posé par `IdempotencyMiddleware` uniquement sur les requêtes portant un
    #: en-tête `Idempotency-Key` valide — absent sinon.
    idempotency_record: "IdempotencyRecord"
