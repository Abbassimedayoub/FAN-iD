from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organizing.constants import ORGANIZER_PENDING
from apps.organizing.models import Organizer
from apps.organizing.serializers import (
    OrganizerApplySerializer,
    OrganizerRejectSerializer,
    OrganizerSerializer,
    organizer_apply_data,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_apply_serializer_accepts_only_the_public_input_shape():
    serializer = OrganizerApplySerializer(
        data={
            "org_name": "Stade de France",
            "contact_email": "contact@example.test",
            "vat_number": "FR123456789",
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {
        "org_name": "Stade de France",
        "contact_email": "contact@example.test",
        "vat_number": "FR123456789",
    }


def test_apply_serializer_does_not_expose_privileged_model_fields():
    serializer = OrganizerApplySerializer(
        data={
            "org_name": "Stade de France",
            "contact_email": "contact@example.test",
            "validation_status": "APPROVED",
            "commission_rate": "0.9999",
            "validated_by": "11111111-1111-4111-8111-111111111111",
            "rejection_reason": "injecte",
            "version": 999,
        }
    )

    assert serializer.is_valid(), serializer.errors

    command = organizer_apply_data(serializer.validated_data)

    assert command == {
        "org_name": "Stade de France",
        "contact_email": "contact@example.test",
        "vat_number": None,
    }
    assert "validation_status" not in serializer.validated_data
    assert "commission_rate" not in serializer.validated_data
    assert "validated_by" not in serializer.validated_data
    assert "rejection_reason" not in serializer.validated_data
    assert "version" not in serializer.validated_data


@pytest.mark.parametrize(
    "payload",
    [
        {"contact_email": "contact@example.test"},
        {"org_name": "Stade de France"},
        {
            "org_name": "Stade de France",
            "contact_email": "pas-un-email",
        },
    ],
)
def test_apply_serializer_rejects_invalid_required_shape(payload):
    serializer = OrganizerApplySerializer(data=payload)

    assert serializer.is_valid() is False


@pytest.mark.parametrize("reason", ["", "   "])
def test_reject_serializer_refuses_a_blank_reason(reason):
    serializer = OrganizerRejectSerializer(data={"reason": reason})

    assert serializer.is_valid() is False
    assert "reason" in serializer.errors


def test_reject_serializer_normalizes_the_reason():
    serializer = OrganizerRejectSerializer(data={"reason": "  Dossier incomplet  "})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["reason"] == "Dossier incomplet"


def test_organizer_serializer_exposes_the_expected_public_shape(roles):
    user = User.objects.create_user(
        email="serializer-organizer@example.test",
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1990, 3, 12),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name="Stade de France",
        contact_email="contact@example.test",
    )

    data = OrganizerSerializer(organizer).data

    assert data["id"] == str(organizer.pk)
    assert data["org_name"] == "Stade de France"
    assert data["validation_status"] == ORGANIZER_PENDING
    assert Decimal(data["commission_rate"]) == Decimal("0.0000")
    assert data["vat_number"] is None
    assert data["contact_email"] == "contact@example.test"
    assert data["rejection_reason"] is None
    assert data["validated_at"] is None
    assert data["version"] == 1

    assert set(data) == {
        "id",
        "org_name",
        "validation_status",
        "commission_rate",
        "vat_number",
        "contact_email",
        "rejection_reason",
        "validated_at",
        "version",
        "created_at",
        "updated_at",
    }
