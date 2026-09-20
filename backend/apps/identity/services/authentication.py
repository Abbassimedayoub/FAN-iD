"""
`AuthenticationService` owns login ordering and session authentication flows.

Credential verification and account state checks happen before device-lock
checks so a locked account cannot become an account-existence oracle. Unknown
addresses, wrong passwords, and inactive accounts deliberately share the same
public failure shape.

Unknown addresses also perform a decoy password check so response timing remains
comparable to real password verification rather than exposing existence through
a fast failure path.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.observability.metrics import fanid_auth_login_total, fanid_auth_token_refresh_total
from apps.core.outbox.publisher import publish_event

from ..constants import (
    CLIENT_WEB,
    SESSION_REVOKED_LOGOUT,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_REPLACED,
)
from ..events import (
    AGGREGATE_USER,
    USER_LOGGED_IN,
    USER_PASSWORD_CHANGED,
    user_logged_in_payload,
    user_password_changed_payload,
)
from ..exceptions import (
    DeviceLockedError,
    DeviceMismatchError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    PasswordUnchangedError,
)
from ..models import Device, Session, User
from ..tokens import TokenExpiredError, TokenInvalidError, TokenReuseDetectedError, TokenType, decode_token
from .devices import DeviceBindingService
from .tokens import IssuedPair, TokenService

logger = logging.getLogger("fanid.identity")


@functools.lru_cache(maxsize=1)
def _decoy_hash() -> str:
    """
    Process-wide cached decoy hash used to equalize unknown-account timing.

    The random source value has no usable corresponding password. Cache the
    expensive hash so rejected attempts do not create unnecessary CPU work.
    """
    return make_password(secrets.token_urlsafe(32))


@dataclasses.dataclass(frozen=True, slots=True)
class LoginCommand:
    """
    Login service input.

    `fingerprint` is optional because browser logins do not bind a device. The
    device lock applies only when a client supplies a fingerprint.
    """

    email: str
    password: str
    client: str | None = None
    fingerprint: str | None = None
    platform: str | None = None
    label: str = ""
    ip: str | None = None
    user_agent: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    device: Device | None
    pair: IssuedPair


@dataclasses.dataclass(frozen=True, slots=True)
class RefreshCommand:
    """
    Refresh service input.

    A fingerprint is required only when the session is bound to a device.
    Browser sessions and exempt roles therefore do not need to invent one.
    """

    refresh: str
    fingerprint: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class RefreshResult:
    user: User
    device: Device | None
    pair: IssuedPair


class AuthenticationService:
    """Authenticate credentials, then device binding, then token issuance."""

    def __init__(self, binding: DeviceBindingService) -> None:
        self._binding = binding

    def login(self, command: LoginCommand) -> LoginResult:
        """Open a session after validating credentials and device constraints in order."""
        user = self._verify_credentials(command)

        try:
            with transaction.atomic():
                # Serialize concurrent web logins for the same account so only one new web
                # session wins.
                if command.client == CLIENT_WEB or user.must_change_password:
                    user = User.objects.select_for_update().select_related("role").get(pk=user.pk)

                if command.client == CLIENT_WEB:
                    replaced_at = timezone.now()
                    Session.objects.filter(
                        user=user,
                        revoked_at__isnull=True,
                    ).filter(Q(client=CLIENT_WEB) | Q(client__isnull=True, device__isnull=True)).update(
                        revoked_at=replaced_at,
                        revoked_reason=SESSION_REVOKED_REPLACED,
                    )

                if user.must_change_password:
                    if user.temporary_password_used_at is not None:
                        logger.info(
                            "auth.login.failed",
                            extra={
                                "reason": ("temporary_password_already_used"),
                            },
                        )
                        fanid_auth_login_total.labels(
                            result="bad_credentials",
                        ).inc()
                        raise InvalidCredentialsError()

                if (
                    user.must_change_password
                    and user.temporary_password_expires_at is not None
                    and user.temporary_password_expires_at <= timezone.now()
                ):
                    logger.info(
                        "auth.login.failed",
                        extra={
                            "reason": ("temporary_password_expired"),
                        },
                    )

                    fanid_auth_login_total.labels(
                        result="bad_credentials",
                    ).inc()

                    raise InvalidCredentialsError()

                device = self._bind_device(
                    user,
                    command,
                )

                pair = TokenService.issue_pair(
                    user=user,
                    device=device,
                    client=command.client,
                    ip=command.ip,
                    user_agent=command.user_agent,
                )

                if user.must_change_password:
                    user.temporary_password_used_at = timezone.now()
                    user.save(
                        update_fields=[
                            "temporary_password_used_at",
                        ],
                    )

                publish_event(
                    event_type=USER_LOGGED_IN,
                    aggregate_type=AGGREGATE_USER,
                    aggregate_id=user.pk,
                    actor_id=user.pk,
                    payload=user_logged_in_payload(
                        role_name=user.role.name,
                        device_bound=device is not None,
                    ),
                )
        except DeviceLockedError:
            fanid_auth_login_total.labels(result="device_locked").inc()
            raise

        fanid_auth_login_total.labels(result="success").inc()

        # Do not log email, fingerprint, or tokens. The correlation ID links this entry
        # to request context when diagnostics need more information.
        logger.info(
            "auth.login.success",
            extra={"session_id": str(pair.session.pk), "device_bound": device is not None},
        )
        return LoginResult(user=user, device=device, pair=pair)

    # -- step 1: credentials -------------------------------------------------

    def _verify_credentials(self, command: LoginCommand) -> User:
        """
        Map unknown address, wrong password, and inactive/anonymized account to
        one public failure. The `citext` email column provides case-insensitive
        lookup without wrapping the indexed value in `LOWER()`.
        """
        user = User.objects.select_related("role").filter(email=command.email).first()

        if user is None:
            # Run the decoy hash so unknown-address failures have comparable password-check
            # cost instead of exposing a fast timing oracle.
            check_password(command.password, _decoy_hash())
            logger.info("auth.login.failed", extra={"reason": "unknown_email"})
            fanid_auth_login_total.labels(result="bad_credentials").inc()
            raise InvalidCredentialsError()

        if not user.check_password(command.password):
            logger.info("auth.login.failed", extra={"reason": "bad_password"})
            fanid_auth_login_total.labels(result="bad_credentials").inc()
            raise InvalidCredentialsError()

        if not user.is_active or user.anonymized_at is not None:
            # Deliberately return the same public failure so account existence and password
            # correctness are not disclosed.
            logger.warning("auth.login.failed", extra={"reason": "inactive_account"})
            fanid_auth_login_total.labels(result="inactive").inc()
            raise InvalidCredentialsError()

        return user

    # -- step 2: device binding, after credentials ----------------------------

    def _bind_device(self, user: User, command: LoginCommand) -> Device | None:
        """
        Bind a device only when the client supplies a fingerprint.

        Browser sessions may open without a `did`; exempt roles are handled by
        the device service and return no bound device.
        """
        if command.fingerprint is None:
            return None
        return self._binding.bind(
            user=user,
            fingerprint=command.fingerprint,
            platform=command.platform or "",
            label=command.label,
        )

    # -- refresh -------------------------------------------------------------

    def refresh(self, command: RefreshCommand) -> RefreshResult:
        """
        Rotate a refresh token and issue a new pair.

        For refresh, device verification happens before token consumption so a
        device mismatch does not destroy the legitimate holder's refresh token.
        An unresolvable current session does not short-circuit rotation because
        reuse detection still needs to run.
        """
        try:
            session = self._session_for(command.refresh)
            if session is not None and session.device is not None:
                self._binding.assert_fingerprint(
                    device=session.device,
                    fingerprint=command.fingerprint,
                )

            pair = TokenService.rotate(command.refresh)
        except TokenExpiredError:
            fanid_auth_token_refresh_total.labels(result="expired").inc()
            raise
        except TokenReuseDetectedError:
            fanid_auth_token_refresh_total.labels(result="reuse_detected").inc()
            raise
        except DeviceMismatchError:
            fanid_auth_token_refresh_total.labels(result="device_mismatch").inc()
            raise
        except TokenInvalidError:
            fanid_auth_token_refresh_total.labels(result="invalid").inc()
            raise

        fanid_auth_token_refresh_total.labels(result="success").inc()

        logger.info(
            "auth.refresh.success",
            extra={
                "session_id": str(pair.session.pk),
                "device_bound": pair.session.device is not None,
            },
        )
        return RefreshResult(user=pair.session.user, device=pair.session.device, pair=pair)

    @staticmethod
    def _session_for(raw_refresh: str) -> Session | None:
        """
        Find the session for which this refresh is currently active, without locking.

        This read exists only to discover the expected device before rotation;
        pessimistic locking remains in `TokenService.rotate`. A previously
        rotated token intentionally returns `None` here so rotation can continue
        and perform family-reuse detection.
        """
        claims = decode_token(raw_refresh, expected_type=TokenType.REFRESH)
        try:
            jti = uuid.UUID(str(claims.get("jti")))
        except (TypeError, ValueError):
            # Normalize malformed UUID claims into token invalidity rather than letting a
            # model-field conversion surface as a server error.
            raise TokenInvalidError() from None

        return (
            Session.objects.select_related("user", "user__role", "device")
            .filter(refresh_jti=jti, revoked_at__isnull=True, expires_at__gt=timezone.now())
            .first()
        )

    # -- logout --------------------------------------------------------------

    def logout(self, *, session_id: uuid.UUID) -> int:
        """
        Revoke the current session and return the number of affected rows.

        Logout revokes one session, not the whole family. Family revocation is
        reserved for token-reuse detection where the legitimate holder is
        unknown.
        """
        session = Session.objects.filter(pk=session_id).first()
        if session is None:
            # The session may disappear between authentication and this call because of
            # concurrent cleanup or revocation; there is then nothing left to revoke.
            return 0

        revoked = TokenService.revoke_session(session, SESSION_REVOKED_LOGOUT)
        logger.info(
            "auth.session.revoked",
            extra={"session_id": str(session.pk), "reason": SESSION_REVOKED_LOGOUT},
        )
        return revoked

    # -- password change -----------------------------------------------------

    def change_password(self, *, user: User, current_password: str, new_password: str) -> int:
        """
        Change the password and revoke every active session for the account.

        The caller's session is revoked too. The bound device is deliberately
        preserved so a credential change does not open the account to a new
        device while compromise is suspected. Password update and session
        revocation happen atomically.
        """
        if not user.check_password(current_password):
            logger.warning(
                "auth.password_change.failed",
                extra={"user_id": str(user.pk), "reason": "bad_current_password"},
            )
            raise InvalidCurrentPasswordError(
                details={"current_password": ["Le mot de passe actuel est incorrect."]}
            )

        if user.check_password(new_password):
            raise PasswordUnchangedError(
                details={"new_password": ["Le nouveau mot de passe doit etre different de l ancien."]}
            )

        temporary_credential_replaced = bool(user.must_change_password)

        with transaction.atomic():
            user.set_password(new_password)

            user.must_change_password = False

            user.save(
                update_fields=[
                    "password",
                    "must_change_password",
                ],
            )

            revoked = TokenService.revoke_all_for_user(
                user,
                SESSION_REVOKED_PASSWORD_CHANGE,
            )

            publish_event(
                event_type=USER_PASSWORD_CHANGED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=(
                    user_password_changed_payload(
                        temporary_credential_replaced=(temporary_credential_replaced),
                    )
                ),
            )

        logger.info(
            "auth.session.revoked",
            extra={"user_id": str(user.pk), "reason": SESSION_REVOKED_PASSWORD_CHANGE, "sessions": revoked},
        )
        return revoked
