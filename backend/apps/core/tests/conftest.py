import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


# `get_user_model()` est utilisé à dessein plutôt qu'un import direct de
# `apps.identity` : le contrat import-linter `core-is-independent` couvre AUSSI
# `apps.core.tests`, qui ne doit donc importer aucun bounded context.
# `roles` est requise explicitement : une fixture qui crée un utilisateur
# dépend du référentiel des rôles, que les tests transactionnels effacent
# (voir apps/conftest.py).
@pytest.fixture
def user(db, roles):
    User = get_user_model()
    return User.objects.create_user(
        email="fan@example.test",
        password="irrelevant-for-s0",
        date_of_birth=datetime.date(1995, 5, 5),
        terms_accepted_at=timezone.now(),
    )


@pytest.fixture
def other_user(db, roles):
    User = get_user_model()
    return User.objects.create_user(
        email="other@example.test",
        password="irrelevant-for-s0",
        date_of_birth=datetime.date(1990, 3, 3),
        terms_accepted_at=timezone.now(),
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
