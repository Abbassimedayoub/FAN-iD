from django.urls import path

from .views import TicketAdmissionScanView


urlpatterns = [
    path("access/scans", TicketAdmissionScanView.as_view(), name="ticket-admission-scan"),
]
