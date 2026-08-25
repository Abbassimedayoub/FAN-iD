from django.urls import path

from .views import (
    CategoryListView,
    EventDetailView,
    EventListCreateView,
)

app_name = "catalog"

urlpatterns = [
    path(
        "categories",
        CategoryListView.as_view(),
        name="category-list",
    ),
    path(
        "events",
        EventListCreateView.as_view(),
        name="event-list-create",
    ),
    path(
        "events/<uuid:event_id>",
        EventDetailView.as_view(),
        name="event-detail",
    ),
]
