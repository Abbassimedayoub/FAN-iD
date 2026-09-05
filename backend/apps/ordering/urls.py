from django.urls import path

from .views import ReservationCreateView

app_name = "ordering"

urlpatterns = [
    path(
        "orders/reservations",
        ReservationCreateView.as_view(),
        name="order-reservation-create",
    ),
]
