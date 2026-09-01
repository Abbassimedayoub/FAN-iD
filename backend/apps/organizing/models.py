"""
Contexte borne `organizing` — l organisateur et son dossier de validation.

## Ce que ce module N IMPORTE PAS

Ni `apps.identity.models`, ni quoi que ce soit d autre de ce contexte. La cle
etrangere vers le compte passe par `settings.AUTH_USER_MODEL`, une CHAINE que
le registre Django resout paresseusement : aucun import n existe, et le graphe
de dependances reste acyclique (ADR-S1-05).

Consequence honnete a connaitre : `import-linter` ne voit pas ce couplage. La
contrainte de cle etrangere existe bien en base, entre deux contextes. C est
une limite de l outil, pas une faille du modele — mais elle merite d etre
ecrite plutot que decouverte.

## Suppression : PROTECT, jamais CASCADE

`user` est protege : supprimer un compte qui porte un organisateur effacerait
ses evenements, ses ventes et ses journaux de scan. L effacement RGPD passe par
l anonymisation (S5, ADR-13), pas par un `DELETE`.

`validated_by` est en `SET_NULL` : le depart d un administrateur ne doit pas
effacer la trace d une decision, seulement son auteur.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

from .constants import (
    ORG_NAME_MAX_LENGTH,
    ORGANIZER_PENDING,
    ORGANIZER_STATUSES,
    SCANNER_CREDENTIAL_REQUEST_PENDING,
    SCANNER_CREDENTIAL_REQUEST_STATUSES,
    SCANNER_INVITED,
    SCANNER_STATUSES,
)
from .querysets import OrganizerQuerySet

#: Taux par defaut. Le plan §3.1 fixe le type `numeric(5,4)` et la contrainte
#: `BETWEEN 0 AND 1`, mais ni valeur par defaut ni qui la renseigne — et
#: `apply` ne peut pas la recevoir du client. Zero est la seule valeur qui
#: n invente aucune regle commerciale : aucune commission tant qu elle n a pas
#: ete posee explicitement. Ecart consigne, a trancher au lot S1-A.8b.
DEFAULT_COMMISSION_RATE = Decimal("0.0000")


class Organizer(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Dossier d organisateur (plan S1 §3.1).

    `VersionedModel` fournit le verrouillage optimiste exige par le plan : deux
    administrateurs validant simultanement le meme dossier ne doivent pas
    s ecraser en silence — le second recoit `409 STALE_RESOURCE`. Le champ est
    pose ici, son EXPLOITATION appartient au lot S1-A.8b.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizer",
    )
    org_name = models.CharField(max_length=ORG_NAME_MAX_LENGTH)
    validation_status = models.CharField(
        max_length=20,
        default=ORGANIZER_PENDING,
        choices=[(status, status) for status in ORGANIZER_STATUSES],
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=DEFAULT_COMMISSION_RATE)
    vat_number = models.CharField(max_length=32, null=True, blank=True)
    contact_email = models.EmailField(max_length=254)
    rejection_reason = models.TextField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizers_validated",
    )

    objects = OrganizerQuerySet.as_manager()  # type: ignore[django-manager-missing]

    class Meta:
        db_table = "organizing_organizer"
        constraints = [
            # Unicite INSENSIBLE A LA CASSE : « Stade de France » et « stade de
            # france » designent le meme organisateur. Une unicite simple
            # laisserait creer les deux, et le doublon ne se verrait qu au
            # moment ou un acheteur choisit le mauvais.
            models.UniqueConstraint(Lower("org_name"), name="uq_organizer_org_name_ci"),
            models.CheckConstraint(
                condition=models.Q(commission_rate__gte=0) & models.Q(commission_rate__lte=1),
                name="ck_organizer_commission_rate_range",
            ),
            models.CheckConstraint(
                condition=models.Q(validation_status__in=list(ORGANIZER_STATUSES)),
                name="ck_organizer_status_valid",
            ),
        ]
        indexes = [
            # Filtre principal de la console d administration (§3.1).
            models.Index(fields=["validation_status"], name="ix_organizer_status"),
        ]

    def __str__(self) -> str:
        return f"{self.org_name} ({self.validation_status})"


class Scanner(
    UUIDModel,
    TimeStampedModel,
    VersionedModel,
):
    """
    Scanner rattaché à un organisateur.

    PROTECT conserve la traçabilité métier.
    """

    organizer = models.ForeignKey(
        Organizer,
        on_delete=models.PROTECT,
        related_name="scanners",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scanner_membership",
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scanner_invitations_sent",
    )

    # Snapshot métier conservé pour la traçabilité
    # après anonymisation du compte identité.
    invited_first_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    invited_last_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    invited_email = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
    )

    removed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scanner_removals",
        null=True,
        blank=True,
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scanner_archives",
        null=True,
        blank=True,
    )

    revocation_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    revocation_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_request_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_request_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_rejected_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    leave_rejected_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        default=SCANNER_INVITED,
        choices=[(value, value) for value in SCANNER_STATUSES],
    )

    scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    opened_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    opened_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    opened_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    active_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    active_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "organizing_scanner"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=list(SCANNER_STATUSES),
                ),
                name="ck_scanner_status_valid",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "organizer",
                    "status",
                ],
                name="ix_scanner_org_status",
            ),
        ]

    def __str__(self) -> str:
        return f"Scanner(" f"{self.user_id}, " f"{self.status}" f")"


class ScannerCredentialRequest(
    UUIDModel,
    TimeStampedModel,
):
    """
    Demande de nouveau mot de passe temporaire
    initiée par un scanner.

    Aucun mot de passe n'est stocké ici.
    """

    scanner = models.ForeignKey(
        Scanner,
        on_delete=models.PROTECT,
        related_name="credential_requests",
    )

    status = models.CharField(
        max_length=16,
        default=SCANNER_CREDENTIAL_REQUEST_PENDING,
        choices=[(value, value) for value in SCANNER_CREDENTIAL_REQUEST_STATUSES],
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=("scanner_credential_requests_resolved"),
        null=True,
        blank=True,
    )

    generation = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    request_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    request_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reissue_scanner_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reissue_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "organizing_scanner_credential_request"

        constraints = [
            models.UniqueConstraint(
                fields=["scanner"],
                condition=models.Q(
                    status=(SCANNER_CREDENTIAL_REQUEST_PENDING),
                ),
                name=("uq_scanner_pending_credential_request"),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "scanner",
                    "status",
                    "-created_at",
                ],
                name="ix_scan_cred_req_status",
            ),
        ]


class ScannerRevocationChallenge(UUIDModel):
    ACTION_REVOKE = "REVOKE"
    ACTION_LEAVE_ACCEPT = "LEAVE_ACCEPT"
    ACTION_LEAVE_REQUEST = "LEAVE_REQUEST"

    ACTION_CHOICES = (
        (ACTION_REVOKE, ACTION_REVOKE),
        (ACTION_LEAVE_ACCEPT, ACTION_LEAVE_ACCEPT),
        (ACTION_LEAVE_REQUEST, ACTION_LEAVE_REQUEST),
    )

    organizer = models.ForeignKey(
        Organizer,
        on_delete=models.CASCADE,
        related_name="scanner_revocation_challenges",
    )
    scanner = models.ForeignKey(
        Scanner,
        on_delete=models.CASCADE,
        related_name="revocation_challenges",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scanner_revocation_challenges",
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )
    code_hash = models.CharField(
        max_length=64,
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=5,
    )
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "organizing_scanner_revocation_challenge"
        indexes = [
            models.Index(
                fields=[
                    "organizer",
                    "scanner",
                    "action",
                    "consumed_at",
                ],
                name="ix_scanner_revoke_otp_open",
            ),
            models.Index(
                fields=["expires_at"],
                name="ix_scanner_revoke_otp_exp",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    attempts__lte=models.F("max_attempts"),
                ),
                name="ck_scanner_revoke_otp_attempts",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    code_hash__regex=r"^[0-9a-f]{64}$",
                ),
                name="ck_scanner_revoke_otp_hash",
            ),
        ]


class OrganizerReactivationRequest(
    UUIDModel,
    TimeStampedModel,
):
    """
    Demande persistante de réouverture d'un organisateur suspendu.

    Le statut de l'Organizer reste SUSPENDED pendant PENDING
    et REJECTED. Seule une décision administrative APPROVED
    peut déclencher SUSPENDED -> APPROVED.
    """

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_APPROVED, STATUS_APPROVED),
        (STATUS_REJECTED, STATUS_REJECTED),
    )

    organizer = models.ForeignKey(
        Organizer,
        on_delete=models.PROTECT,
        related_name="reactivation_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizer_reactivation_requests",
    )
    organizer_version = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizer_reactivation_reviews",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    rejection_reason = models.TextField(
        null=True,
        blank=True,
    )

    request_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    request_admin_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    decision_organizer_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    decision_admin_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "organizing_organizer_reactivation_request"
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "organizer",
                    "-created_at",
                ],
                name="ix_org_react_org_created",
            ),
            models.Index(
                fields=[
                    "status",
                    "-created_at",
                ],
                name="ix_org_react_status_created",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organizer",
                ],
                condition=models.Q(
                    status="PENDING",
                ),
                name="uq_org_pending_reactivation",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING",
                        "APPROVED",
                        "REJECTED",
                    ],
                ),
                name="ck_org_reactivation_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organizer_id} " f"reactivation {self.status}"
