"""
Métriques RED (par endpoint) + USE (par ressource) + métriques métier
(§29/§30/§31 master prompt, §5.3 Source B).

Règle absolue (§64 master prompt) : aucune métrique métier n'est alimentée
artificiellement. `fanid_scan_total`, `fanid_purchase_total`,
`fanid_totp_verification_total` sont déclarées ici (structure posée au S0,
Source B §5.3) mais restent à zéro jusqu'à ce que les sprints correspondants
appellent réellement `.inc()` depuis du code métier réel — ce ne sont PAS des
compteurs factices pour "faire joli" sur un dashboard.
"""

import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from prometheus_client import Counter, Gauge, Histogram

# --- RED : Rate, Errors, Duration (par endpoint) ---
http_requests_total = Counter("http_requests_total", "Nombre de requêtes HTTP", ["method", "route", "status"])
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
http_requests_in_flight = Gauge("http_requests_in_flight", "Requêtes HTTP en cours de traitement", ["route"])

# --- USE : Utilization, Saturation, Errors (par ressource) ---
db_connections_active = Gauge("db_connections_active", "Connexions PostgreSQL actives")
db_connections_max = Gauge("db_connections_max", "Connexions PostgreSQL maximum configurées")
db_query_duration_seconds = Histogram("db_query_duration_seconds", "Durée des requêtes SQL")
redis_commands_total = Counter("redis_commands_total", "Commandes Redis exécutées", ["command"])
redis_latency_seconds = Histogram("redis_latency_seconds", "Latence des commandes Redis")
celery_queue_depth = Gauge("celery_queue_depth", "Profondeur de la file Celery", ["queue"])
celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds", "Durée des tâches Celery", ["task", "status"]
)

# --- Métriques métier (structure posée au S0, cf. ADR-S-07) ---
fanid_outbox_pending = Gauge("fanid_outbox_pending", "Événements Outbox en attente de publication")
fanid_outbox_dead = Gauge("fanid_outbox_dead", "Événements Outbox définitivement en échec (DEAD)")
fanid_idempotency_conflicts_total = Counter(
    "fanid_idempotency_conflicts_total",
    "Conflits d'idempotence détectés (clé réutilisée ou en cours)",
    ["reason"],
)
fanid_scan_total = Counter("fanid_scan_total", "Scans de billets", ["result", "reason"])
fanid_scan_duration_seconds = Histogram("fanid_scan_duration_seconds", "Durée de validation d'un scan")
fanid_purchase_total = Counter("fanid_purchase_total", "Achats", ["status"])
fanid_stock_hold_active = Gauge("fanid_stock_hold_active", "Réservations de stock actives")
fanid_totp_verification_total = Counter("fanid_totp_verification_total", "Vérifications TOTP", ["result"])


# --- Métriques métier du Sprint 1 (§5.4 du plan de sprint) ---

fanid_auth_login_total = Counter(
    "fanid_auth_login_total",
    "Tentatives de connexion par résultat",
    ["result"],
)

fanid_auth_token_refresh_total = Counter(
    "fanid_auth_token_refresh_total",
    "Rotations de jeton de rafraîchissement par résultat",
    ["result"],
)

fanid_auth_token_reuse_detected_total = Counter(
    "fanid_auth_token_reuse_detected_total",
    "Réutilisations détectées d'un jeton de rafraîchissement déjà tourné",
)

fanid_device_reset_total = Counter(
    "fanid_device_reset_total",
    "Confirmations de réinitialisation d'appareil par résultat",
    ["result"],
)

fanid_authz_denied_total = Counter(
    "fanid_authz_denied_total",
    "Refus d'autorisation par action et par rôle",
    ["action", "role"],
)

# Valeur fermée utilisée lorsque Subject.role vaut None.
AUTHZ_ROLE_ANONYMOUS = "anonymous"


class MetricsMiddleware:
    """
    Middleware RED — positionné au plus près de la vue (§2.5 Source B) pour
    mesurer une latence représentative du traitement métier, pas de la pile
    de middlewares en amont.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        route = self._route_template(request)
        http_requests_in_flight.labels(route=route).inc()
        start = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            http_requests_in_flight.labels(route=route).dec()

        duration = time.monotonic() - start
        http_requests_total.labels(method=request.method, route=route, status=response.status_code).inc()
        http_request_duration_seconds.labels(method=request.method, route=route).observe(duration)
        return response

    @staticmethod
    def _route_template(request: HttpRequest) -> str:
        match = getattr(request, "resolver_match", None)
        if match is not None and getattr(match, "route", None):
            return match.route
        return request.path
