from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.outbox.models import OutboxEvent
from apps.identity.constants import MFA_PURPOSE_PASSWORD_RESET, OTP_MAX_ATTEMPTS
from apps.identity.events import PASSWORD_RESET_COMPLETED, PASSWORD_RESET_REQUESTED
from apps.identity.models import MfaChallenge, Session, User
from apps.identity.services.password_reset import build_password_reset_magic_token, derive_password_reset_code
from apps.identity.services.tokens import TokenService

REQUEST_URL = "/api/v1/auth/password/reset/request"
CONFIRM_URL = "/api/v1/auth/password/reset/confirm"

OLD_PASSWORD = "Chataigne-Orageuse-2026"
NEW_PASSWORD = "Grenadine-Tumultueuse-2027"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(
    settings,
):
    settings.CACHES = {
        "default": {
            "BACKEND": ("django.core.cache.backends." "locmem.LocMemCache"),
            "LOCATION": ("password-reset-tests"),
        }
    }

    cache.clear()

    yield

    cache.clear()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def make_user(
    *,
    roles,
    role_name: str = "FAN",
    email: str = "recovery@example.test",
) -> User:
    return User.objects.create_user(
        email=email,
        password=OLD_PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1996,
            5,
            4,
        ),
        terms_accepted_at=(timezone.now()),
        role=roles[role_name],
    )


def request_reset(
    client: APIClient,
    *,
    email: str,
):
    return client.post(
        REQUEST_URL,
        {
            "email": email,
        },
        format="json",
    )


def current_challenge(
    user: User,
) -> MfaChallenge:
    return MfaChallenge.objects.filter(
        user=user,
        purpose=(MFA_PURPOSE_PASSWORD_RESET),
    ).latest("created_at")


@pytest.mark.parametrize(
    "role_name",
    [
        "FAN",
        "ORGANIZER",
        "SCANNER",
        "ADMIN",
    ],
)
@pytest.mark.django_db
def test_every_role_can_request_password_reset(
    client,
    roles,
    role_name,
):
    user = make_user(
        roles=roles,
        role_name=role_name,
        email=(role_name.lower() + "@example.test"),
    )

    response = request_reset(
        client,
        email=user.email,
    )

    assert response.status_code == 200

    assert response.data["expires_in_seconds"] == 15 * 60

    assert (
        MfaChallenge.objects.filter(
            user=user,
            purpose=(MFA_PURPOSE_PASSWORD_RESET),
        ).count()
        == 1
    )

    event = OutboxEvent.objects.filter(
        aggregate_id=user.pk,
        event_type=(PASSWORD_RESET_REQUESTED),
    ).get()

    assert "challenge_id" in (event.payload)

    assert user.email not in (str(event.payload))


@pytest.mark.django_db
def test_unknown_email_has_identical_public_response(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    known = request_reset(
        client,
        email=user.email,
    )

    unknown = request_reset(
        client,
        email="unknown@example.test",
    )

    assert known.status_code == unknown.status_code == 200

    assert known.data == (unknown.data)

    assert (
        OutboxEvent.objects.filter(
            event_type=(PASSWORD_RESET_REQUESTED),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_six_digit_code_resets_password(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    challenge = current_challenge(user)

    code = derive_password_reset_code(challenge.pk)

    assert len(code) == 6 and code.isdigit()

    response = client.post(
        CONFIRM_URL,
        {
            "email": user.email,
            "code": code,
            "new_password": (NEW_PASSWORD),
        },
        format="json",
    )

    assert response.status_code == 204

    user.refresh_from_db()

    assert user.check_password(NEW_PASSWORD)

    challenge.refresh_from_db()

    assert challenge.consumed_at is not None

    assert OutboxEvent.objects.filter(
        aggregate_id=user.pk,
        event_type=(PASSWORD_RESET_COMPLETED),
    ).exists()


@pytest.mark.django_db
def test_magic_link_resets_password(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    challenge = current_challenge(user)

    token = build_password_reset_magic_token(
        challenge_id=(challenge.pk),
        user_id=user.pk,
    )

    response = client.post(
        CONFIRM_URL,
        {
            "token": token,
            "new_password": (NEW_PASSWORD),
        },
        format="json",
    )

    assert response.status_code == 204

    user.refresh_from_db()

    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_magic_link_is_single_use(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    challenge = current_challenge(user)

    token = build_password_reset_magic_token(
        challenge_id=(challenge.pk),
        user_id=user.pk,
    )

    first = client.post(
        CONFIRM_URL,
        {
            "token": token,
            "new_password": (NEW_PASSWORD),
        },
        format="json",
    )

    second = client.post(
        CONFIRM_URL,
        {
            "token": token,
            "new_password": ("Trompette-Neigeuse-2028"),
        },
        format="json",
    )

    assert first.status_code == 204

    assert second.status_code == 400

    assert second.data["error"]["code"] == "PASSWORD_RESET_INVALID"


@pytest.mark.django_db
def test_reset_revokes_every_session(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    first = TokenService.issue_pair(user=user)

    second = TokenService.issue_pair(user=user)

    request_reset(
        client,
        email=user.email,
    )

    challenge = current_challenge(user)

    token = build_password_reset_magic_token(
        challenge_id=(challenge.pk),
        user_id=user.pk,
    )

    response = client.post(
        CONFIRM_URL,
        {
            "token": token,
            "new_password": (NEW_PASSWORD),
        },
        format="json",
    )

    assert response.status_code == 204

    for pair in (
        first,
        second,
    ):
        session = Session.objects.get(pk=pair.session.pk)

        assert session.revoked_at is not None


@pytest.mark.django_db
def test_weak_password_does_not_consume_valid_challenge(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    challenge = current_challenge(user)

    code = derive_password_reset_code(challenge.pk)

    response = client.post(
        CONFIRM_URL,
        {
            "email": user.email,
            "code": code,
            "new_password": ("12345678901"),
        },
        format="json",
    )

    assert response.status_code == 400

    assert response.data["error"]["code"] == "VALIDATION_ERROR"

    challenge.refresh_from_db()

    assert challenge.consumed_at is None

    user.refresh_from_db()

    assert user.check_password(OLD_PASSWORD)


@pytest.mark.django_db
def test_new_request_invalidates_previous_challenge(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    first = current_challenge(user)

    request_reset(
        client,
        email=user.email,
    )

    first.refresh_from_db()

    second = current_challenge(user)

    assert first.pk != second.pk

    assert first.consumed_at is not None

    assert second.consumed_at is None


@pytest.mark.django_db
def test_wrong_code_is_limited_to_five_attempts(
    client,
    roles,
):
    user = make_user(
        roles=roles,
    )

    request_reset(
        client,
        email=user.email,
    )

    responses = []

    for _ in range(OTP_MAX_ATTEMPTS):
        responses.append(
            client.post(
                CONFIRM_URL,
                {
                    "email": (user.email),
                    "code": "999999",
                    "new_password": (NEW_PASSWORD),
                },
                format="json",
            )
        )

    assert [response.status_code for response in responses[:-1]] == [400] * (OTP_MAX_ATTEMPTS - 1)

    assert responses[-1].status_code == 429

    challenge = current_challenge(user)

    assert challenge.attempts == OTP_MAX_ATTEMPTS

    assert challenge.consumed_at is not None


@pytest.mark.django_db
def test_bad_magic_token_is_generic(
    client,
):
    response = client.post(
        CONFIRM_URL,
        {
            "token": ("not-a-valid-reset-token"),
            "new_password": (NEW_PASSWORD),
        },
        format="json",
    )

    assert response.status_code == 400

    assert response.data["error"]["code"] == "PASSWORD_RESET_INVALID"
