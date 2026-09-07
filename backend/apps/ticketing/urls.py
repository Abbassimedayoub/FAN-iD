from django.urls import path

from .views import MyTicketsView

urlpatterns = [
    path("tickets", MyTicketsView.as_view(), name="my-tickets"),
]
