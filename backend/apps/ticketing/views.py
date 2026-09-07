from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Ticket
from .serializers import TicketSerializer


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
