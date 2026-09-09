from django.urls import path

from .admin_dashboard_views import AdminFinancialDashboardView

app_name = "access_admin"

urlpatterns = [
    path(
        "dashboard",
        AdminFinancialDashboardView.as_view(),
        name="financial-dashboard",
    ),
]
