"""
CorrelationMiddleware and RequestLogMiddleware.

CorrelationMiddleware must execute before anything that logs. RequestLogMiddleware
runs immediately after it so every request log carries the same correlation ID.
"""

import logging
import time
import uuid
from collections.abc import Callable

from django.http import HttpResponse

from apps.core.http import FanIdRequest

from .context import CORRELATION_ID_HEADER, get_correlation_id, set_correlation_id

request_logger = logging.getLogger("fanid.request")


class CorrelationMiddleware:
    """
    Generate or propagate one correlation identifier per request.

    The invariant is explicit: one request must never end up with two different
    correlation IDs, whether through regeneration or ignored input headers.
    """

    def __init__(self, get_response: Callable[[FanIdRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: FanIdRequest) -> HttpResponse:
        incoming = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = incoming if incoming else str(uuid.uuid4())
        set_correlation_id(correlation_id)
        request.correlation_id = correlation_id

        response = self.get_response(request)

        response[CORRELATION_ID_HEADER] = correlation_id
        return response


class RequestLogMiddleware:
    """Write one structured log line per request: method, route, status, latency, actor."""

    def __init__(self, get_response: Callable[[FanIdRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: FanIdRequest) -> HttpResponse:
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
