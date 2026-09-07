from django.urls import path

from .views import MyTicketsView, TicketDynamicQrView

urlpatterns = [
    path("tickets/<uuid:ticket_id>/qr", TicketDynamicQrView.as_view(), name="ticket-dynamic-qr"),
    path("tickets", MyTicketsView.as_view(), name="my-tickets"),
]
