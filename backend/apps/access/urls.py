from django.urls import path

from .views import (
    EventAdmissionCloseView,
    EventAdmissionOpenView,
    EventAdmissionStatusView,
    TicketAdmissionScanView,
)


urlpatterns = [
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
        "access/scans",
        TicketAdmissionScanView.as_view(),
        name="ticket-admission-scan",
    ),
]
