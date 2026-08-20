"""
`subject_from_request` — l organisateur vient de la requete, pas d une requete SQL.

Ce fichier fige la moitie `identity` de l option B d ADR-S1-05 : le contexte
lit un primitif pose par la couche exterieure, exactement comme il lit deja
`auth_level`, et refuse tout ce qui n est pas un UUID.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from apps.identity.authz.context import subject_from_request
from apps.identity.constants import ROLE_IDS, ROLE_ORGANIZER

ORG_ID = uuid.uuid4()


def fake_request(**extra):
    user = SimpleNamespace(
        pk=uuid.uuid4(),
        is_authenticated=True,
        is_active=True,
        anonymized_at=None,
        role_id=ROLE_IDS[ROLE_ORGANIZER],
    )
    return SimpleNamespace(user=user, **extra)


def test_the_organizer_is_read_from_the_request():
    subject = subject_from_request(fake_request(organizer_id=ORG_ID))

    assert subject.organizer_id == ORG_ID


def test_the_organizer_approval_is_read_from_the_request():
    subject = subject_from_request(
        fake_request(
            organizer_id=ORG_ID,
            organizer_approved=True,
        )
    )

    assert subject.organizer_is_approved is True


def test_an_absent_approval_is_fail_closed():
    subject = subject_from_request(fake_request(organizer_id=ORG_ID))

    assert subject.organizer_is_approved is False


@pytest.mark.parametrize("value", [1, 0, "true", "false", None, object()])
def test_anything_that_is_not_a_boolean_is_not_approved(value):
    subject = subject_from_request(
        fake_request(
            organizer_id=ORG_ID,
            organizer_approved=value,
        )
    )

    assert subject.organizer_is_approved is False


def test_an_absent_organizer_gives_none_rather_than_an_error():
    """
    C est le cas d une requete servie par un contexte qui n enrichit pas — la
    quasi-totalite de l API. Le sujet doit se construire normalement, sans
    organisateur.
    """
    subject = subject_from_request(fake_request())

    assert subject.organizer_id is None


@pytest.mark.parametrize("value", ["pas-un-uuid", 42, "", None, object()])
def test_anything_that_is_not_a_uuid_is_ignored(value):
    """
    Meme garde que pour `role_id` : une valeur inattendue ne doit pas lever au
    milieu d un controle d autorisation, elle doit produire l absence de droit.
    """
    subject = subject_from_request(fake_request(organizer_id=value))

    assert subject.organizer_id is None


def test_no_query_is_issued_while_building_the_subject(db, django_assert_num_queries):
    """
    L invariant du lot S1-A.2, preserve. C est la raison pour laquelle
    `resolve_organizer_id()` a ete SUPPRIMEE plutot que remplie : la remplir
    aurait coute une requete par controle d autorisation — sur le chemin le
    plus chaud de l API, et invisible tant qu on ne compte pas.
    """
    with django_assert_num_queries(0):
        subject_from_request(
            fake_request(
                organizer_id=ORG_ID,
                organizer_approved=True,
            )
        )
