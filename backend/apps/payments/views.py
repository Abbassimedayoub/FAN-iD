from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateways import get_payment_gateway
from .serializers import PaymentIntentResponseSerializer
from .services import create_payment_intent



class PaymentIntentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        intent = create_payment_intent(
            order_id=order_id,
            user=request.user,
            gateway=get_payment_gateway(),
        )
        return Response(
            PaymentIntentResponseSerializer(intent).data,
            status=201,
        )
