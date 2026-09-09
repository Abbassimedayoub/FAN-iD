from __future__ import annotations

from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import Action, ActionPermission

from .models import EventFinalReport


class AdminFinancialDashboardView(APIView):
    """
    Agrégats financiers confirmés à destination exclusive de l’Admin.

    Seuls les rapports finaux sont retenus : une vente d’un événement non
    terminé ne peut pas être affichée comme un gain définitivement acquis.
    """

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.ORGANIZER_READ

    def get(self, request: Request) -> Response:
        permission = ActionPermission()
        if not permission.has_object_permission(request, self, object()):
            self.permission_denied(
                request,
                message=permission.message,
                code=permission.code,
            )

        reports = EventFinalReport.objects.filter(
            event__organizer__isnull=False,
        )
        totals = reports.aggregate(
            confirmed_commission_cents=Sum("commission_cents"),
        )
        organizer_rows = list(
            reports.values(
                "event__organizer_id",
                "event__organizer__org_name",
            )
            .annotate(
                net_revenue_cents=Sum("net_revenue_cents"),
                completed_events_count=Count("event_id"),
            )
            .order_by(
                "-net_revenue_cents",
                "event__organizer__org_name",
            )
        )

        return Response(
            {
                "confirmed_commission_cents": int(totals["confirmed_commission_cents"] or 0),
                "organizer_count": len(organizer_rows),
                "organizers": [
                    {
                        "organizer_id": str(row["event__organizer_id"]),
                        "org_name": row["event__organizer__org_name"],
                        "net_revenue_cents": int(row["net_revenue_cents"] or 0),
                        "completed_events_count": int(row["completed_events_count"]),
                    }
                    for row in organizer_rows
                ],
            }
        )
