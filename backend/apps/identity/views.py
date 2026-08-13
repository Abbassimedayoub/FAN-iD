"""
Points de terminaison HTTP du contexte `identity`.

Une vue ne fait que trois choses : valider la forme, appeler un service,
traduire le resultat en reponse. Toute logique qui ne rentre pas dans ces trois
lignes appartient a un service.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import RegistrationSerializer, UserPublicSerializer
from .services.registration import RegistrationService


class RegistrationView(APIView):
    """
    `POST /api/v1/auth/register` — creation d un compte supporter.

    **`AllowAny` explicite.** Le defaut du projet est desormais `DenyAll` : une
    vue sans politique est refusee. Cette ligne est donc obligatoire, et c est
    exactement l effet recherche — l ouverture au public d un point de
    terminaison devient une decision ecrite, visible en revue de code.

    **Limitation de debit dediee.** Le seuil borne l enumeration d adresses
    rendue possible par la reponse `EMAIL_ALREADY_EXISTS` : la divulgation n est
    pas supprimee, elle est rendue couteuse (3/h/IP, plan §3.3).

    **Pas d idempotence par cle.** `IdempotencyMiddleware` exige un utilisateur
    authentifie ; l inscription est anonyme par nature. Son idempotence vient de
    l unicite `citext` de l adresse : rejouer la meme requete renvoie 400
    `EMAIL_ALREADY_EXISTS`, jamais un second compte (ADR-S1-02).
    """

    permission_classes = [AllowAny]
    # Aucune authentification tentee : `SessionAuthentication` imposerait un
    # jeton CSRF des lors qu un cookie de session traine dans le navigateur.
    authentication_classes: list[Any] = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        operation_id="auth_register",
        summary="Creer un compte supporter",
        request=RegistrationSerializer,
        responses={
            201: UserPublicSerializer,
            400: OpenApiResponse(
                description=(
                    "Donnees invalides, age insuffisant, CGU refusees, "
                    "ou adresse deja inscrite (EMAIL_ALREADY_EXISTS)"
                )
            ),
            429: OpenApiResponse(description="Trop de tentatives d inscription"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = RegistrationService.register(RegistrationService.as_command(serializer.validated_data))

        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)
