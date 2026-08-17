"""
Routes d administration du contexte `organizing`.

Montees sous `/api/v1/admin/organizers/`.
"""

from django.urls import path

from .views import OrganizerApproveView, OrganizerRejectView, OrganizerSuspendView

app_name = "organizing_admin"

urlpatterns = [
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
]
