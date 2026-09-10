from django.urls import path

from .views import (
    EventAdmissionCloseView,
    EventAdmissionOpenView,
    EventAdmissionStatusView,
    EventFinalReportView,
    EventLiveDashboardView,
    ScannerHeartbeatView,
    TicketAdmissionScanView,
)

urlpatterns = [
    path(
        "access/events/<uuid:event_id>/final-report",
        EventFinalReportView.as_view(),
        name="event-final-report",
    ),
    path(
        "access/events/<uuid:event_id>/live-dashboard",
        EventLiveDashboardView.as_view(),
        name="event-live-dashboard",
    ),
    path(
        "access/events/<uuid:event_id>/admission",
        EventAdmissionStatusView.as_view(),
        name="event-admission-status",
    ),
    path(
        "access/events/<uuid:event_id>/admission/open",
        EventAdmissionOpenView.as_view(),
        name="event-admission-open",
    ),
    path(
        "access/events/<uuid:event_id>/admission/close",
        EventAdmissionCloseView.as_view(),
        name="event-admission-close",
    ),
    path(
        "access/scanners/heartbeat",
        ScannerHeartbeatView.as_view(),
        name="scanner-heartbeat",
    ),
    path(
        "access/scans",
        TicketAdmissionScanView.as_view(),
        name="ticket-admission-scan",
    ),
]
