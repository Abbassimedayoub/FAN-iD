"""
Tests for `POST /api/v1/auth/register` cover the HTTP contract, business rules,
and cross-cutting invariants such as closed input, secret redaction, and atomic
event publication.
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import get_hasher, identify_hasher
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.outbox.models import OutboxEvent
from apps.identity.constants import MINIMUM_AGE_YEARS, ROLE_FAN
from apps.identity.events import AGGREGATE_USER, USER_REGISTERED
from apps.identity.models import User
from apps.identity.services.registration import age_in_years

URL = "/api/v1/auth/register"
STRONG_PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """Use a test-local throttle counter so parallel workers cannot interfere through shared Redis state."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-register-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def payload(**overrides):
    body = {
        "email": "supporter@example.test",
        "password": STRONG_PASSWORD,
        "first_name": "Ines",
        "last_name": "Bouzid",
        "date_of_birth": "1996-05-04",
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


def birthdate_for_age(age: int, *, extra_days: int = 0) -> str:
    """Return a birth date exactly `age` years ago, handling leap-day edge cases deterministically."""
    today = timezone.localdate()
    month, day = (3, 1) if (today.month, today.day) == (2, 29) else (today.month, today.day)
    born = datetime.date(today.year - age, month, day) + datetime.timedelta(days=extra_days)
    return born.isoformat()


# ===========================================================================
# Contrat HTTP
# ===========================================================================


@pytest.mark.django_db
def test_a_valid_registration_returns_201_and_the_public_representation(client, roles):
    response = client.post(URL, payload(), format="json")

    assert response.status_code == 201, response.data
    body = response.data
    assert set(body) == {"id", "email", "first_name", "last_name", "role", "created_at"}
    assert body["email"] == "supporter@example.test"
    assert body["first_name"] == "Ines"
    assert body["role"] == ROLE_FAN


@pytest.mark.django_db
def test_the_response_never_echoes_the_password(client, roles):
    """Verify against the raw response body so password leakage cannot hide under a different or nested key."""
    response = client.post(URL, payload(), format="json")

    assert response.status_code == 201
    assert STRONG_PASSWORD not in response.content.decode()


@pytest.mark.django_db
def test_the_stored_password_is_hashed_by_the_configured_hasher(client, roles):
    """The stored password must be unreadable and verifiable; algorithm selection is tested separately as configuration."""
    client.post(URL, payload(), format="json")
    user = User.objects.get(email="supporter@example.test")

    assert user.password != STRONG_PASSWORD
    assert STRONG_PASSWORD not in user.password
    assert identify_hasher(user.password).algorithm == get_hasher("default").algorithm
    assert user.check_password(STRONG_PASSWORD)


def test_production_settings_hash_passwords_with_argon2id():
    """Read production password-hasher configuration from base settings rather than test-overridden active settings."""
    from config.settings import base as base_settings

    assert base_settings.PASSWORD_HASHERS[0] == "apps.identity.hashers.FanIdArgon2PasswordHasher"


# ===========================================================================
# Regles metier
# ===========================================================================


@pytest.mark.django_db
def test_someone_below_the_minimum_age_is_refused_with_an_actionable_code(client, roles):
    too_young = birthdate_for_age(MINIMUM_AGE_YEARS, extra_days=1)
    response = client.post(URL, payload(date_of_birth=too_young), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "UNDERAGE"
    assert response.data["error"]["details"] == {"minimum_age_years": MINIMUM_AGE_YEARS}
    assert not User.objects.filter(email__iexact="supporter@example.test").exists()


@pytest.mark.django_db
def test_exactly_the_minimum_age_is_accepted(client, roles):
    """The minimum-age boundary is inclusive."""
    response = client.post(URL, payload(date_of_birth=birthdate_for_age(MINIMUM_AGE_YEARS)), format="json")

    assert response.status_code == 201, response.data


@pytest.mark.django_db
def test_refusing_the_terms_is_a_named_business_error_not_a_field_error(client, roles):
    """Terms acceptance is a business rule handled by the service rather than serializer shape validation."""
    response = client.post(URL, payload(terms_accepted=False), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "TERMS_NOT_ACCEPTED"
    assert not User.objects.filter(email__iexact="supporter@example.test").exists()


@pytest.mark.django_db
def test_the_consent_timestamp_comes_from_the_server_not_from_the_client(client, roles):
    """The server owns the consent timestamp; client-supplied timestamps are outside the input contract."""
    before = timezone.now()
    client.post(URL, payload(terms_accepted_at="1999-01-01T00:00:00Z"), format="json")

    user = User.objects.get(email="supporter@example.test")
    assert user.terms_accepted_at >= before


@pytest.mark.django_db
def test_the_same_address_in_another_case_is_refused_as_a_duplicate(client, roles):
    """Email uniqueness is case-insensitive through the citext column type."""
    assert client.post(URL, payload(), format="json").status_code == 201

    response = client.post(URL, payload(email="Supporter@Example.TEST"), format="json")

    # Keep the published HTTP error contract stable because clients depend on it.
    assert response.status_code == 400
    assert response.data["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert User.objects.filter(email__iexact="supporter@example.test").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("weak", "why"),
    [
        ("Ab-12", "moins de 10 caracteres"),
        ("1234567890", "entierement numerique"),
    ],
)
def test_a_weak_password_is_refused_and_never_appears_in_the_error(client, roles, weak, why):
    """Use deterministic validators and ensure rejected password values never appear in the response."""
    response = client.post(URL, payload(password=weak), format="json")

    assert response.status_code == 400, why
    assert weak not in response.content.decode()
    assert not User.objects.filter(email__iexact="supporter@example.test").exists()


@pytest.mark.django_db
def test_a_password_too_similar_to_the_email_is_refused(client, roles):
    """Provide a non-persisted user to similarity validation so registration can compare account attributes and password safely."""
    response = client.post(
        URL, payload(email="chataigne.orageuse@example.test", password="chataigne.orageuse"), format="json"
    )

    assert response.status_code == 400
    assert not User.objects.filter(email__iexact="chataigne.orageuse@example.test").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_an_empty_name_is_refused(client, roles, field):
    """First and last names are required, and whitespace-only values remain invalid after DRF trimming."""
    assert client.post(URL, payload(**{field: ""}), format="json").status_code == 400
    assert client.post(URL, payload(**{field: "   "}), format="json").status_code == 400
    assert not User.objects.filter(email__iexact="supporter@example.test").exists()


@pytest.mark.django_db
def test_a_birth_date_in_the_future_is_a_form_error_not_an_age_refusal(client, roles):
    tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
    response = client.post(URL, payload(date_of_birth=tomorrow), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# Invariants transversaux
# ===========================================================================


@pytest.mark.django_db
def test_over_posting_privileged_fields_has_no_effect(client, roles):
    """Privilege fields are structurally absent from both serializer and RegistrationCommand, preventing over-posting."""
    response = client.post(
        URL,
        payload(
            role=str(roles["ADMIN"].id),
            is_staff=True,
            is_superuser=True,
            anonymized_at="2020-01-01T00:00:00Z",
        ),
        format="json",
    )

    assert response.status_code == 201, response.data
    user = User.objects.get(email="supporter@example.test")
    assert user.role.name == ROLE_FAN
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.anonymized_at is None


@pytest.mark.django_db
def test_registration_publishes_exactly_one_event_with_no_personal_data(client, roles):
    client.post(URL, payload(), format="json")

    user = User.objects.get(email="supporter@example.test")
    events = list(
        OutboxEvent.objects.filter(
            event_type=USER_REGISTERED,
            aggregate_type=AGGREGATE_USER,
            aggregate_id=user.pk,
        )
    )

    assert len(events) == 1
    event = events[0]
    assert str(event.aggregate_id) == str(user.pk)
    assert event.payload == {"role": ROLE_FAN}

    # Do not copy email or password data into the Outbox payload.
    # duplique hors du perimetre que l anonymisation RGPD sait atteindre.
    serialized = str(event.payload)
    assert "example.test" not in serialized
    assert STRONG_PASSWORD not in serialized


@pytest.mark.django_db
def test_a_refused_registration_publishes_no_event(client, roles):
    """Account creation and event publication share one transaction; no event may survive a failed account creation."""
    with patch("apps.identity.services.registration.publish_event") as publish_event_mock:
        client.post(URL, payload(terms_accepted=False), format="json")

    assert not User.objects.filter(email__iexact="supporter@example.test").exists()
    publish_event_mock.assert_not_called()


@pytest.mark.django_db
def test_the_endpoint_throttles_repeated_attempts(client, roles, monkeypatch):
    """The dedicated registration throttle must apply to this endpoint rather than the generic anonymous limit."""
    # `override_settings` serait SANS EFFET ici : DRF fige
    # `SimpleRateThrottle.THROTTLE_RATES` a l import du module, en capturant
    # l objet dictionnaire. Recharger les reglages remplace le dictionnaire de
    # `api_settings` mais la classe pointe toujours sur l ancien. Le test
    # passerait donc au vert en ne testant rien. On patche donc la classe.
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"register": "2/hour"})

    assert client.post(URL, payload(email="a@example.test"), format="json").status_code == 201
    assert client.post(URL, payload(email="b@example.test"), format="json").status_code == 201
    blocked = client.post(URL, payload(email="c@example.test"), format="json")

    assert blocked.status_code == 429
    assert blocked.data["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# ===========================================================================
# Calcul de l age
# ===========================================================================


@pytest.mark.parametrize(
    ("birth", "today", "expected"),
    [
        ((2010, 1, 1), (2026, 1, 1), 16),  # jour anniversaire : inclusif
        ((2010, 1, 2), (2026, 1, 1), 15),  # la veille : pas encore
        ((2010, 12, 31), (2026, 1, 1), 15),
        ((2008, 2, 29), (2026, 2, 28), 17),  # ne un 29 fevrier, annee non bissextile
        ((2008, 2, 29), (2026, 3, 1), 18),
        ((2000, 6, 15), (2026, 6, 14), 25),
    ],
)
def test_age_is_computed_by_calendar_not_by_dividing_days(birth, today, expected):
    """Leap-day cases guard against day-count age approximations that cross the boundary too early."""
    assert age_in_years(datetime.date(*birth), datetime.date(*today)) == expected
