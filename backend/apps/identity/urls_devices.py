"""
Routes appareils, montees sous `/api/v1/devices/`.

Module distinct de `urls.py` parce que le prefixe l est : `urls.py` sert
`/api/v1/auth/`, qui correspond a `REFRESH_COOKIE_PATH`. Melanger les deux
ferait envoyer le cookie de rafraichissement aux routes appareils, sans aucune
raison de le faire.
"""

from django.urls import path

from .views import DeviceResetConfirmView, DeviceResetRequestView

app_name = "identity_devices"

urlpatterns = [
    path("reset/request", DeviceResetRequestView.as_view(), name="device-reset-request"),
    path("reset/confirm", DeviceResetConfirmView.as_view(), name="device-reset-confirm"),
]
