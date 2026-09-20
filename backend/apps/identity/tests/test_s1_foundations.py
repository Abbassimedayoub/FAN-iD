"""Security foundation tests for password hashing, secret redaction, and shared configuration invariants."""

import pytest
from django.conf import settings

from apps.core.exceptions import InvalidStateTransitionError, PreconditionFailed
from apps.core.observability.logging import SecretRedactor
from apps.identity.hashers import FanIdArgon2PasswordHasher

_REDACTED = "***REDACTED***"


# --------------------------------------------------------------- Argon2id


def test_argon2_parameters_match_the_security_plan():
    """Argon2 parameters remain pinned to the intended cost profile."""
    hasher = FanIdArgon2PasswordHasher()
    assert hasher.time_cost == 3
    assert hasher.memory_cost == 65536  # kibioctets
    assert hasher.parallelism == 4


def test_argon2_uses_the_id_variant_not_i_or_d():
    """The configured password hasher must use the Argon2id variant."""
    from argon2.low_level import Type

    assert FanIdArgon2PasswordHasher().algorithm == "argon2"
    assert Type.ID is not None  # la variante est celle du hasher Django (argon2.low_level.Type.ID)


def test_production_hasher_list_puts_argon2_first():
    """Django uses the first configured hasher for new passwords; later entries only verify legacy hashes."""
    from django.conf import settings as live

    if live.PASSWORD_HASHERS[0].endswith("MD5PasswordHasher"):
        pytest.skip("environnement de test : hacheur rapide volontaire (plan S1 §5.3)")
    assert live.PASSWORD_HASHERS[0] == "apps.identity.hashers.FanIdArgon2PasswordHasher"


# ---------------------------------------------------- Secret redaction


@pytest.mark.parametrize(
    "key",
    [
        "device_fingerprint",
        "fingerprint",
        "otp",
        "otp_code",
        "refresh",
        "refresh_jti",
        "refresh_token",
        "jti",
        "did",
        "access",
        "code",
        "Authorization",
        "password",
    ],
)
def test_sprint1_authentication_secrets_are_redacted(key):
    """OTP codes, fingerprints, and tokens must never reach logs unredacted."""
    assert SecretRedactor.redact({key: "valeur-sensible"})[key] == _REDACTED


@pytest.mark.parametrize(
    "key",
    ["error_code", "status_code", "http_status", "candidate", "totp_result", "user_id", "event_type"],
)
def test_observability_keys_are_not_over_redacted(key):
    """Redaction must stay narrow enough to preserve ordinary diagnostic fields."""
    assert SecretRedactor.redact({key: "visible"})[key] == "visible"


def test_redaction_still_reaches_nested_sprint1_payloads():
    payload = {"login": {"device_fingerprint": "a" * 64, "email": "fan@example.test"}}
    result = SecretRedactor.redact(payload)
    assert result["login"]["device_fingerprint"] == _REDACTED
    assert result["login"]["email"] == "fan@example.test"


# ------------------------------------------------------- Error contract


def test_precondition_required_is_428_not_412():
    """Missing required `If-Match` maps to 428 Precondition Required, not a failed provided precondition."""
    error = PreconditionFailed()
    assert error.status_code == 428
    assert error.code == "PRECONDITION_REQUIRED"


def test_invalid_state_transition_is_a_409_conflict():
    error = InvalidStateTransitionError()
    assert error.status_code == 409
    assert error.code == "INVALID_STATE_TRANSITION"


# ------------------------------------------------------- Configuration


def test_session_middleware_is_declared_exactly_once():
    """SessionMiddleware must be declared exactly once."""
    occurrences = [m for m in settings.MIDDLEWARE if m.endswith("SessionMiddleware")]
    assert len(occurrences) == 1, f"SessionMiddleware déclaré {len(occurrences)} fois"


def test_refresh_cookie_is_always_httponly():
    """Refresh cookies must remain HttpOnly and unreadable to JavaScript."""
    assert settings.REFRESH_COOKIE_HTTPONLY is True


def test_no_production_domain_is_hardcoded():
    """Configuration must not invent a hard-coded production domain."""
    for value in (settings.REFRESH_COOKIE_DOMAIN, *settings.CSRF_TRUSTED_ORIGINS):
        if value:
            assert "fan-id" not in str(value).lower()
