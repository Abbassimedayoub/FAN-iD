"""
Routes du contexte `identity`, montees sous `/api/v1/auth/`.

Pas de barre oblique finale, par coherence avec `apps/core/urls.py`. Le prefixe
correspond a `REFRESH_COOKIE_PATH` : le cookie de rafraichissement n est envoye
qu aux routes d authentification, et non a chaque appel de l API.
"""

from django.urls import path

from .views import LoginView, LogoutView, PasswordChangeView, RefreshView, RegistrationView

app_name = "identity"

urlpatterns = [
    path("register", RegistrationView.as_view(), name="auth-register"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("password/change", PasswordChangeView.as_view(), name="auth-password-change"),
    path("token/refresh", RefreshView.as_view(), name="auth-refresh"),
]
