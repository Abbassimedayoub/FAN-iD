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

import uuid
from typing import TYPE_CHECKING

from django.http import HttpRequest
from rest_framework.request import Request

if TYPE_CHECKING:  # pragma: no cover - déclaration de type uniquement
    from apps.core.idempotency.models import IdempotencyRecord


class FanIdRequest(HttpRequest):
    """`HttpRequest` augmentée des attributs posés par les middlewares du socle."""

    #: Posé par `CorrelationMiddleware` sur CHAQUE requête (jamais absent).
    correlation_id: str

    #: Posé par `IdempotencyMiddleware` uniquement sur les requêtes portant un
    #: en-tête `Idempotency-Key` valide — absent sinon.
    idempotency_record: "IdempotencyRecord"


class FanIdApiRequest(Request):
    """
    `Request` de DRF, augmentee par l authentification du contexte `identity`.

    Distincte de `FanIdRequest`, qui decrit la `HttpRequest` de Django vue par
    les middlewares. `JWTAuthentication` s execute DANS la vue DRF et pose ses
    attributs sur l objet `Request` — lequel n herite pas de `HttpRequest`, il
    l enveloppe. Les declarer sur `FanIdRequest` aurait decrit un objet qui ne
    les porte jamais.

    Types PRIMITIFS uniquement : y mettre `Session` ferait dependre `core` du
    contexte `identity` (ADR-S-01), ce que `lint-imports` interdit.

    Jamais instanciee, comme `FanIdRequest`. Ces attributs n existent que si
    `JWTAuthentication` a authentifie l appel : un autre authentificateur
    laisserait une requete sans eux.
    """

    #: Session relue en base a chaque requete authentifiee.
    session_id: uuid.UUID

    #: 1 = mot de passe, 2 = verification renforcee. Lu sur la SESSION, jamais
    #: sur le jeton, pour qu une retrogradation prenne effet immediatement.
    auth_level: int

    #: Organisateur de rattachement, pose par le contexte proprietaire
    #: avant le controle des permissions (ADR-S1-05). Absent partout
    #: ailleurs : son absence REFUSE la portee `OWN_ORGANIZER`.
    organizer_id: uuid.UUID | None
