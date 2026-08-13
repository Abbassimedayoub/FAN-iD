import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="fan-test", email="fan@example.test", password="irrelevant-for-s0"
    )


@pytest.fixture
def other_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="fan-other", email="other@example.test", password="irrelevant-for-s0"
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
