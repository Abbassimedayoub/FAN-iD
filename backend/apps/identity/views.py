"""
HTTP endpoints for the `identity` context.

A view validates input shape, calls a service, and translates the result into a
response. Business logic that does not belong to those responsibilities lives
in services.
"""

from __future__ import annotations

import logging
from typing import Any, cast
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.core.adapters.notifications import build_notification_sender
from apps.core.concurrency import format_etag, parse_if_match
from apps.core.exceptions import NotFoundBusinessError, PermissionBusinessError, StaleResourceError
from apps.core.http import FanIdApiRequest
from apps.core.openapi import ERROR_RESPONSE
from apps.core.outbox.publisher import publish_event

from .authentication import default_binding_service
from .authz import Action
from .constants import CLIENT_WEB, OTP_TTL_MINUTES, PASSWORD_RESET_TTL_MINUTES, SESSION_REVOKED_LOGOUT
from .events import (
    AGGREGATE_USER,
    USER_PHONE_CHANGED,
    USER_PROFILE_UPDATED,
    user_phone_changed_payload,
    user_profile_updated_payload,
)
from .models import Device, Session, User
from .permissions import ActionPermission, SelfResourcePermission, SelfUserPermission
from .serializers import (
    DeviceHistorySerializer,
    DeviceMeResponseSerializer,
    DeviceResetConfirmSerializer,
    DeviceResetRequestSerializer,
    DeviceSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneChangeConfirmSerializer,
    PhoneChangeRequestSerializer,
    ProfileUpdateSerializer,
    RefreshSerializer,
    RegistrationSerializer,
    SessionSerializer,
    StepUpConfirmSerializer,
    StepUpRequestSerializer,
    UserMeSerializer,
    UserPublicSerializer,
)
from .services.authentication import AuthenticationService, LoginCommand, RefreshCommand
from .services.device_reset import DeviceResetService
from .services.password_reset import PasswordResetService
from .services.phone_change import PhoneChangeService, clean_phone, same_phone
from .services.profile import ProfileService
from .services.registration import RegistrationService
from .services.step_up import StepUpService
from .services.tokens import TokenService
from .throttling import (
    DeviceResetAccountRateThrottle,
    LoginAccountRateThrottle,
    PasswordResetAccountRateThrottle,
    RefreshOriginRateThrottle,
    RefreshSessionRateThrottle,
    RefreshTokenRateThrottle,
)
from .tokens import TokenInvalidError


def build_authentication_service() -> AuthenticationService:
    """
    Build the authentication service through a replaceable module-level seam.

    Tests can inject an in-memory lock here without constructing a real Redis
    client inside every endpoint test.
    """
    return AuthenticationService(binding=default_binding_service())


def set_refresh_cookie(response: Response, refresh: str) -> None:
    """
    Store the refresh token in an HttpOnly cookie for web clients only.

    Cookie domain and path come from environment-backed settings. HttpOnly is
    mandatory so JavaScript cannot read the refresh token, while the narrow path
    limits where the browser sends it.
    """
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def _canonical_origin(value: str) -> str | None:
    """Return a strict scheme/authority origin or None for an invalid value."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def enforce_web_refresh_origin(request: Request) -> None:
    """Reject browser refresh requests that do not come from a trusted origin."""
    supplied = _canonical_origin(request.headers.get("Origin", ""))

    allowed = {
        canonical
        for item in settings.CSRF_TRUSTED_ORIGINS
        if (canonical := _canonical_origin(str(item))) is not None
    }

    if supplied is None or supplied not in allowed:
        raise PermissionBusinessError(
            code="CSRF_ORIGIN_DENIED",
            message="Request origin is not allowed.",
        )


class RegistrationView(APIView):
    """
    `POST /api/v1/auth/register` — create a supporter account.

    `AllowAny` is explicit because the project defaults to deny-all permissions.
    A dedicated throttle limits account enumeration. Registration does not use
    authenticated idempotency keys; case-insensitive email uniqueness instead
    guarantees that replaying the same address never creates a second account.
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
    `POST /api/v1/auth/login` — open a session.

    Rate limits apply both to the request origin and the target account. Refresh
    transport is client-specific: web receives an HttpOnly cookie, while mobile
    receives the token in the response body. The two transports never overlap.
    Login itself has no authentication classes because the caller is not yet
    authenticated.
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
                client=data["client"],
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
            )
        else:
            body["refresh"] = result.pair.refresh
            response.data = body

        return response


class RefreshView(APIView):
    """
    `POST /api/v1/auth/token/refresh` — rotate a refresh token.

    Web reads only the refresh cookie; mobile reads only the request body. The
    endpoint has no access-token authentication because refresh exists precisely
    for expired access tokens. Browser-origin checks protect cookie-backed
    refreshes, and error paths do not add transport-specific cleanup behavior.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [
        RefreshOriginRateThrottle,
        RefreshTokenRateThrottle,
        RefreshSessionRateThrottle,
    ]

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

        if is_web and (settings.REFRESH_REQUIRE_TRUSTED_ORIGIN or request.headers.get("Origin")):
            enforce_web_refresh_origin(request)

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
            )
        else:
            body["refresh"] = result.pair.refresh
            response.data = body

        return response


def clear_refresh_cookie(response: Response) -> None:
    """
    Remove the refresh cookie using the same path and domain that created it.

    This helper is used for logout and password change, not generic error paths.
    """
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


class LogoutView(APIView):
    """
    `POST /api/v1/auth/logout` — close the current session.

    The token itself identifies the session, so there is no separate resource ID
    to scope. Repeating logout is naturally rejected by authentication after the
    first revocation.
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
    `POST /api/v1/auth/password/change` — change the password and revoke all sessions.

    The current password is required so a stolen session alone cannot take over
    the account. The caller's session is revoked too and the client must log in
    again. Rate limiting is account-scoped because the caller is authenticated.
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
            # Type stubs expose an abstract user; IsAuthenticated guarantees a real account,
            # so this cast only communicates that fact to the type checker.
            user=cast(User, request.user),
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


def build_password_reset_service() -> PasswordResetService:
    """Replaceable service-construction seam for tests."""
    return PasswordResetService()


class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password/reset/request

    La réponse ne révèle jamais si l'adresse appartient à un compte.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [
        ScopedRateThrottle,
        PasswordResetAccountRateThrottle,
    ]
    throttle_scope = "password_reset_request"

    @extend_schema(
        operation_id="auth_password_reset_request",
        summary="Demander une récupération de mot de passe",
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description=("Réponse identique pour une adresse connue ou inconnue.")),
            400: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
        auth=[],
    )
    def post(
        self,
        request: Request,
    ) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        build_password_reset_service().request(email=(serializer.validated_data["email"]))

        return Response(
            {
                "message": (
                    "Si un compte FANID correspond à cette adresse, "
                    "un e-mail de récupération va être envoyé."
                ),
                "expires_in_seconds": (int(PASSWORD_RESET_TTL_MINUTES) * 60),
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password/reset/confirm

    Fonctionne soit avec le token du lien magique, soit avec email + code.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [
        ScopedRateThrottle,
    ]
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        operation_id="auth_password_reset_confirm",
        summary="Définir un nouveau mot de passe",
        request=PasswordResetConfirmSerializer,
        responses={
            204: OpenApiResponse(description=("Mot de passe réinitialisé et toutes les sessions révoquées.")),
            400: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
        auth=[],
    )
    def post(
        self,
        request: Request,
    ) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        build_password_reset_service().reset(
            token=data.get("token"),
            email=data.get("email"),
            code=data.get("code"),
            new_password=data["new_password"],
        )

        response = Response(status=status.HTTP_204_NO_CONTENT)

        clear_refresh_cookie(response)

        return response


def build_step_up_service() -> StepUpService:
    """Build the step-up service through a replaceable test seam."""
    return StepUpService(sender=build_notification_sender())


class StepUpRequestView(APIView):
    """POST /api/v1/auth/step-up/request."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "step_up_request"

    @extend_schema(
        operation_id="auth_step_up_request",
        summary="Demander un code de verification renforcee",
        request=StepUpRequestSerializer,
        responses={
            200: OpenApiResponse(description="Challenge STEP_UP cree et code envoye."),
            401: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def post(self, request: FanIdApiRequest) -> Response:
        serializer = StepUpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = build_step_up_service().request(
            user=cast(User, request.user),
            session_id=request.session_id,
        )

        return Response(
            {
                "challenge_id": str(result.challenge_id),
                "expires_in_seconds": int(OTP_TTL_MINUTES) * 60,
            },
            status=status.HTTP_200_OK,
        )


class StepUpConfirmView(APIView):
    """POST /api/v1/auth/step-up/confirm."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "step_up_confirm"

    @extend_schema(
        operation_id="auth_step_up_confirm",
        summary="Confirmer la verification renforcee",
        request=StepUpConfirmSerializer,
        responses={
            204: OpenApiResponse(description="Session courante elevee au niveau STEP_UP."),
            400: OpenApiResponse(
                description=("OTP_INVALID — challenge inconnu, expire, consomme " "ou code incorrect")
            ),
            401: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def post(self, request: FanIdApiRequest) -> Response:
        serializer = StepUpConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        build_step_up_service().confirm(
            user=cast(User, request.user),
            session_id=request.session_id,
            challenge_id=serializer.validated_data["challenge_id"],
            code=serializer.validated_data["code"],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


def build_device_reset_service() -> DeviceResetService:
    """Build the device-reset service through the test replacement seam."""
    return DeviceResetService(binding=default_binding_service(), sender=build_notification_sender())


class DeviceResetRequestView(APIView):
    """
    `POST /api/v1/devices/reset/request` — demande un code de deliaison.

    **Anonyme, et ce n est pas un oubli** (ADR-S1-04). `IsAuthenticated`, que le
    plan §3.3 prevoyait, est incompatible avec le parcours §1.1 : `DEVICE_LOCKED`
    n emet aucun jeton, donc l utilisateur verrouille dehors ne peut appeler
    aucune route authentifiee. La preuve, ici, ce sont les identifiants.

    **La reponse est identique dans tous les cas** — compte inconnu, mot de
    passe faux, succes. Le `challenge_id` est toujours present, fabrique quand
    les identifiants sont faux : sa presence ne doit jamais dire si le compte
    existe. `expires_in_seconds` est une constante, donc muet lui aussi.

    Deux axes de quota. Par COMPTE (3/h) : c est lui qui empeche de noyer la
    boite d une personne ciblee depuis mille adresses. Par ORIGINE (20/h) :
    simple garde-fou anti-inondation, volontairement large pour ne pas bloquer
    un NAT d operateur ou le wifi d un stade.
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [ScopedRateThrottle, DeviceResetAccountRateThrottle]
    throttle_scope = "device_reset_request"

    @extend_schema(
        operation_id="device_reset_request",
        summary="Demander un code de reinitialisation d appareil",
        request=DeviceResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Reponse identique que le compte existe ou non. `challenge_id` est "
                    "toujours present ; il ne designe un defi reel que si les identifiants "
                    "etaient valides."
                )
            ),
            400: OpenApiResponse(description="Corps invalide"),
            429: OpenApiResponse(description="Trop de demandes"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = DeviceResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = build_device_reset_service().request(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        return Response(
            {
                "challenge_id": str(result.challenge_id),
                "expires_in_seconds": int(OTP_TTL_MINUTES) * 60,
            },
            status=status.HTTP_200_OK,
        )


class DeviceResetConfirmView(APIView):
    """
    `POST /api/v1/devices/reset/confirm` — verifie le code et delie l appareil.

    Renvoie `204`. **Aucun jeton n est emis** : la preuve apportee ici vaut pour
    cette action et rien d autre. L utilisateur se reconnecte par
    `POST /auth/login`, et c est cette connexion qui liera le nouvel appareil,
    par le chemin deja eprouve du lot S1-A.6c.

    `Session.auth_level` n est pas eleve : il n existe aucune session a elever
    au moment ou cette route s execute. Le `[COUPE-B]` du §2.4 est donc sans
    objet dans ce sprint (ADR-S1-04).
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_reset_confirm"

    @extend_schema(
        operation_id="device_reset_confirm",
        summary="Confirmer la reinitialisation avec le code recu",
        request=DeviceResetConfirmSerializer,
        responses={
            204: OpenApiResponse(description="Appareil delie, sessions revoquees, defi consomme"),
            400: OpenApiResponse(
                description="OTP_INVALID — defi introuvable, expire, consomme, ou code faux"
            ),
            429: OpenApiResponse(description="OTP_MAX_ATTEMPTS — cinq tentatives atteintes, defi consomme"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = DeviceResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        build_device_reset_service().confirm(
            challenge_id=serializer.validated_data["challenge_id"],
            code=serializer.validated_data["code"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Account self-service
# ---------------------------------------------------------------------------

logger = logging.getLogger("fanid.identity")


def build_profile_service() -> ProfileService:
    """Build the profile service through a replaceable test seam."""
    return ProfileService()


def build_phone_change_service() -> PhoneChangeService:
    """Build the phone-change service."""
    return PhoneChangeService(
        sender=build_notification_sender(),
    )


class MeView(APIView):
    """GET/PATCH /api/v1/auth/me."""

    permission_classes = [IsAuthenticated, SelfUserPermission]
    read_action = Action.USER_READ_SELF
    write_action = Action.USER_UPDATE_SELF

    # Reads use the general authenticated quota while writes use the dedicated profile-update scope.
    throttle_scope = "profile_update"

    def get_throttles(self) -> list[Any]:
        if self.request.method in SAFE_METHODS:
            return [UserRateThrottle()]
        return [ScopedRateThrottle()]

    def get_object(self, request: Request) -> User:
        user = User.objects.select_related("role").get(pk=request.user.pk)
        self.check_object_permissions(request, user)
        return user

    @staticmethod
    def response_for(user: User) -> Response:
        response = Response(
            UserMeSerializer(user).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(user.version)
        return response

    @extend_schema(
        operation_id="auth_me_get",
        summary="Lire le profil du compte courant",
        responses={
            200: UserMeSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request) -> Response:
        return self.response_for(self.get_object(request))

    @extend_schema(
        operation_id="auth_me_patch",
        summary="Modifier le profil du compte courant",
        request=ProfileUpdateSerializer,
        responses={
            200: UserMeSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            412: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def patch(self, request: Request) -> Response:
        user = self.get_object(request)
        expected_version = parse_if_match(request.headers.get("If-Match"))

        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        changes = dict(serializer.validated_data)

        if "phone" in changes:
            role_name = str(user.role.name)
            current_phone = str(
                user.phone or "",
            ).strip()
            requested_phone = str(
                changes.get("phone") or "",
            ).strip()

            if role_name == "SCANNER" and user.must_change_password:
                raise ValidationError(
                    {
                        "phone": [
                            (
                                "SCANNER_PASSWORD_CHANGE_REQUIRED_BEFORE_PHONE: "
                                "Vous devez d'abord remplacer votre mot de passe temporaire."
                            )
                        ]
                    }
                )

            if current_phone:
                if requested_phone and same_phone(
                    current_phone,
                    requested_phone,
                ):
                    changes.pop(
                        "phone",
                        None,
                    )
                else:
                    raise ValidationError(
                        {
                            "phone": [
                                (
                                    "PHONE_CHANGE_REQUIRES_VERIFICATION: "
                                    "Un code de validation est obligatoire "
                                    "pour remplacer le numéro actuel."
                                )
                            ]
                        }
                    )
            elif not requested_phone:
                if role_name == "SCANNER":
                    raise ValidationError(
                        {"phone": ["Le numéro de téléphone est obligatoire " "pour un compte scanner."]}
                    )

                changes.pop(
                    "phone",
                    None,
                )
            else:
                try:
                    changes["phone"] = clean_phone(
                        requested_phone,
                    )
                except ValueError as exc:
                    raise ValidationError(
                        {
                            "phone": [
                                str(exc),
                            ]
                        }
                    ) from exc

        # An empty PATCH, or one containing no effective contract fields, is a no-op.
        # Still verify the optimistic-lock precondition without creating a new version.
        if not changes:
            if expected_version != user.version:
                raise StaleResourceError(details={"current_version": user.version})
            return self.response_for(user)

        with transaction.atomic():
            user = build_profile_service().update(
                user_id=user.pk,
                expected_version=expected_version,
                changes=changes,
            )

            publish_event(
                event_type=USER_PROFILE_UPDATED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=user_profile_updated_payload(
                    changed_fields=list(changes.keys()),
                ),
            )

            if "phone" in changes:
                publish_event(
                    event_type=USER_PHONE_CHANGED,
                    aggregate_type=AGGREGATE_USER,
                    aggregate_id=user.pk,
                    actor_id=user.pk,
                    payload=user_phone_changed_payload(
                        first_record=True,
                    ),
                )

        return self.response_for(user)


class SessionListView(APIView):
    """GET /api/v1/auth/sessions — active sessions for the current subject only."""

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.SESSION_LIST_SELF
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sessions_list"

    def get_queryset(self):
        user = cast(User, self.request.user)
        return Session.objects.for_user(user).active().select_related("device").order_by("-issued_at")

    @extend_schema(
        operation_id="auth_sessions_list",
        summary="Lister les sessions actives du compte courant",
        responses={
            200: SessionSerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request) -> Response:
        sessions = self.get_queryset()
        serializer = SessionSerializer(
            sessions,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class SessionRevokeView(APIView):
    """DELETE /api/v1/auth/sessions/{id} — self-service session revocation."""

    permission_classes = [IsAuthenticated, SelfResourcePermission]
    required_action = Action.SESSION_REVOKE_SELF
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "session_revoke"

    def get_object(self, request: Request, session_id: Any) -> Session:
        # Scope by owner before lookup so a 403 cannot reveal another account's session.
        session = Session.objects.for_user(cast(User, request.user)).filter(pk=session_id).first()
        if session is None:
            raise NotFoundBusinessError()

        self.check_object_permissions(request, session)
        return session

    @extend_schema(
        operation_id="auth_session_revoke",
        summary="Revoquer une session du compte courant",
        request=None,
        responses={
            204: OpenApiResponse(description="Session revoquee."),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def delete(self, request: Request, session_id: Any) -> Response:
        session = self.get_object(request, session_id)

        TokenService.revoke_session(
            session,
            SESSION_REVOKED_LOGOUT,
        )

        logger.info(
            "auth.session.revoked",
            extra={
                "session_id": str(session.pk),
                "reason": SESSION_REVOKED_LOGOUT,
            },
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceMeView(APIView):
    """GET /api/v1/devices/me — active device and recent device history."""

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.DEVICE_LIST_SELF
    throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        user = cast(User, self.request.user)
        return Device.objects.for_user(user)

    @extend_schema(
        operation_id="devices_me_get",
        summary="Lire l appareil actif et l historique recent",
        responses={
            200: DeviceMeResponseSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request) -> Response:
        queryset = self.get_queryset()

        active = queryset.active().first()
        history = list(queryset.revoked().order_by("-revoked_at")[:20])

        return Response(
            {
                "active": (DeviceHistorySerializer(active).data if active is not None else None),
                "history": DeviceHistorySerializer(history, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class PhoneChangeRequestView(APIView):
    """
    Request an OTP before replacing an already-registered phone number.

    The old number remains the only persisted value until confirmation succeeds.
    """

    permission_classes = [
        IsAuthenticated,
        SelfUserPermission,
    ]
    write_action = Action.USER_UPDATE_SELF
    throttle_classes = [
        ScopedRateThrottle,
    ]
    throttle_scope = "profile_update"

    def get_user(
        self,
        request: Request,
    ) -> User:
        user = User.objects.select_related(
            "role",
        ).get(pk=request.user.pk)
        self.check_object_permissions(
            request,
            user,
        )
        return user

    @extend_schema(
        operation_id="auth_phone_change_request",
        summary=("Demander le code de changement de téléphone"),
        request=PhoneChangeRequestSerializer,
        responses={
            200: OpenApiResponse(description=("Challenge envoyé par e-mail")),
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: FanIdApiRequest,
    ) -> Response:
        user = self.get_user(
            request,
        )

        if str(user.role.name) == "SCANNER" and user.must_change_password:
            raise ValidationError(
                {
                    "phone": [
                        (
                            "SCANNER_PASSWORD_CHANGE_REQUIRED_BEFORE_PHONE: "
                            "Vous devez d'abord remplacer votre mot de passe temporaire."
                        )
                    ]
                }
            )

        current_phone = str(
            user.phone or "",
        ).strip()

        if not current_phone:
            raise ValidationError(
                {
                    "phone": [
                        (
                            "PHONE_NOT_REGISTERED: "
                            "Aucun numéro actuel n'est enregistré. "
                            "Le premier numéro doit être ajouté depuis le profil."
                        )
                    ]
                }
            )

        serializer = PhoneChangeRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        target_phone = serializer.validated_data["phone"]

        if same_phone(
            current_phone,
            target_phone,
        ):
            raise ValidationError({"phone": ["Le nouveau numéro doit être " "différent du numéro actuel."]})

        result = build_phone_change_service().request(
            user=user,
            session_id=request.session_id,
            phone=target_phone,
        )

        return Response(
            {
                "challenge_id": str(
                    result.challenge_id,
                ),
                "expires_in_seconds": (
                    int(
                        OTP_TTL_MINUTES,
                    )
                    * 60
                ),
            },
            status=status.HTTP_200_OK,
        )


class PhoneChangeConfirmView(APIView):
    """Validate the OTP and atomically replace the phone number."""

    permission_classes = [
        IsAuthenticated,
        SelfUserPermission,
    ]
    write_action = Action.USER_UPDATE_SELF
    throttle_classes = [
        ScopedRateThrottle,
    ]
    throttle_scope = "profile_update"

    def get_user(
        self,
        request: Request,
    ) -> User:
        user = User.objects.select_related(
            "role",
        ).get(pk=request.user.pk)
        self.check_object_permissions(
            request,
            user,
        )
        return user

    @extend_schema(
        operation_id="auth_phone_change_confirm",
        summary=("Confirmer le changement de téléphone"),
        request=PhoneChangeConfirmSerializer,
        responses={
            200: UserMeSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: FanIdApiRequest,
    ) -> Response:
        user = self.get_user(
            request,
        )

        serializer = PhoneChangeConfirmSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        result = build_phone_change_service().confirm(
            user=user,
            session_id=request.session_id,
            challenge_id=(serializer.validated_data["challenge_id"]),
            phone=(serializer.validated_data["phone"]),
            code=(serializer.validated_data["code"]),
        )

        response = Response(
            UserMeSerializer(
                result.user,
            ).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(
            result.user.version,
        )
        return response
