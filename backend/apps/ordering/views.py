from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import ReservationCreateSerializer
from .services import ReservationLine, reserve_stock


class ReservationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = reserve_stock(
            user=request.user,
            lines=[
                ReservationLine(
                    ticket_category_id=item["ticket_category_id"],
                    quantity=item["quantity"],
                )
                for item in serializer.validated_data["items"]
            ],
        )

        return Response(
            {
                "order_id": str(order.id),
                "status": order.status,
                "total_amount_cents": order.total_amount_cents,
                "hold_expires_at": order.stock_hold.expires_at,
                "lines": [
                    {
                        "ticket_category_id": str(line.ticket_category_id),
                        "label": line.label,
                        "quantity": line.quantity,
                        "unit_price_cents": line.unit_price_cents,
                    }
                    for line in order.lines.all()
                ],
            },
            status=201,
        )



class OrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("stock_hold"),
            pk=order_id,
            user=request.user,
        )

        return Response(
            {
                "order_id": str(order.id),
                "status": order.status,
                "total_amount_cents": order.total_amount_cents,
                "hold_expires_at": order.stock_hold.expires_at,
            }
        )
