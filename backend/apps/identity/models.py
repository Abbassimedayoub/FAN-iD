"""
Bounded context `identity` — Role et User (plan S1 §3.1).

**Point de non-retour** : neuf tables du schéma porteront une clé étrangère vers
`user`. Le modèle est donc figé ici avec ses contraintes, pas ajusté au fil des
sprints.

Ce que ce module NE fait pas : aucune règle métier. L'inscription, la validation
d'âge avec message exploitable, le refus du sur-postage et le consentement CGU
appartiennent à `RegistrationService` (lot S1-A.3). Les modèles ne portent que
les invariants structurels — ceux qui doivent tenir même face à une insertion
SQL directe.
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
    Référentiel des rôles — 4 lignes, quasi statique (plan S1 §3.1).

    `permissions` est **descriptif** (ADR-02) : il documente les capacités du
    rôle pour la console d'administration. La source de vérité de l'autorisation
    est la politique en code de `apps.identity.authz` (master prompt §10). Ne
    jamais autoriser une
    requête sur la foi de ce JSON.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_role"
        constraints = [
            # Second niveau de défense (ADR-S-04 règle 7) : le SGBD refuse un
            # rôle inconnu même inséré directement en SQL.
            models.CheckConstraint(
                condition=models.Q(name__in=list(ROLE_NAMES)),
                name="ck_role_name_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser, TimeStampedModel, VersionedModel):
    """
    Utilisateur — l'email est l'identité canonique de l'application.

    **`username` conservé mais neutralisé** (décision D-4) : `AbstractUser`
    l'impose en `UNIQUE NOT NULL`. Plutôt que de le supprimer — migration
    destructive, contraire au §9 — il devient nullable et non unique. Il ne
    sert plus à rien fonctionnellement ; il est conservé pour ne pas casser
    l'historique de migration et pourra être retiré plus tard en
    expand/contract (ADR-S-08).

    **`date_joined` conservé** pour la même raison. L'horodatage canonique du
    projet est `created_at`, hérité de `TimeStampedModel` comme sur toutes les
    autres tables — c'est lui que référence la contrainte d'âge.

    **Suppression** : jamais de `CASCADE` depuis `user`. Toutes les références
    entrantes seront en `PROTECT` ; l'effacement RGPD passe par l'anonymisation
    (`anonymized_at`, Sprint 5).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Identité ---
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

    # --- État civil ---
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)

    # --- Conformité ---
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    # Comptes SCANNER créés par invitation.
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
    #: `createsuperuser` demandera la date de naissance ; la contrainte d'âge
    #: s'applique aussi aux administrateurs.
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
    Appareil lié à un compte (plan S1 §2.4 et §3.1, matérialise RM-5).

    **Un seul appareil actif par compte**, garanti par une unicité PARTIELLE en
    base : `UNIQUE(user_id) WHERE revoked_at IS NULL`. L'historique des appareils
    révoqués est conservé pour l'audit ; seul l'appareil courant est contraint.
    Vérifié sur PostgreSQL 16 : révoquer l'actif puis en lier un nouveau
    fonctionne, lier un second actif est rejeté.

    **L'empreinte est opaque.** Elle est calculée côté client (identifiant
    matériel + bundle id + sel persistant, puis SHA-256). Le serveur ne la
    recalcule jamais, n'en déduit rien, et n'utilise NI l'IP, NI le User-Agent,
    NI aucune empreinte comportementale comme substitut — c'est instable,
    intrusif, et non conforme à la minimisation RGPD. Il valide uniquement le
    format.

    **Pas de `TimeStampedModel`** : `bound_at` EST l'horodatage de création.
    Ajouter `created_at` créerait deux champs pour la même information, donc une
    occasion de divergence.

    **`on_delete=CASCADE`** : contrairement aux tables métier (commandes, billets,
    journaux de scan) qui seront en `PROTECT`, une empreinte d'appareil est une
    donnée personnelle sans valeur d'audit propre. La conserver après suppression
    du compte serait un passif RGPD, pas une protection.
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
            # Un appareil révoqué SANS motif perd toute valeur d'audit ; un motif
            # SANS date de révocation décrit un état qui n'existe pas. Les deux
            # champs vont ensemble ou pas du tout.
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
    Session d'authentification et famille de jetons (plan S1 §3.1).

    **Pourquoi une table plutôt que la seule liste noire de SimpleJWT** : elle
    permet de lister ses sessions actives, de révoquer une famille entière lors
    d'une détection de vol, de lier la session à un appareil, et de porter le
    niveau d'authentification pour l'élévation.

    `family_id` identifie toute la lignée issue d'une connexion. Sa révocation
    est l'unité de réponse à une réutilisation de refresh (master prompt §17) :
    on ne révoque pas le jeton fautif, on révoque la famille — y compris le
    refresh qui vient d'être émis légitimement, puisqu'on ne sait pas lequel des
    deux porteurs est l'attaquant.

    À ne pas confondre avec `django.contrib.sessions` : aucun rapport, ce modèle
    ne stocke pas d'état de session HTTP.
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
    # `default=` et non `auto_now_add=` : la date d'émission d'une session est
    # une donnée MÉTIER, décidée par `TokenService`, pas un horodatage d'audit
    # posé par l'ORM. `auto_now_add` la rendrait impossible à fixer
    # explicitement — donc impossible à antidater dans un test, et impossible
    # à reconstituer lors d'une reprise de données.
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
            # Une session qui expire avant son émission est un bug de calcul de
            # durée de vie. Mieux vaut le voir à l'écriture qu'au moment où un
            # utilisateur se retrouve déconnecté sans raison.
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
    Défi de vérification renforcée — code à usage unique (plan S1 §3.1).

    **Le code n'est jamais stocké en clair.** Seul son SHA-256 l'est, et le
    format est verrouillé par une contrainte CHECK : insérer `042917` dans
    `code_hash` est rejeté par le SGBD, y compris par une écriture SQL directe
    qui contournerait le service. Sans cette contrainte, un développeur pressé
    pourrait y écrire le code brut sans que rien ne le signale — la fuite ne se
    verrait qu'au moment d'une exfiltration de base.

    `attempts <= max_attempts` est garanti en base : le plafond de 5 tentatives
    ne peut pas être dépassé par une écriture concurrente qui aurait lu une
    valeur périmée.
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
