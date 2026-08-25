from django.urls import path

from .views import (
    CategoryListView,
    EventArchiveView,
    EventDetailView,
    EventImageView,
    EventListCreateView,
    EventPublishView,
    LocalStorageMediaView,
    TicketCategoryDetailView,
    TicketCategoryListCreateView,
)

app_name = "catalog"

urlpatterns = [
    path(
        "storage/local/<str:token>",
        LocalStorageMediaView.as_view(),
        name="local-storage-media",
    ),
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
        "events/<uuid:event_id>/archive",
        EventArchiveView.as_view(),
        name="event-archive",
    ),
    path(
        "events/<uuid:event_id>/image",
        EventImageView.as_view(),
        name="event-image",
    ),
    path(
        "events/<uuid:event_id>/publish",
        EventPublishView.as_view(),
        name="event-publish",
    ),
    path(
        (
            "events/<uuid:event_id>/"
            "ticket-categories"
        ),
        TicketCategoryListCreateView.as_view(),
        name="ticket-category-list-create",
    ),
    path(
        (
            "events/<uuid:event_id>/"
            "ticket-categories/"
            "<uuid:ticket_category_id>"
        ),
        TicketCategoryDetailView.as_view(),
        name="ticket-category-detail",
    ),
    path(
        "events/<uuid:event_id>",
        EventDetailView.as_view(),
        name="event-detail",
    ),
]
