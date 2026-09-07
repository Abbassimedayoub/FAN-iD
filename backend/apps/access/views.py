from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TicketAdmissionScanSerializer
from .services.admissions import admit_ticket_from_qr


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
