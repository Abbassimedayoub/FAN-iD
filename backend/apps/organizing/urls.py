"""
Routes du contexte `organizing`.

Aucune barre oblique finale, par coherence avec le reste de l API.
"""

from django.urls import path

from .views import OrganizerApplyView, OrganizerMeView

app_name = "organizing"

urlpatterns = [
    path("apply", OrganizerApplyView.as_view(), name="organizer-apply"),
    path("me", OrganizerMeView.as_view(), name="organizer-me"),
]
