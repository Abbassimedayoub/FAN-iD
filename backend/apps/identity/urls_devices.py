"""
Device routes mounted under `/api/v1/devices/`.

They live separately from authentication routes so the refresh-cookie path stays
narrow and the browser does not send that cookie to device endpoints.
"""

from django.urls import path

from .views import DeviceMeView, DeviceResetConfirmView, DeviceResetRequestView

app_name = "identity_devices"

urlpatterns = [
    path("me", DeviceMeView.as_view(), name="device-me"),
    path("reset/request", DeviceResetRequestView.as_view(), name="device-reset-request"),
    path("reset/confirm", DeviceResetConfirmView.as_view(), name="device-reset-confirm"),
]
