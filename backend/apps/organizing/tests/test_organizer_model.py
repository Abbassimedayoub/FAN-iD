"""
`Organizer` — les invariants que la BASE fait respecter.

Chaque test tente une insertion INTERDITE et verifie que le SGBD la refuse. Un
invariant verifie seulement par le code applicatif tombe a la premiere commande
d administration ou reprise de donnees.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizing.constants import ORGANIZER_APPROVED, ORGANIZER_PENDING
from apps.organizing.models import Organizer

User = get_user_model()

pytestmark = pytest.mark.django_db


def make_user(roles, email: str) -> Any:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1990, 3, 12),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def applicant(db, roles) -> Any:
    return make_user(roles, "organisateur@example.test")


def test_a_new_dossier_starts_pending(applicant):
    organizer = Organizer.objects.create(
        user=applicant,
        org_name="Stade de France",
        contact_email="contact@example.test",
    )

    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.commission_rate == Decimal("0.0000")


def test_one_account_carries_at_most_one_dossier(applicant):
    """
    Sans cette unicite, l API renverrait une 500 de violation d integrite la ou
    un 403 est la bonne reponse — c est aussi pourquoi `ORGANIZER_CREATE` n est
    pas accorde au role ORGANIZER dans la matrice.
    """
    Organizer.objects.create(
        user=applicant,
        org_name="Premier",
        contact_email="a@example.test",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=applicant,
            org_name="Second",
            contact_email="b@example.test",
        )


def test_the_commercial_name_is_unique_regardless_of_case(applicant, roles):
    """
    « Stade de France » et « stade de france » designent le meme organisateur.
    Une unicite sensible a la casse laisserait creer les deux, et le doublon ne
    se verrait qu au moment ou un acheteur choisit le mauvais.
    """
    Organizer.objects.create(
        user=applicant,
        org_name="Stade de France",
        contact_email="a@example.test",
    )
    other = make_user(roles, "second@example.test")

    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=other,
            org_name="stade de FRANCE",
            contact_email="b@example.test",
        )


@pytest.mark.parametrize("rate", [Decimal("-0.0001"), Decimal("1.0001")])
def test_the_commission_rate_stays_between_zero_and_one(applicant, rate):
    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=applicant,
            org_name="Hors bornes",
            contact_email="a@example.test",
            commission_rate=rate,
        )


def test_an_unknown_status_is_rejected_by_the_database(applicant):
    """
    La contrainte lit le MEME tuple que le code (`constants.py`). Deux
    enumerations aux memes valeurs finissent par diverger — la panne tombe
    alors sur un chemin d ecriture, au pire moment.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        Organizer.objects.create(
            user=applicant,
            org_name="Etat invente",
            contact_email="a@example.test",
            validation_status="VALIDE",
        )


def test_deleting_an_account_that_carries_a_dossier_is_refused(applicant):
    """
    `PROTECT`, jamais `CASCADE` : supprimer le compte effacerait evenements,
    ventes et journaux de scan. L effacement RGPD passe par l anonymisation.
    """
    Organizer.objects.create(
        user=applicant,
        org_name="Protege",
        contact_email="a@example.test",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        applicant.delete()


def test_the_querysets_filter_by_business_state(applicant, roles):
    Organizer.objects.create(
        user=applicant,
        org_name="En attente",
        contact_email="a@example.test",
    )

    approved_user = make_user(roles, "approuve@example.test")

    Organizer.objects.create(
        user=approved_user,
        org_name="Approuve",
        contact_email="b@example.test",
        validation_status=ORGANIZER_APPROVED,
    )

    assert Organizer.objects.pending().count() == 1
    assert Organizer.objects.approved().count() == 1
    assert Organizer.objects.for_user(applicant).count() == 1
