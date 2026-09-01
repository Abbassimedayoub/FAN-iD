"""
Routes racine. Au Sprint 0 : uniquement les 4 endpoints plateforme (§3.2 Source B).
Aucune route métier — les bounded contexts n'exposent rien avant leur sprint.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import config.admin_autoregister  # noqa: F401

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("django_prometheus.urls")),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/auth/", include("apps.identity.urls")),
    path("api/v1/devices/", include("apps.identity.urls_devices")),
    path("api/v1/organizers/", include("apps.organizing.urls")),
    path("api/v1/admin/organizers/", include("apps.organizing.urls_admin")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
