"""
Points de terminaison HTTP du contexte `identity`.

Une vue ne fait que trois choses : valider la forme, appeler un service,
traduire le resultat en reponse. Toute logique qui ne rentre pas dans ces trois
lignes appartient a un service.
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.http import FanIdApiRequest

from .authentication import default_binding_service
from .constants import CLIENT_WEB
from .models import User
from .serializers import (
    DeviceSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    RefreshSerializer,
    RegistrationSerializer,
    UserPublicSerializer,
)
from .services.authentication import AuthenticationService, LoginCommand, RefreshCommand
from .services.registration import RegistrationService
from .throttling import LoginAccountRateThrottle, RefreshSessionRateThrottle
from .tokens import TokenInvalidError


def build_authentication_service() -> AuthenticationService:
    """
    Assemble le service de connexion.

    Fonction de module plutot qu appel direct dans la vue : c est le seul point
    que les tests ont besoin de remplacer pour injecter un verrou en memoire a
    la place de Redis. Une construction en dur dans `post()` obligerait a
    corriger un client Redis reel dans chaque test de bout en bout.
    """
    return AuthenticationService(binding=default_binding_service())


def set_refresh_cookie(response: Response, refresh: str, expires_at: Any) -> None:
    """
    Depose le refresh dans un cookie HttpOnly — chemin web uniquement.

    Tout est pilote par l environnement (§70) : aucun domaine n est ecrit en
    dur. `REFRESH_COOKIE_DOMAIN` vide donne un cookie lie a l hote, qui est le
    bon defaut. `HttpOnly` n est PAS configurable : un refresh lisible en
    JavaScript annulerait l interet du dispositif.

    `path` limite l envoi aux routes d authentification : le cookie ne part donc
    pas avec chaque appel de l API, ce qui reduit d autant sa surface
    d exposition.
    """
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        expires=expires_at,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


class RegistrationView(APIView):
    """
    `POST /api/v1/auth/register` — creation d un compte supporter.

    **`AllowAny` explicite.** Le defaut du projet est desormais `DenyAll` : une
    vue sans politique est refusee. Cette ligne est donc obligatoire, et c est
    exactement l effet recherche — l ouverture au public d un point de
    terminaison devient une decision ecrite, visible en revue de code, au lieu
    d etre l etat par defaut de tout ce qu on oublie de configurer.

    **Limitation de debit dediee.** `AnonRateThrottle` (60/min) est calibre pour
    de la lecture ; l inscription merite bien plus strict. Le seuil dedie borne
    l enumeration d adresses rendue possible par la reponse
    `EMAIL_ALREADY_EXISTS` : la divulgation n est pas supprimee, elle est rendue
    couteuse (3 tentatives par heure et par adresse IP, plan §3.3).

    **Pas d idempotence par cle.** `IdempotencyMiddleware` exige un utilisateur
    authentifie — la cle est scopee par compte, faute de quoi deux clients
    partageant la meme cle se voleraient leurs reponses. L inscription est
    anonyme par nature : elle ne peut donc pas en beneficier. Son idempotence
    vient d ailleurs, de l unicite `citext` de l adresse : rejouer la meme
    requete renvoie 400 `EMAIL_ALREADY_EXISTS`, jamais un second compte. Ce
    n est pas equivalent — le client ne recupere pas la reponse d origine —
    mais l invariant qui compte, « un seul compte par adresse », tient.
    """

    permission_classes = [AllowAny]
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

        return Response(
            UserPublicSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    `POST /api/v1/auth/login` — ouverture de session.

    **Deux axes de limitation, simultanement** (plan §3.3). `ScopedRateThrottle`
    borne l origine — 5 par minute et par adresse IP. `LoginAccountRateThrottle`
    borne la CIBLE — 10 par heure et par compte. Le second est indispensable :
    sans lui, un attaquant disposant de mille adresses IP dispose de mille fois
    le quota sur le compte qu il vise.

    **Le transport du refresh est decide par le client** (`client: web|mobile`).
    Web : cookie HttpOnly, et le jeton n apparait PAS dans le corps. Mobile :
    corps de reponse, et aucun cookie n est pose. Les deux ne se cumulent
    jamais — un refresh present dans le corps est lisible en JavaScript, et le
    cookie HttpOnly ne protegerait alors plus rien.

    `authentication_classes = []` : une connexion n a par definition aucun
    appelant authentifie a resoudre, et `SessionAuthentication` imposerait un
    jeton CSRF des lors qu un cookie de session traine dans le navigateur.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [ScopedRateThrottle, LoginAccountRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        operation_id="auth_login",
        summary="Ouvrir une session",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Session ouverte. `refresh` n est present que pour "
                    "`client=mobile` ; pour `client=web` il est depose "
                    "dans un cookie HttpOnly."
                )
            ),
            400: OpenApiResponse(description="Corps invalide"),
            401: OpenApiResponse(
                description=("INVALID_CREDENTIALS — adresse, mot de passe ou " "compte inactif")
            ),
            403: OpenApiResponse(description="DEVICE_LOCKED — un autre appareil est deja lie"),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = build_authentication_service().login(
            LoginCommand(
                email=data["email"],
                password=data["password"],
                fingerprint=data.get("fingerprint") or None,
                platform=data.get("platform") or None,
                label=data.get("label") or "",
                ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
        )

        body: dict[str, Any] = {
            "access": result.pair.access,
            "user": UserPublicSerializer(result.user).data,
            "device": (DeviceSerializer(result.device).data if result.device is not None else None),
        }

        response = Response(body, status=status.HTTP_200_OK)

        if data["client"] == CLIENT_WEB:
            set_refresh_cookie(
                response,
                result.pair.refresh,
                result.pair.refresh_expires_at,
            )
        else:
            body["refresh"] = result.pair.refresh
            response.data = body

        return response


class RefreshView(APIView):
    """
    `POST /api/v1/auth/token/refresh` — rotation du jeton de rafraichissement.

    **La source de lecture est celle que le client declare, et elle seule.**
    `client=web` lit le cookie et ne regarde pas le corps ; `client=mobile` lit
    le corps et ne regarde pas le cookie. Essayer une source puis retomber sur
    l autre serait plus souple et reintroduirait exactement le cumul que le lot
    S1-A.6c a ferme : un jeton accepte depuis deux transports annule la
    protection que le cookie HttpOnly est cense apporter.

    `authentication_classes = []` : l access est probablement EXPIRE — c est la
    raison meme de l appel. Exiger une authentification ici rendrait le
    rafraichissement impossible au moment ou il sert.

    **La protection CSRF repose sur `SameSite=Strict`** (pose au lot S1-A.6c).
    Le navigateur joint le cookie automatiquement : sans cet attribut, une page
    tierce pourrait declencher une rotation a l insu de l utilisateur. Elle
    n en lirait pas le resultat, mais elle le ferait DECONNECTER, puisque la
    rotation invalide le jeton que son onglet legitime detient encore.

    Le cookie n est PAS efface sur un refus. Le jeton est deja mort cote
    serveur ; brancher une suppression de cookie sur le chemin d erreur ferait
    entrer une preoccupation de transport dans le gestionnaire d exception,
    pour un gain nul.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [RefreshSessionRateThrottle]

    @extend_schema(
        operation_id="auth_refresh",
        summary="Tourner le jeton de rafraichissement",
        request=RefreshSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Nouvelle paire. `refresh` n est present que pour "
                    "`client=mobile` ; pour `client=web` il remplace le "
                    "cookie HttpOnly."
                )
            ),
            400: OpenApiResponse(description="Corps invalide"),
            401: OpenApiResponse(
                description=(
                    "TOKEN_INVALID, TOKEN_EXPIRED, TOKEN_REUSE_DETECTED "
                    "(famille revoquee) ou DEVICE_MISMATCH"
                )
            ),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        is_web = data["client"] == CLIENT_WEB

        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME) if is_web else data.get("refresh")

        if not raw:
            raise TokenInvalidError()

        result = build_authentication_service().refresh(
            RefreshCommand(
                refresh=raw,
                fingerprint=data.get("fingerprint") or None,
            )
        )

        body: dict[str, Any] = {
            "access": result.pair.access,
            "user": UserPublicSerializer(result.user).data,
            "device": (DeviceSerializer(result.device).data if result.device is not None else None),
        }

        response = Response(body, status=status.HTTP_200_OK)

        if is_web:
            set_refresh_cookie(
                response,
                result.pair.refresh,
                result.pair.refresh_expires_at,
            )
        else:
            body["refresh"] = result.pair.refresh
            response.data = body

        return response


def clear_refresh_cookie(response: Response) -> None:
    """
    Retire le cookie de rafraichissement.

    Le chemin et le domaine DOIVENT etre ceux qui ont servi a le poser : un
    `delete_cookie` sur un autre chemin depose un second cookie vide a cote de
    l original, qui continue tranquillement d exister.

    Appele sur la deconnexion et le changement de mot de passe — pas sur les
    chemins d erreur, ou le jeton est deja mort cote serveur et ou brancher une
    suppression ferait entrer le transport dans le gestionnaire d exception.
    """
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


class LogoutView(APIView):
    """
    `POST /api/v1/auth/logout` — ferme la session courante.

    `IsAuthenticated` et non une permission « self » : il n y a aucun
    identifiant de ressource dans la requete. La session fermee est celle que
    porte le jeton presente, donc l appartenance est STRUCTURELLE — le client
    n a aucun moyen de designer la session d autrui, et une regle de perimetre
    n aurait rien a comparer.

    Renvoie `204` sans corps. Un second appel renvoie `401` : la session est
    deja revoquee et l authentification la refuse. C est le comportement
    attendu et sans double effet (ADR-S1-03).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "logout"

    @extend_schema(
        operation_id="auth_logout",
        summary="Fermer la session courante",
        request=None,
        responses={
            204: OpenApiResponse(description="Session revoquee, cookie de rafraichissement retire"),
            401: OpenApiResponse(description="Jeton absent, invalide, ou session deja revoquee"),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
    )
    def post(self, request: FanIdApiRequest) -> Response:
        build_authentication_service().logout(session_id=request.session_id)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class PasswordChangeView(APIView):
    """
    `POST /api/v1/auth/password/change` — change le mot de passe et deconnecte
    partout.

    Le mot de passe actuel est exige : sans lui, un jeton vole suffirait a
    verrouiller le compte de sa victime, ce qui transformerait un vol de session
    en prise de controle definitive.

    Toutes les sessions tombent, **y compris celle de l appelant** : le client
    doit se reconnecter. `204` sans corps, cookie de rafraichissement retire.

    Le quota de 5/h porte sur le COMPTE et non sur l adresse IP —
    `ScopedRateThrottle` se cale sur la cle primaire des lors que l appelant est
    authentifie, ce qui est le bon axe ici, contrairement a la connexion ou il
    ne l etait pas encore.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    @extend_schema(
        operation_id="auth_password_change",
        summary="Changer le mot de passe",
        request=PasswordChangeSerializer,
        responses={
            204: OpenApiResponse(
                description="Mot de passe change. Toutes les sessions sont revoquees, reconnexion requise."
            ),
            400: OpenApiResponse(
                description="VALIDATION_ERROR — mot de passe actuel faux, nouveau identique, ou trop faible"
            ),
            401: OpenApiResponse(description="Non authentifie"),
            429: OpenApiResponse(description="Trop de tentatives"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        build_authentication_service().change_password(
            # `request.user` est type comme un utilisateur abstrait par les
            # stubs ; `IsAuthenticated` garantit deja qu il s agit d un compte
            # reel, la conversion ne fait que le dire au verificateur.
            user=cast(User, request.user),
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response
