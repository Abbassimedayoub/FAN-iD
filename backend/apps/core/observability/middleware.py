"""
CorrelationMiddleware + RequestLogMiddleware (§26/§33 master prompt, §2.5 Source B).

Position imposée : CorrelationMiddleware doit s'exécuter avant TOUT ce qui
journalise (règle absolue). RequestLogMiddleware juste après.
"""
import logging
import time
import uuid

from .context import CORRELATION_ID_HEADER, get_correlation_id, set_correlation_id

request_logger = logging.getLogger("fanid.request")


class CorrelationMiddleware:
    """
    Génère ou propage un identifiant de corrélation unique par requête.

    Règle testée explicitement : jamais deux `correlation_id` différents pour
    la même requête (ni un généré puis un autre, ni le header ignoré).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = incoming if incoming else str(uuid.uuid4())
        set_correlation_id(correlation_id)
        request.correlation_id = correlation_id

        response = self.get_response(request)

        response[CORRELATION_ID_HEADER] = correlation_id
        return response


class RequestLogMiddleware:
    """Une ligne de log structurée par requête : méthode, route, statut, latence, acteur."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        user_id = None
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = str(user.pk)

        request_logger.info(
            "http_request",
            extra={
                "http_method": request.method,
                "http_path": request.path,
                "http_status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "correlation_id": get_correlation_id(),
            },
        )
        return response
