"""
Routes d administration du contexte `organizing`.

Montees sous `/api/v1/admin/organizers/`.
"""

from django.urls import path

from .reactivation_views import (
    AdminOrganizerReactivationApproveView,
    AdminOrganizerReactivationRejectView,
    AdminOrganizerReactivationRequestView,
)
from .views import (
    AdminOrganizerCommissionAcceptView,
    AdminOrganizerCommissionNegotiationView,
    AdminOrganizerCommissionProposalView,
    AdminOrganizerDetailView,
    AdminOrganizerListView,
    OrganizerApproveView,
    OrganizerRejectView,
    OrganizerSuspendView,
)

app_name = "organizing_admin"

urlpatterns = [
    path(
        "",
        AdminOrganizerListView.as_view(),
        name="list",
    ),
    path(
        "<uuid:organizer_id>",
        AdminOrganizerDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:organizer_id>/commission-negotiation",
        AdminOrganizerCommissionNegotiationView.as_view(),
        name="commission-negotiation",
    ),
    path(
        "<uuid:organizer_id>/commission-proposals",
        AdminOrganizerCommissionProposalView.as_view(),
        name="commission-proposals",
    ),
    path(
        "<uuid:organizer_id>/commission-accept",
        AdminOrganizerCommissionAcceptView.as_view(),
        name="commission-accept",
    ),
    path(
        "<uuid:organizer_id>/approve",
        OrganizerApproveView.as_view(),
        name="approve",
    ),
    path(
        "<uuid:organizer_id>/reject",
        OrganizerRejectView.as_view(),
        name="reject",
    ),
    path(
        "<uuid:organizer_id>/suspend",
        OrganizerSuspendView.as_view(),
        name="suspend",
    ),
    path(
        "<uuid:organizer_id>/reactivation-request",
        AdminOrganizerReactivationRequestView.as_view(),
        name="reactivation-request",
    ),
    path(
        "<uuid:organizer_id>/reactivation-request/approve",
        AdminOrganizerReactivationApproveView.as_view(),
        name="reactivation-request-approve",
    ),
    path(
        "<uuid:organizer_id>/reactivation-request/reject",
        AdminOrganizerReactivationRejectView.as_view(),
        name="reactivation-request-reject",
    ),
]
