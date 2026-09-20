"""
Bounded context `identity`: roles, users, devices, sessions, and MFA state.

These models contain structural invariants only. Registration, age-validation
messages, over-posting protection, and explicit terms consent belong to
services. Database constraints remain responsible for invariants that must hold
even for direct SQL writes.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

from .constants import (
    AUTH_LEVEL_PASSWORD,
    AUTH_LEVELS,
    CLIENT_MOBILE,
    CLIENT_WEB,
    CODE_HASH_PATTERN,
    DEVICE_PLATFORMS,
    DEVICE_REVOKED_REASONS,
    FINGERPRINT_PATTERN,
    MFA_PURPOSES,
    OTP_MAX_ATTEMPTS,
    ROLE_IDS,
    ROLE_NAMES,
    ROLE_SCANNER,
    SESSION_REVOKED_REASONS,
)
from .fields import CITextEmailField
from .managers import UserManager
from .querysets import DeviceQuerySet, MfaChallengeQuerySet, SessionQuerySet


class Role(models.Model):
    """
    Role reference table with four nearly static rows.

    `permissions` is descriptive metadata for administration interfaces. The
    authorization source of truth is the code policy in `apps.identity.authz`;
    requests must never be authorized from this JSON field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_role"
        constraints = [
            # Second line of defense: the database rejects an unknown role name even when
            # inserted directly with SQL.
            models.CheckConstraint(
                condition=models.Q(name__in=list(ROLE_NAMES)),
                name="ck_role_name_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser, TimeStampedModel, VersionedModel):
    """
    User model whose canonical application identity is the email address.

    `username` is retained but neutralized because it comes from `AbstractUser`;
    keeping it nullable and non-unique avoids a destructive historical migration.
    `date_joined` is retained for the same compatibility reason while
    `created_at` is the project's canonical creation timestamp.

    Incoming business references use PROTECT rather than CASCADE; account
    erasure is handled through anonymization instead of deleting business data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Identity ---
    email = CITextEmailField(unique=True)
    username = models.CharField(  # type: ignore[misc]
        max_length=150,
        null=True,
        blank=True,
        validators=[UnicodeUsernameValidator()],
        help_text="Hérité d'AbstractUser, neutralisé : l'identifiant de connexion est l'email.",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        help_text="V1 : un seul rôle par utilisateur (ADR-01).",
    )

    # --- Personal details ---
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)

    # --- Compliance ---
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    # Scanner accounts created by invitation.
    must_change_password = models.BooleanField(
        default=False,
        db_default=False,
    )
    temporary_password_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    temporary_password_generation = models.PositiveIntegerField(
        default=0,
        db_default=0,
    )

    temporary_password_expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    #: `createsuperuser` asks for the date of birth; the age constraint also applies
    #: to administrator accounts.
    REQUIRED_FIELDS = ["date_of_birth"]

    objects = UserManager()  # type: ignore[misc,assignment]

    class Meta:
        db_table = "identity_user"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        role_id=ROLE_IDS[ROLE_SCANNER],
                    )
                    | (
                        models.Q(
                            date_of_birth__isnull=False,
                        )
                        & models.Q(
                            terms_accepted_at__isnull=False,
                        )
                    )
                ),
                name=("ck_user_compliance_or_scanner"),
            ),
        ]

    def __str__(self) -> str:
        return self.email


class Device(UUIDModel):
    """
    Device bound to an account.

    At most one active device per account is enforced by a partial uniqueness
    constraint: `UNIQUE(user_id) WHERE revoked_at IS NULL`. Revoked devices are
    retained as history while only the current device is constrained.

    The fingerprint is opaque and computed client-side. The server never
    recomputes it or substitutes IP, User-Agent, or behavioral fingerprinting;
    it validates only the canonical format.

    `bound_at` is the creation timestamp, so this model does not also inherit a
    second generic creation field. Device rows cascade with the account because
    the fingerprint is personal data with no independent business-history value.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    fingerprint = models.CharField(max_length=64)
    label = models.CharField(max_length=60, blank=True, default="")
    platform = models.CharField(max_length=10, choices=[(p, p) for p in DEVICE_PLATFORMS])
    bound_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(  # type: ignore[misc]
        max_length=20,
        null=True,
        blank=True,
        choices=[(r, r) for r in DEVICE_REVOKED_REASONS],
    )

    objects = DeviceQuerySet.as_manager()

    class Meta:
        db_table = "identity_device"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(revoked_at__isnull=True),
                name="uq_device_active_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(fingerprint__regex=FINGERPRINT_PATTERN),
                name="ck_device_fingerprint_format",
            ),
            models.CheckConstraint(
                condition=models.Q(platform__in=list(DEVICE_PLATFORMS)),
                name="ck_device_platform_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(revoked_reason__isnull=True)
                | models.Q(revoked_reason__in=list(DEVICE_REVOKED_REASONS)),
                name="ck_device_revoked_reason_valid",
            ),
            # A revoked device without a reason has incomplete audit value, while a reason
            # without a revocation timestamp is incoherent. The two fields must
            # therefore be set together or both remain null.
            models.CheckConstraint(
                condition=models.Q(revoked_at__isnull=True, revoked_reason__isnull=True)
                | models.Q(revoked_at__isnull=False, revoked_reason__isnull=False),
                name="ck_device_revocation_coherent",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-bound_at"], name="ix_device_history"),
        ]

    def __str__(self) -> str:
        return f"{self.label or self.platform} ({self.user_id})"


class Session(UUIDModel):
    """
    Authentication session and refresh-token family.

    A dedicated table makes active sessions listable, allows whole-family
    revocation after token reuse, binds sessions to devices, and stores the
    authentication level used for step-up authorization.

    `family_id` identifies the lineage created by one login. On refresh reuse,
    the entire family is revoked because the system cannot know which holder is
    legitimate. This model is unrelated to `django.contrib.sessions` and stores
    no generic HTTP-session state.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    family_id = models.UUIDField()
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        help_text="Nul pour ORGANIZER et ADMIN, exemptés du verrou d'appareil (ADR-03).",
    )
    refresh_jti = models.UUIDField(unique=True)
    auth_level = models.PositiveSmallIntegerField(default=AUTH_LEVEL_PASSWORD)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    client = models.CharField(
        max_length=10,
        choices=[
            (CLIENT_WEB, CLIENT_WEB),
            (CLIENT_MOBILE, CLIENT_MOBILE),
        ],
        null=True,
        blank=True,
        help_text=(
            "Canal ayant ouvert la session. Null uniquement pour les sessions "
            "historiques ou les appels internes anterieurs a ce champ."
        ),
    )
    # Use `default=` instead of `auto_now_add=` because session issuance time is
    # business data chosen by `TokenService`, not an ORM audit timestamp. It must
    # remain explicitly settable for tests and data recovery.
    issued_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(  # type: ignore[misc]
        max_length=20,
        null=True,
        blank=True,
        choices=[(r, r) for r in SESSION_REVOKED_REASONS],
    )

    objects = SessionQuerySet.as_manager()

    class Meta:
        db_table = "identity_session"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(auth_level__in=list(AUTH_LEVELS)),
                name="ck_session_auth_level_valid",
            ),
            # A session expiring before issuance indicates an invalid lifetime calculation;
            # reject it at write time rather than surfacing it later to users.
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("issued_at")),
                name="ck_session_expiry_after_issue",
            ),
            models.CheckConstraint(
                condition=models.Q(revoked_reason__isnull=True)
                | models.Q(revoked_reason__in=list(SESSION_REVOKED_REASONS)),
                name="ck_session_revoked_reason_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(revoked_at__isnull=True, revoked_reason__isnull=True)
                | models.Q(revoked_at__isnull=False, revoked_reason__isnull=False),
                name="ck_session_revocation_coherent",
            ),
        ]
        indexes = [
            models.Index(fields=["family_id"], name="ix_session_family"),
            models.Index(fields=["user", "revoked_at"], name="ix_session_user_active"),
            models.Index(fields=["expires_at"], name="ix_session_purge"),
        ]

    def __str__(self) -> str:
        return f"Session({self.user_id}, family={self.family_id})"


class MfaChallenge(UUIDModel):
    """
    Step-up verification challenge with a one-time code.

    The code is never stored in plaintext; only its SHA-256 digest is persisted,
    with a database CHECK constraint enforcing the digest shape even for direct
    SQL writes. The database also guarantees `attempts <= max_attempts` so a
    stale concurrent write cannot exceed the attempt ceiling.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_challenges")
    purpose = models.CharField(max_length=20, choices=[(p, p) for p in MFA_PURPOSES])
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=OTP_MAX_ATTEMPTS)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MfaChallengeQuerySet.as_manager()

    class Meta:
        db_table = "identity_mfa_challenge"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attempts__lte=models.F("max_attempts")),
                name="ck_mfa_attempts_within_max",
            ),
            models.CheckConstraint(
                condition=models.Q(purpose__in=list(MFA_PURPOSES)),
                name="ck_mfa_purpose_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(code_hash__regex=CODE_HASH_PATTERN),
                name="ck_mfa_code_hash_is_a_digest",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "purpose", "consumed_at"], name="ix_mfa_open"),
            models.Index(fields=["expires_at"], name="ix_mfa_purge"),
        ]

    def __str__(self) -> str:
        return f"MfaChallenge({self.purpose}, user={self.user_id})"
