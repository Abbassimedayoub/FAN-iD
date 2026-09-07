from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Event

from .models import EventAdmissionSession
from .serializers import TicketAdmissionScanSerializer
from .services.admission_sessions import (
    close_event_admission,
    open_event_admission,
)
from .services.admissions import admit_ticket_from_qr
from .services.live_dashboard import event_live_dashboard
from .services.scanner_presence import record_scanner_heartbeat


def _owned_event(*, request, event_id):
    return get_object_or_404(
        Event,
        pk=event_id,
        organizer__user_id=request.user.pk,
    )


def _admission_payload(*, event_id, session):
    return {
        "event_id": str(event_id),
        "is_open": session is not None,
        "opened_at": session.opened_at if session else None,
        "opened_by_id": str(session.opened_by_id) if session else None,
    }


class EventAdmissionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        _owned_event(request=request, event_id=event_id)
        session = EventAdmissionSession.objects.filter(
            event_id=event_id,
            closed_at__isnull=True,
        ).first()
        return Response(_admission_payload(event_id=event_id, session=session))


class EventAdmissionOpenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        _owned_event(request=request, event_id=event_id)
        session = open_event_admission(
            event_id=event_id,
            opened_by_id=request.user.pk,
        )
        return Response(
            _admission_payload(event_id=event_id, session=session),
        )


class EventAdmissionCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        _owned_event(request=request, event_id=event_id)
        close_event_admission(
            event_id=event_id,
            closed_by_id=request.user.pk,
        )
        return Response(_admission_payload(event_id=event_id, session=None))


class TicketAdmissionScanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TicketAdmissionScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admission = admit_ticket_from_qr(
            token=serializer.validated_data["token"],
            scanner_user_id=request.user.pk,
        )

        return Response(
            {
                "status": "ADMITTED",
                "admission_id": str(admission.id),
                "ticket_id": str(admission.ticket_id),
                "admitted_at": admission.admitted_at,
            }
        )


class EventLiveDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = _owned_event(request=request, event_id=event_id)
        return Response(event_live_dashboard(event=event))


class ScannerHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        presence = record_scanner_heartbeat(
            scanner_user_id=request.user.pk,
        )
        return Response(
            {
                "status": "ONLINE",
                "last_seen_at": presence.last_seen_at,
            }
        )
