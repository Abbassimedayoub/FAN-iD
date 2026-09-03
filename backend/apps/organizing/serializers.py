"""
Serialiseurs HTTP du contexte `organizing`.

Comme dans `identity`, les contrats d entree sont FERMES : un champ ajoute au
modele ne devient jamais exposable automatiquement.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .constants import (
    ORGANIZER_COMMISSION_AGREED,
    ORGANIZER_COMMISSION_CANCELLED,
    ORGANIZER_COMMISSION_NEGOTIATING,
    ORGANIZER_REJECTED,
    ORG_NAME_MAX_LENGTH,
)


class OrganizerApplySerializer(serializers.Serializer):
    """Corps de `POST /api/v1/organizers/apply`."""

    org_name = serializers.CharField(max_length=ORG_NAME_MAX_LENGTH)
    contact_email = serializers.EmailField(max_length=254)

    proposed_commission_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=0,
        max_value=1,
        required=True,
    )

    vat_number = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class OrganizerSerializer(serializers.Serializer):
    """Representation publique d un dossier organisateur."""

    id = serializers.UUIDField(read_only=True)
    org_name = serializers.CharField(read_only=True)
    validation_status = serializers.CharField(read_only=True)
    commission_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        read_only=True,
    )
    vat_number = serializers.CharField(read_only=True, allow_null=True)
    contact_email = serializers.EmailField(read_only=True)
    rejection_reason = serializers.CharField(read_only=True, allow_null=True)
    validated_at = serializers.DateTimeField(read_only=True, allow_null=True)
    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class OrganizerCommissionProposalSerializer(
    serializers.Serializer,
):
    id = serializers.UUIDField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    proposer_role = serializers.CharField(read_only=True)
    proposed_by_id = serializers.UUIDField(read_only=True)
    rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        read_only=True,
    )
    created_at = serializers.DateTimeField(read_only=True)
    accepted_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    accepted_by_id = serializers.UUIDField(
        read_only=True,
        allow_null=True,
    )


class OrganizerCommissionNegotiationSerializer(
    serializers.Serializer,
):
    organizer_id = serializers.UUIDField(read_only=True)
    validation_status = serializers.CharField(read_only=True)
    commission_status = serializers.CharField(read_only=True)
    agreed_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        read_only=True,
        allow_null=True,
    )
    agreed_at = serializers.DateTimeField(
        read_only=True,
        allow_null=True,
    )
    version = serializers.IntegerField(read_only=True)
    proposals = OrganizerCommissionProposalSerializer(
        many=True,
        read_only=True,
    )


class OrganizerCommissionProposalCreateSerializer(
    serializers.Serializer,
):
    commission_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=0,
        max_value=1,
    )


def organizer_commission_negotiation_data(
    organizer,
) -> dict[str, Any]:
    proposals = list(
        organizer.commission_proposals.all().order_by(
            "sequence",
        )
    )

    if organizer.validation_status == ORGANIZER_REJECTED:
        commission_status = ORGANIZER_COMMISSION_CANCELLED
        agreed_rate = None
        agreed_at = None
    elif organizer.commission_agreed_at is not None:
        commission_status = ORGANIZER_COMMISSION_AGREED
        agreed_rate = organizer.commission_rate
        agreed_at = organizer.commission_agreed_at
    else:
        commission_status = ORGANIZER_COMMISSION_NEGOTIATING
        agreed_rate = None
        agreed_at = None

    return {
        "organizer_id": organizer.pk,
        "validation_status": organizer.validation_status,
        "commission_status": commission_status,
        "agreed_rate": agreed_rate,
        "agreed_at": agreed_at,
        "version": organizer.version,
        "proposals": proposals,
    }


class OrganizerRejectSerializer(serializers.Serializer):
    """Corps de l action administrative de rejet."""

    reason = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
        allow_blank=False,
    )

    def validate_reason(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Ce champ est obligatoire.")
        return value


class AdminOrganizerListResponseSerializer(serializers.Serializer):
    """Page standard de dossiers organisateurs pour l administration."""

    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = OrganizerSerializer(many=True, read_only=True)


def organizer_apply_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Construit la commande fermee transmise au service.

    Les champs absents du contrat ne peuvent pas traverser cette fonction, meme
    s ils figurent dans le corps brut de la requete.
    """
    return {
        "org_name": data["org_name"],
        "contact_email": data["contact_email"],
        "vat_number": data.get("vat_number") or None,
    }
