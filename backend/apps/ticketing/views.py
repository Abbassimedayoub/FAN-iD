from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket
from .serializers import TicketSerializer, TicketTransferSerializer
from .services.qr import issue_dynamic_ticket_qr
from .services.transfers import transfer_ticket


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
            Ticket.objects.only("id", "status", "qr_version"),
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


class TicketTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        serializer = TicketTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ticket = transfer_ticket(
            ticket_id=ticket_id,
            owner_user_id=request.user.pk,
            recipient_email=serializer.validated_data["recipient_email"],
        )
        return Response({"ticket": TicketSerializer(ticket).data})
