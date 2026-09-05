from django.urls import path

from .views import OrderStatusView, ReservationCreateView

app_name = "ordering"

urlpatterns = [
    path(
        "orders/<uuid:order_id>",
        OrderStatusView.as_view(),
        name="order-status",
    ),
    path(
        "orders/reservations",
        ReservationCreateView.as_view(),
        name="order-reservation-create",
    ),
]
