from django.urls import path
from django_prometheus import exports as prometheus_exports

from .views import HealthView, ReadinessView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("health/ready", ReadinessView.as_view(), name="health-ready"),
    path("metrics", prometheus_exports.ExportToDjangoView, name="metrics"),
]
