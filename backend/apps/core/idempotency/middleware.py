"""
IdempotencyMiddleware — interception des mutations portant `Idempotency-Key`.

Position imposée (§2.5 Source B / §33 master prompt) : APRÈS
`AuthenticationMiddleware`. La clé est scopée par utilisateur
(`UNIQUE(key, user_id)`) : sans utilisateur résolu, deux clients différents
partageant la même clé se voleraient mutuellement leurs réponses — faille de
fuite de données inter-comptes explicitement identifiée par Source B.
"""
import json
import logging

from django.http import JsonResponse

from apps.core.exceptions import BusinessError
from apps.core.handlers import _error_body

from . import service

logger = logging.getLogger("fanid.idempotency")

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENCY_KEY_HEADER = "HTTP_IDEMPOTENCY_KEY"


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.META.get(IDEMPOTENCY_KEY_HEADER)

        if request.method not in _MUTATING_METHODS or not key:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            # Pas d'utilisateur résolu : on ne peut pas scoper la clé en sécurité.
            # On laisse passer — c'est l'authentification (401) qui traitera le cas,
            # jamais l'idempotence qui ne doit pas se substituer à l'auth.
            return self.get_response(request)

        request_hash = service.compute_request_hash(request.body)

        try:
            outcome = service.begin(
                key=key,
                user_id=user.pk,
                endpoint=request.path,
                request_hash=request_hash,
            )
        except BusinessError as exc:
            return JsonResponse(
                _error_body(exc.code, exc.message, exc.details), status=exc.status_code
            )

        if outcome.replayed:
            body = outcome.record.response_body
            return JsonResponse(body, status=outcome.record.response_status, safe=False)

        request.idempotency_record = outcome.record

        response = self.get_response(request)

        try:
            payload = json.loads(response.content) if response.content else None
        except (ValueError, TypeError):
            payload = None

        if 200 <= response.status_code < 500:
            service.complete(outcome.record, response_status=response.status_code, response_body=payload)
        else:
            service.fail(outcome.record)

        return response
