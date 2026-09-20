"""
Bounded context `organizing`: organizer records and their validation dossier.

This module deliberately does not import `apps.identity.models`. The account
foreign key uses `settings.AUTH_USER_MODEL`, which Django resolves lazily, so
the Python dependency graph remains acyclic even though a database foreign key
still connects the two contexts.

Deletion rules are intentional: `user` uses PROTECT so business history is not
removed with an account, while `validated_by` uses SET_NULL so a decision
remains recorded even if its administrator account disappears.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

from .constants import (
    ORG_NAME_MAX_LENGTH,
    ORGANIZER_COMMISSION_PROPOSER_ROLES,
    ORGANIZER_PENDING,
    ORGANIZER_STATUSES,
    SCANNER_CREDENTIAL_REQUEST_PENDING,
    SCANNER_CREDENTIAL_REQUEST_STATUSES,
    SCANNER_INVITED,
    SCANNER_STATUSES,
)
from .querysets import OrganizerQuerySet

#: Default rate. Zero is the neutral value until a commission is explicitly
#: agreed; it does not invent a commercial rule.
DEFAULT_COMMISSION_RATE = Decimal("0.0000")


class Organizer(UUIDModel, TimeStampedModel, VersionedModel):
    """
    Organizer dossier.

    `VersionedModel` provides optimistic locking so concurrent administrative
    updates cannot silently overwrite each other.
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
    commission_agreed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
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
            # Case-insensitive uniqueness prevents duplicate organizer names that differ
            # only by letter case.
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
            # Primary filter used by the administration console.
            models.Index(fields=["validation_status"], name="ix_organizer_status"),
        ]

    def __str__(self) -> str:
        return f"{self.org_name} ({self.validation_status})"


class OrganizerCommissionProposal(
    UUIDModel,
    TimeStampedModel,
):
    """
    Structured commission proposal.

    Each negotiation creates a new row. Rate, author, and sequence are immutable;
    acceptance only fills `accepted_at` and `accepted_by`.
    """

    organizer = models.ForeignKey(
        Organizer,
        on_delete=models.PROTECT,
        related_name="commission_proposals",
    )

    sequence = models.PositiveIntegerField()

    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizer_commission_proposals_authored",
    )

    proposer_role = models.CharField(
        max_length=16,
        choices=[(role, role) for role in ORGANIZER_COMMISSION_PROPOSER_ROLES],
    )

    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
    )

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizer_commission_proposals_accepted",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "organizing_organizer_commission_proposal"
        ordering = ["sequence"]

        constraints = [
            models.UniqueConstraint(
                fields=["organizer", "sequence"],
                name="uq_org_commission_proposal_seq",
            ),
            models.CheckConstraint(
                condition=(models.Q(rate__gte=0) & models.Q(rate__lte=1)),
                name="ck_org_commission_proposal_rate",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    proposer_role__in=list(ORGANIZER_COMMISSION_PROPOSER_ROLES),
                ),
                name="ck_org_commission_proposer_role",
            ),
        ]

        indexes = [
            models.Index(
                fields=["organizer", "sequence"],
                name="ix_org_commission_prop_seq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organizer_id} " f"#{self.sequence} " f"{self.proposer_role} " f"{self.rate}"


class Scanner(
    UUIDModel,
    TimeStampedModel,
    VersionedModel,
):
    """
    Scanner attached to an organizer.

    PROTECT preserves business traceability.
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

    # Business snapshot kept for traceability after identity-account anonymization.
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
    Scanner-initiated request for a new temporary password.

    No password is stored here.
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
    Persistent request to reactivate a suspended organizer.

    The organizer remains SUSPENDED while the request is PENDING or REJECTED.
    Only an APPROVED administrative decision may transition it back to APPROVED.
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
