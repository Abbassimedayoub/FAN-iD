from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket
from .serializers import TicketSerializer
from .services.qr import issue_dynamic_ticket_qr


class MyTicketsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = (
            Ticket.objects.filter(user=request.user)
            .select_related("event", "ticket_category")
            .order_by("-created_at", "-id")
        )

        return Response(
            {
                "results": TicketSerializer(tickets, many=True).data,
            }
        )


class TicketDynamicQrView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = get_object_or_404(
            Ticket.objects.only("id", "status"),
            pk=ticket_id,
            user=request.user,
        )
        qr = issue_dynamic_ticket_qr(ticket=ticket)

        return Response(
            {
                "token": qr.token,
                "expires_at": qr.expires_at,
                "refresh_after_seconds": 20,
            }
        )
