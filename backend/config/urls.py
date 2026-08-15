"""
Routes racine. Au Sprint 0 : uniquement les 4 endpoints plateforme (§3.2 Source B).
Aucune route métier — les bounded contexts n'exposent rien avant leur sprint.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", include("django_prometheus.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.identity.urls")),
    path("api/v1/devices/", include("apps.identity.urls_devices")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
