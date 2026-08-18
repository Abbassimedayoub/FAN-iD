"""
Serialiseurs HTTP du contexte `organizing`.

Comme dans `identity`, les contrats d entree sont FERMES : un champ ajoute au
modele ne devient jamais exposable automatiquement.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .constants import ORG_NAME_MAX_LENGTH


class OrganizerApplySerializer(serializers.Serializer):
    """Corps de `POST /api/v1/organizers/apply`."""

    org_name = serializers.CharField(max_length=ORG_NAME_MAX_LENGTH)
    contact_email = serializers.EmailField(max_length=254)
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
